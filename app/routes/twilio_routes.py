from fastapi import APIRouter, Request, File, UploadFile, HTTPException
from fastapi.responses import Response, JSONResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from ..services.ai_agent import AI_SalesAgent, ai_agents
from ..services.pdf_processor import PDFProcessor
from twilio.rest import Client
from ..config import settings  # Ensure you have a config file to load environment variables
import logging  # Import logging
from pydantic import BaseModel
import asyncio

server_URL = settings.NGROK_URL  # Ensure you have a config file to load environment variables

# Set up logging
logger = logging.getLogger(__name__)  # Initialize the logger

# Suppress Twilio INFO logs
twilio_logger = logging.getLogger('twilio')
twilio_logger.setLevel(logging.WARNING)  # Set to WARNING to suppress INFO logs

# Suppress other INFO logs
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

router = APIRouter()

caller_names = {}

class SummaryResponse(BaseModel):
    summary: str
    status: str = "success"

@router.post("/twilio/voice")  # Changed from GET to POST as Twilio makes POST requests
async def handle_incoming_call(request: Request):
    try:
        # Get form data instead of query parameters as Twilio sends POST data
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        user_name = caller_names.get(call_sid, '')
        
        response = VoiceResponse()
        gather = Gather(
            input='speech',
            action='/process_speech',
            method='POST',
            language='en-US',
            speechTimeout=1,
            timeout=5
        )
        # Include the user's name in the greeting if available
        greeting = f"Hello!{f' {user_name}' if user_name else ''} I'm calling from Toshal Infotech. Is this a good time to talk?"
        gather.say(f'<speak><prosody rate="100%" pitch="+2st" volume="soft">{greeting}</prosody></speak>', ssml=True)
        response.append(gather)
        return Response(content=str(response), media_type='text/xml')
    except Exception as e:
        logger.error(f"Error in handle_incoming_call: {str(e)}")
        # Provide a fallback response in case of error
        response = VoiceResponse()
        response.say("Hello! I'm calling from Toshal Infotech. Is this a good time to talk?")
        return Response(content=str(response), media_type='text/xml')


@router.post("/process_speech")
async def process_speech(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        speech_result = form_data.get('SpeechResult', '')
        
        # Add print message for user input
        print(f"User input received:\n {speech_result}")  # Print user input
        
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
            gather.say(f'<speak><prosody rate="100%" pitch="+2st" volume="loud">{response_text}</prosody></speak>', ssml=True)
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
        name = data.get('name')
        
        if not phone_number:
            return JSONResponse({
                "status": "error",
                "message": "Phone number is required"
            })

        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        ngrok_url = settings.NGROK_URL
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Make the initial call
        call = twilio_client.calls.create(
            to=phone_number,
            from_=settings.TWILIO_FROM_NUMBER,
            url=f"{ngrok_url}/twilio/voice",  # Initial URL
            status_callback=f"{ngrok_url}/call_ends",  # Updated: removed path parameter
            status_callback_event=['completed', 'failed']
        )
        
        # Store the name with the call_sid
        global caller_names
        caller_names[call.sid] = name
        logger.info(f"Stored name {name} for call {call.sid}")
        
        # Set the status callback
        call = twilio_client.calls(call.sid).update(
            status_callback=f"{ngrok_url}/call_ends" # Updated: removed path parameter
        )
        
        return JSONResponse({
            "status": "success",
            "call_sid": call.sid
        })
    except Exception as e:
        logger.error(f"Error making outbound call: {str(e)}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        })

@router.get("/twilio/status/{call_sid}")
async def handle_call_status(call_sid: str, request: Request):
    try:
        form_data = await request.form()
        call_status = form_data.get('CallStatus')
        
        if call_status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
            # Clean up the caller_names dictionary
            global caller_names
            if call_sid in caller_names:
                del caller_names[call_sid]
                logger.info(f"Cleaned up name for call {call_sid}")
        
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
        
        mapped_status = status_mapping.get(call.status, 'failed')
        
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

@router.post("/call_ends")
@router.get("/call_ends/{call_sid}", response_model=SummaryResponse)
async def call_ends(request: Request = None, call_sid: str = None):
    """
    Endpoint to handle call end events and generate a summary.
    Supports both POST (from Twilio callbacks) and GET (with explicit call_sid) methods.
    """
    print("**********************")
    print("Call Ends Successfully")
    print("**********************")
    
    try:
        # Handle POST request from Twilio callback
        if request and not call_sid:
            form_data = await request.form()
            call_sid = form_data.get('CallSid')
            
            if not call_sid:
                logger.error("No CallSid provided in the request")
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "summary": "No CallSid provided in the request"
                    }
                )
                
        # Check if we have an agent for this call_sid
        if call_sid not in ai_agents:
            logger.warning(f"No active conversation found for Call SID: {call_sid}")
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "summary": "No active conversation found for the provided Call SID"
                }
            )

        agent = ai_agents[call_sid]
        await agent.print_summary()

        try:
            # Check for required entities and ensure they are not null
            required_entities = ['name', 'email', 'company_name', 'meeting_date', 'meeting_time']
            if all(agent.client_entities.get(entity) for entity in required_entities):
                # Sanitize email before creating calendar event and Salesforce lead
                sanitized_email = agent.sanitize_email(agent.client_entities.get('email', ''))
                if sanitized_email:
                    agent.client_entities['email'] = sanitized_email
                    
                    # Log the client entities before creating the lead
                    logger.info(f"Creating lead with the following client entities: {agent.client_entities}")

                    # Create Google Calendar event and Salesforce lead concurrently
                    calendar_task = asyncio.create_task(agent.calendar_manager.create_calendar_event(agent.client_entities))
                    salesforce_task = asyncio.create_task(agent.salesforce_integration.create_lead(agent.client_entities))
                    await asyncio.gather(calendar_task, salesforce_task)

                    # Add print message after generating lead and event
                    print("Lead generated on Salesforce and calendar event created successfully.")
                    
                else:
                    logger.error("Invalid email address provided. Cannot create calendar event or Salesforce lead.")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "summary": "Invalid email address provided."
                        }
                    )
            else:
                missing_entities = [entity for entity in required_entities if not agent.client_entities.get(entity)]
                logger.warning(f"Required entities are missing or null: {missing_entities}. Client entities: {agent.client_entities}")
                print(f"Required entities are missing or null: {missing_entities}. Continuing with other processes.")
        except Exception as e:
            logger.error(f"Error creating lead or calendar event: {e}")
            print(f"Error creating lead or calendar event: {e}")
            
        # Generate the summary regardless of lead and event creation
        result = agent.get_latest_summary()
        print("<<<<<<<<<<<<<< Summary >>>>>>>>>>>>>>>>>>>\n", result)
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
    
@router.get("/config")
async def get_config(request: Request):
    return {
        "wsUrl": server_URL
    }

