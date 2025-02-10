from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ..services.ai_agent import AI_SalesAgent
from ..config import settings
from twilio.rest import Client

router = APIRouter()
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

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
        
        call = twilio_client.calls.create(
            to=phone_number,
            from_=settings.TWILIO_FROM_NUMBER,
            url=f"{settings.NGROK_URL}/twilio/voice",
            status_callback=f"{settings.NGROK_URL}/twilio/status",
            status_callback_event=['completed', 'failed']
        )
        
        return JSONResponse({
            "status": "success",
            "call_sid": call.sid
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        })

@router.get("/some-endpoint")
async def some_function():
    agent = AI_SalesAgent()
    response = await agent.generate_response()
    return JSONResponse({"status": "success", "response": response})