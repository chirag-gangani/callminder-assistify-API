from datetime import datetime
import json
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import base64
from openai import OpenAI
from smallest import Smallest
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from pydub import AudioSegment
from typing import Optional
from ..config import settings
from ..utils.constants import END_CALL_PHRASES, DEFAULT_SALES_PROMPT
from ..models.retrieval import RetrievalResult
from .audio_manager import AudioStreamManager
import random
import whisper
import time

# Define ai_agents as a global dictionary
ai_agents = {}

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=10)

model = whisper.load_model("tiny")

class AI_SalesAgent:
    def __init__(self, system_prompt=None, encoder=None):
        self.system_prompt = system_prompt or DEFAULT_SALES_PROMPT
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.smallestai_client = Smallest(api_key=settings.SMALLEST_API_KEY)
        self.conversation_history = [{"role": "system", "content": self.system_prompt}]
        self.end_call_detected = False
        self.end_call_confirmed = False
        self.client_entities = {
            "name": None,
            "email": None,
            "company_name": None,
            "requirements": [],
            "meeting_date": None,
            "meeting_time": None,
            "industry": None
        }
        self.audio_manager = AudioStreamManager()
        self.encoder = encoder  # Use the encoder passed as an argument
        self.documents = []
        self.embeddings = []
        self.sources = []
        self.page_numbers = []

    def check_for_end_call(self, text: str) -> bool:
        return any(phrase.lower() in text.lower() for phrase in END_CALL_PHRASES)\

    async def process_audio_to_text(self, audio_data: bytes) -> str:
        try:
            logger.info("Processing audio with Whisper-Tiny (Local)")

            start_time = time.time()
            
            # Save the bytes to a temporary file-like object
            temp_file = io.BytesIO(audio_data)

            # Run Whisper in an executor to keep function async-friendly
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.transcribe_audio(temp_file))

            logger.debug(f"Raw STT response: {response}")

            transcribed_text = response
            elapsed_time = time.time() - start_time
            logger.info(f"STT processing time: {elapsed_time:.2f} seconds")
            logger.info(f"Transcribed text: {transcribed_text}")
            return transcribed_text

        except Exception as e:
            logger.error(f"Error in audio transcription: {str(e)}", exc_info=True)
            return ""

    def transcribe_audio(temp_file: io.BytesIO) -> str:
        """Helper function to transcribe audio from a BytesIO object using Whisper-Tiny."""
        temp_file.seek(0)  # Reset file pointer
        return model.transcribe(temp_file)["text"]

    async def generate_response(self, user_input: str, was_interrupted: bool = False) -> tuple[str, None, bool]:
        try:
            if self.end_call_detected and ("yes" in user_input.lower() or "okay" in user_input.lower()):
                self.end_call_confirmed = True
                return "Thank you for your time. Have a great day!", None, True
            
            if self.check_for_end_call(user_input) and not self.end_call_detected:
                self.end_call_detected = True
                return "Would you like to end our conversation?", None, False
            
            retrieved = self.retrieve_relevant_chunks(user_input)
            context = "\n".join([f"Context {i+1}: {chunk}" 
                            for i, chunk in enumerate(retrieved.chunks)])
            
            enhanced_input = f"""User Input: {user_input}

            Retrieved Context:
            {context}

            Based on the system prompt and above context, generate a response.

            Current Entities Tracked:
            {json.dumps(self.client_entities, indent=2)}"""
            
            self.conversation_history.append({"role": "user", "content": enhanced_input})
            
            # Run the OpenAI API call in a separate thread
            response = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo-1106",
                    messages=[
                        {"role": "system", "content": DEFAULT_SALES_PROMPT},
                        *self.conversation_history
                    ],
                    temperature=0.1,
                    max_tokens=75
                )
            )
            
            response_text = response.choices[0].message.content
            spoken_response, entities = self.extract_entities(response_text)
            
            # Log the AI-generated response
            logger.info(f"AI Generated Response: {spoken_response}")
            
            if entities:
                # Log the extracted entities
                logger.info(f"Extracted Entities: {json.dumps(entities, indent=2)}")
                self.update_entities(entities)
            
            self.conversation_history.append({"role": "assistant", "content": spoken_response})
            return spoken_response, None, self.end_call_detected
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I apologize, but I'm having trouble processing that. Could you please repeat?", None, False

    def extract_entities(self, response_text: str) -> tuple[str, Optional[dict]]:
        parts = response_text.split("[[ENTITIES]]")
        spoken_response = parts[0].strip()
        entities = None
        if len(parts) > 1:
            try:
                entities_text = parts[1].strip()
                entities = json.loads(entities_text)
            except Exception as e:
                logger.error(f"Error parsing entities: {str(e)}")
        return spoken_response, entities

    def update_entities(self, entities: dict):
        if "entities" in entities:
            entities = entities["entities"]
        for key, value in entities.items():
            if value is not None:
                self.client_entities[key] = value

    def retrieve_relevant_chunks(self, query: str, k: int = 3) -> RetrievalResult:
        if not self.documents:
            return RetrievalResult.empty()
            
        query_embedding = self.encoder.encode([query])[0]
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        
        top_k_indices = np.argsort(similarities)[-k:][::-1]
        
        result = RetrievalResult()
        result.chunks = [self.documents[i] for i in top_k_indices]
        result.similarities = [float(similarities[i]) for i in top_k_indices]
        result.sources = [self.sources[i] for i in top_k_indices]
        result.page_numbers = [self.page_numbers[i] for i in top_k_indices]
        
        return result