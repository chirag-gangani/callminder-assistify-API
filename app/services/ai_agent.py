from datetime import datetime
import json
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from openai import OpenAI
from smallest import Smallest
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import Optional
from ..config import settings
from ..utils.constants import END_CALL_PHRASES, DEFAULT_SALES_PROMPT
from ..models.retrieval import RetrievalResult
from .audio_manager import AudioStreamManager
import whisper
import re
from .google_calendar_manager import GoogleCalendarManager  # Import GoogleCalendarManager
from .salesforce_integration import SalesforceIntegration  # Import SalesforceIntegration
from functools import lru_cache

# Define ai_agents as a global dictionary
ai_agents = {}

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=10)

model = whisper.load_model("base") # or small
# model = WhisperModel("small", device="cpu", compute_type="int8")

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
        self.conversation_summary = None
        self.raw_entity_history = []
        self.calendar_manager = GoogleCalendarManager()  # Initialize Google Calendar Manager
        self.salesforce_integration = SalesforceIntegration()  # Initialize Salesforce Integration

        # Preload the OpenAI model
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.preload_openai_model())
        else:
            asyncio.run(self.preload_openai_model())

    async def preload_openai_model(self):
        """Preload the OpenAI model to reduce initial delay."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Preloading model."},
                    {"role": "user", "content": "Hello"}
                ],
                temperature=0,
                max_tokens=1
            ))
            logger.info("OpenAI model preloaded successfully.")
        except Exception as e:
            logger.error(f"Error preloading OpenAI model: {str(e)}")

    def check_for_end_call(self, text: str) -> bool:
        return any(phrase.lower() in text.lower() for phrase in END_CALL_PHRASES)\

    async def process_audio_to_text(self, audio_data: bytes) -> str:
        try:
            temp_file = io.BytesIO(audio_data)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.transcribe_audio(temp_file))
            transcribed_text = response
            return transcribed_text
        except Exception as e:
            logger.error(f"Error in audio transcription: {str(e)}", exc_info=True)
            return ""

    def transcribe_audio(temp_file: io.BytesIO) -> str:
        """Helper function to transcribe audio from a BytesIO object using Whisper-Tiny."""
        temp_file.seek(0)  # Reset file pointer
        return model.transcribe(temp_file)["text"]

    def sanitize_email(self, email: str) -> str:
        """Sanitize and validate the email address."""
        # Remove any unwanted characters and spaces
        email = email.strip()
        # Use regex to validate the email format
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return email
        return None  # Return None if the email is invalid

    @lru_cache(maxsize=128)
    def extract_entities(self, response_text: str) -> tuple[str, Optional[dict]]:
        """Extract entities with improved parsing."""
        try:
            # Split on [[ENTITIES]] and [[END_ENTITIES]]
            parts = response_text.split("[[ENTITIES]]")
            spoken_response = parts[0].strip()
            entities = None
            
            if len(parts) > 1:
                entities_text = parts[1].split("[[END_ENTITIES]]")[0].strip()
                logger.debug(f"Raw entities text found: {entities_text}")
                
                if entities_text:
                    try:
                        # Clean and parse the JSON
                        cleaned_text = entities_text.replace("'", '"').strip()
                        entities = json.loads(cleaned_text)
                        
                        # Ensure proper structure
                        if not isinstance(entities, dict):
                            entities = {"entities": {}}
                        elif "entities" not in entities:
                            entities = {"entities": entities}
                        
                        logger.debug(f"Successfully parsed entities: {entities}")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing error: {str(e)}, Raw text: {entities_text}")
            
            # Ensure that the response does not include extra data
            return spoken_response, entities
            
        except Exception as e:
            logger.error(f"Error in extract_entities: {str(e)}")
            return response_text, None

    async def generate_response(self, user_input: str, was_interrupted: bool = False) -> tuple[str, None, bool]:
        try:
            if not user_input:
                return "I didn't catch that. Could you please repeat?", None, False

            if self.end_call_detected:
                if "yes" in user_input.lower() or "okay" in user_input.lower():
                    self.end_call_confirmed = True
                    logger.debug(f"Current client entities: {self.client_entities}")
                    logger.debug(f"Raw entity history length: {len(self.raw_entity_history)}")
                    self.print_raw_entities()

                    # Sanitize email before returning
                    sanitized_email = self.sanitize_email(self.client_entities.get('email', ''))
                    if sanitized_email:
                        self.client_entities['email'] = sanitized_email
                    else:
                        logger.error("Invalid email address provided. Cannot create calendar event or Salesforce lead.")
                        return "Thank you for your time. However, there was an issue with the email provided.", None, True

                    return "Thank you for your time. The call has ended.", None, True  # Return without creating events

            if self.check_for_end_call(user_input) and not self.end_call_detected:
                self.end_call_detected = True
                return "Would you like to end our conversation?", None, False

            # Parse the current conversation for entities
            current_entities = self.parse_conversation_for_entities(user_input)
            
            # Create the prompt with the current entity state
            entity_state = {
                "entities": {
                    "name": current_entities.get("name", self.client_entities["name"]),
                    "email": current_entities.get("email", self.client_entities["email"]),
                    "company_name": current_entities.get("company_name", self.client_entities["company_name"]),
                    "requirements": current_entities.get("requirements", self.client_entities["requirements"]),
                    "meeting_date": current_entities.get("meeting_date", self.client_entities["meeting_date"]),
                    "meeting_time": current_entities.get("meeting_time", self.client_entities["meeting_time"]),
                    "industry": current_entities.get("industry", self.client_entities["industry"])
                }
            }
            
            # Append user input with instructions for entity response
            enhanced_prompt = (
                f"{user_input}\n\n"
                f"Current entities state: {json.dumps(entity_state)}\n"
                "Important: Update and include all entities in your response after [[ENTITIES]] tag, "
                "even if they haven't changed. Use format:\n"
                "Your response text\n"
                "[[ENTITIES]]\n"
                '{"entities": {...}}\n'
                "[[END_ENTITIES]]"
            )
            
            # Run the OpenAI API call concurrently
            loop = asyncio.get_event_loop()
            openai_task = loop.run_in_executor(None, lambda: self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation_history,
                    {"role": "user", "content": enhanced_prompt}
                ],
                temperature=0,
                max_tokens=150
            ))

            response = await openai_task
            
            response_text = response.choices[0].message.content
            print("***********************************")
            print(f"Raw response from OpenAI: \n{response_text}")
            print("***********************************")
            
            # Extract entities and store them
            spoken_response, entities = await loop.run_in_executor(None, lambda: self.extract_entities(response_text))
            
            if entities:
                logger.debug(f"Extracted entities: {entities}")
                try:
                    # Store the raw response and entities
                    self.raw_entity_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'raw_response': response_text,
                        'extracted_entities': entities,
                        'client_entities_state': self.client_entities.copy()
                    })
                    self.update_entities(entities)
                except Exception as e:
                    logger.error(f"Error storing entities: {str(e)}")
            
            self.conversation_history.append({"role": "assistant", "content": spoken_response})
            return spoken_response, None, self.end_call_detected
                
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            if self.end_call_detected:
                return "Thank you for your time. Have a great day!", None, True
            return "I apologize, but I'm having trouble processing that. Could you please repeat?", None, False

    def parse_conversation_for_entities(self, user_input: str) -> dict:
        """Parse the user input for potential entities."""
        entities = {}
        
        # Basic entity extraction logic
        # Name detection (if someone says "my name is" or "I am")
        name_patterns = [r"my name is (\w+)", r"I am (\w+)", r"I'm (\w+)"]
        for pattern in name_patterns:
            match = re.search(pattern, user_input.lower())
            if match:
                entities["name"] = match.group(1).capitalize()
        
        # Email detection
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, user_input)
        if email_match:
            entities["email"] = email_match.group(0)
        
        # Meeting date detection
        date_pattern = r'(\d{2}-\d{2}-\d{4})'
        date_match = re.search(date_pattern, user_input)
        if date_match:
            entities["meeting_date"] = date_match.group(0)
        
        # Meeting time detection
        time_pattern = r'(\d{2}:\d{2})'
        time_match = re.search(time_pattern, user_input)
        if time_match:
            entities["meeting_time"] = time_match.group(0)
        
        return entities

    def update_entities(self, entities: Optional[dict]):
        """Update client entities with better error handling."""
        if not entities:  # Handle None or empty dict case
            logger.debug("No entities to update")
            return
            
        try:
            logger.debug(f"Updating entities with: {entities}")
            if isinstance(entities, dict):
                if "entities" in entities:
                    entities = entities["entities"]
                
                for key, value in entities.items():
                    if value is not None and key in self.client_entities:
                        self.client_entities[key] = value
                        
                logger.debug(f"Updated client_entities: {self.client_entities}")
        except Exception as e:
            logger.error(f"Error in update_entities: {str(e)}")

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

    async def generate_conversation_summary(self) -> str:
        """Generate a summary of the conversation using OpenAI."""
        try:
            print("start")
            # Format the conversation history into a clear format for the AI
            formatted_conversation = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
                for msg in self.conversation_history
                if msg['role'] != 'system'
            ])
            print("formatted_conversation",formatted_conversation)
            # Create the summarization prompt
            summary_prompt = [
    {"role": "system", "content": """Please analyze this sales conversation and provide a concise summary including:
    1. Key points discussed  
    2. Customer's main interests/concerns  
    3. Any commitments or next steps  
    4. Important details captured (contact info, requirements, etc.)  

    If you did not get conversation for analyze, give "Conversation Not Found For make Summary" in response.

     Do **not** include a "Key points discussed" section. 

    Additionally, based on the conversation, classify the outcome with one of the following labels:  
    - **Converted**: If the customer has successfully scheduled a meeting with the manager.  
    - **Follow Up**: If the customer is interested but requests another time to connect.  
    - **Rejected**: If the customer is not interested, declines the offer, or the conversation is missing/not found.  

    At the end of the summary, explicitly mention the classification in the format: **Outcome: [Converted/Follow Up/Rejected]**.
    """},
    {"role": "user", "content": f"Here's the conversation to summarize:\n\n{formatted_conversation}"}
]


            # Get summary from OpenAI
            response = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo-1106",
                    messages=summary_prompt,
                    temperature=0.1,
                    max_tokens=150
                )
            )

            print("END>>>>>>>>>>",response.choices[0].message.content)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating conversation summary: {str(e)}")
            return "Error generating summary"

    def print_conversation(self):
        for message in self.conversation_history:
            if message["role"] == "user":
                user_input = message["content"].split("User Input:")[-1].strip()
                print(f"User: {user_input}")
            elif message["role"] == "assistant":
                print(f"AI: {message['content']}")
        
    async def print_summary(self):
        print("HELLO")
        summary = await self.generate_conversation_summary()
        self.conversation_summary = summary
        
    def get_latest_summary(self) -> dict:
        """Return the latest conversation summary with status."""
        if self.conversation_summary:
            return {
                "status": "success",
                "summary": self.conversation_summary
            }
        return {
            "status": "pending",
            "summary": "No summary available."
        }
        
    def print_raw_entities(self):
        """Print all entities captured during the conversation."""
        print("\n=== Entity Tracking Summary ===")
        print(f"Total entities captured: {len(self.raw_entity_history)}")
        
        if not self.raw_entity_history:
            print("\nDebug: Raw entity history is empty!")
            print("Current client entities state:")
            print(json.dumps(self.client_entities, indent=2))
            print("\nNo entities were captured during this call.")
            return
        
        print("\nFinal Client Entities State:")
        print(json.dumps(self.client_entities, indent=2))
        
        print("\nEntity Extraction History:")
        for idx, entry in enumerate(self.raw_entity_history, 1):
            print(f"\n=== Extraction #{idx} ===")
            print(f"Timestamp: {entry['timestamp']}")
            print("\nRaw Response:")
            print(entry['raw_response'])
            print("\nExtracted Entities:")
            print(json.dumps(entry['extracted_entities'], indent=2))
            print("\nClient Entities State at this point:")
            print(json.dumps(entry['client_entities_state'], indent=2))
            print("-" * 50)

    def get_raw_entities(self):
        """Return the raw entity history as a dictionary."""
        return {
            "status": "success" if self.raw_entity_history else "no_entities",
            "entity_history": self.raw_entity_history
        }