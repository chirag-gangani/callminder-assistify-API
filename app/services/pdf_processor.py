import io
import logging
from typing import Optional
import PyPDF2
from openai import OpenAI
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self):
        self.client = OpenAI()

    def extract_text_from_pdf(self, file_content: bytes) -> Optional[str]:
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            logger.info(f"Processing PDF with {len(pdf_reader.pages)} pages")
            
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += page_text
                logger.debug(f"Page {i+1} extracted text length: {len(page_text)} characters")
            
            if not text.strip():
                logger.warning("No text extracted from PDF")
                return None
                
            logger.info(f"Total extracted text length: {len(text)} characters")
            return text
            
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return None

    def process_text_for_rag(self, text: str) -> list[str]:
        sentences = text.split('. ')
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_size = 300 
        
        for sentence in sentences:
            sentence = sentence.strip() + '. '
            sentence_length = len(sentence)
            
            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
                
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        return chunks

    def create_sales_prompt(self, company_info: dict) -> str:
        try:
            logger.info("Creating sales prompt from structured info")
            
            prompt = f"""You are an outbound AI sales agent for {company_info['company_name']}.
            You've already introduced yourself at the start of the call, so don't introduce yourself again. 
            And Don't say Hello or Hi etc..
            Your role is to understand client needs and guide them toward our solutions.

            Available Services:
            {self._format_services(company_info['services'])}

            Industries We Serve: {', '.join(company_info['industries_served'])}

            Key Points:
            {self._format_points(company_info['unique_selling_points'])}

            Consider today's date as {datetime.now().strftime("%d-%m-%Y")} and time as {datetime.now().strftime("%I:%M %p")}.
            """
            
            logger.debug("Generated prompt")
            return prompt
            
        except Exception as e:
            logger.error(f"Error creating sales prompt: {str(e)}")
            return None

    def _format_services(self, services):
        return "\n".join([f"- {service['name']}: {service['description']}" for service in services])

    def _format_points(self, points):
        return "\n".join([f"- {point}" for point in points])

    def structure_company_info(self, pdf_text: str) -> Optional[dict]:
        try:
            logger.info("Structuring company information from PDF text")
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract company information from the given text. "
                            "Respond in JSON format with company details."
                        )
                    },
                    {"role": "user", "content": pdf_text},
                ],
                temperature=0.7
            )

            structured_info = json.loads(response.choices[0].message.content.strip())
            logger.info("Successfully structured company info")
            return structured_info

        except Exception as e:
            logger.error(f"Error structuring company info: {str(e)}")
            return None