from fastapi import APIRouter, Request, File, UploadFile, HTTPException
from fastapi.responses import Response, JSONResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from ..services.ai_agent import AI_SalesAgent, ai_agents
from ..services.pdf_processor import PDFProcessor
from twilio.rest import Client
from ..config import settings  # Ensure you have a config file to load environment variables
import logging  # Import logging
from pydantic import BaseModel

# Set up logging
logger = logging.getLogger(__name__)  # Initialize the logger

router = APIRouter()

class SummaryResponse(BaseModel):
    summary: str
    status: str = "success"

@router.get("/get_summary", response_model=SummaryResponse)
async def get_summary():
    """Endpoint to get the latest conversation summary."""
    try:
        if not ai_agents:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "summary": "No active conversations found"
                }
            )

        # Get the latest agent's ID (assuming it's the most recent key)
        latest_call_id = max(ai_agents.keys())
        latest_agent = ai_agents[latest_call_id]
        
        result = latest_agent.get_latest_summary()
        
        if result["status"] == "pending":
            return JSONResponse(
                status_code=202,  # 202 Accepted indicates the request is processing
                content=result
            )
            
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "summary": f"Error retrieving summary: {str(e)}"
            }
        )

@router.post("/twilio/voice")
async def handle_incoming_call(request: Request):
    response = VoiceResponse()
    gather = Gather(
        input='speech',
        action='/process_speech',
        method='POST',
        language='en-US',
        speechTimeout=1,
        timeout=5
    )
    gather.say("Hello! I'm calling from Toshal Infotech. Is this a good time to talk?")
    response.append(gather)
    return Response(content=str(response), media_type='text/xml')

@router.post("/process_speech")
async def process_speech(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        speech_result = form_data.get('SpeechResult', '')
        
        if call_sid not in ai_agents:
            ai_agents[call_sid] = AI_SalesAgent()
        agent = ai_agents[call_sid]
        
        response_text, fillers, end_call = await agent.generate_response(speech_result)
        
        response = VoiceResponse()
        
        if end_call:
            response.say(response_text)
            response.hangup()
        else:
            gather = Gather(
                input='speech',
                action='/process_speech',
                method='POST',
                language='en-US',
                speechTimeout=1,
                timeout=5
            )
            if fillers:
                for filler in fillers:
                    gather.say(filler)
                    # Add a brief pause after each filler
                    gather.pause(length=0.3)
            
            # Add the main response
            gather.say(response_text)
            response.append(gather)
        return Response(content=str(response), media_type='text/xml')
            
    except Exception as e:
        logger.error(f"Error processing speech: {str(e)}")  # Log the error
        response = VoiceResponse()
        response.say("I apologize, but I'm having trouble. Could you please repeat that?")
        response.redirect('/twilio/voice')
        return Response(content=str(response), media_type='text/xml')

@router.post("/upload_knowledge")
async def upload_knowledge(file: UploadFile = File(...)):
    try:
        content = await file.read()
        pdf_processor = PDFProcessor()
        
        pdf_text = pdf_processor.extract_text_from_pdf(content)
        if not pdf_text:
            return JSONResponse(
                {"status": "error", "message": "Failed to extract text from PDF"},
                status_code=400
            )
        
        chunks = pdf_processor.process_text_for_rag(pdf_text)
        
        for agent in ai_agents.values():
            agent.documents = chunks
            agent.embeddings = agent.encoder.encode(chunks)
            agent.sources = [file.filename] * len(chunks)
            agent.page_numbers = [1] * len(chunks)
        
        return JSONResponse({
            "status": "success",
            "chunks_processed": len(chunks)
        })
        
    except Exception as e:
        logger.error(f"Error uploading knowledge: {str(e)}")  # Log the error
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )

@router.post("/make_call")
async def make_outbound_call(request: Request):
    try:
        data = await request.json()
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return JSONResponse({
                "status": "error",
                "message": "Phone number is required"
            })

        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Your ngrok URL
        ngrok_url = settings.NGROK_URL
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Make the call
        call = twilio_client.calls.create(
            to=phone_number,
            from_=settings.TWILIO_FROM_NUMBER,
            url=f"{ngrok_url}/twilio/voice",  # This will trigger the initial greeting
            status_callback_event=['completed', 'failed']
        )
        
        # Update the status_callback after the call is created
        call = twilio_client.calls(call.sid).update(
            status_callback=f"{ngrok_url}/twilio/status/{call.sid}"
        )
        return JSONResponse({
            "status": "success",
            "call_sid": call.sid
        })
    except Exception as e:
        logger.error(f"Error making outbound call: {str(e)}")  # Log the error
        return JSONResponse({
            "status": "error",
            "message": str(e)
        })
        
@router.get("/twilio/status/{call_sid}")
async def get_call_status(call_sid: str):
    try:
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        call = twilio_client.calls(call_sid).fetch()
        
        # Map Twilio status to our status
        status_mapping = {
            'completed': 'completed',
            'failed': 'failed',
            'busy': 'failed',
            'no-answer': 'failed',
            'canceled': 'failed',
            'in-progress': 'active',
            'queued': 'initiating',
            'ringing': 'initiating'
        }
        
        mapped_status = status_mapping.get(call.status, 'active')
        
        return JSONResponse({
            "status": mapped_status,
            "twilio_status": call.status,
            "duration": getattr(call, 'duration', 0)
        })
    except Exception as e:
        logger.error(f"Error fetching call status: {str(e)}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)