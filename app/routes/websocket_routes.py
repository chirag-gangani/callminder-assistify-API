from fastapi import APIRouter, WebSocket
import json
import base64
import io
from ..services.ai_agent import AI_SalesAgent

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except Exception:
        pass

@router.websocket("/twilio/stream")
async def handle_twilio_stream(websocket: WebSocket):
    await websocket.accept()
    
    try:
        agent = AI_SalesAgent()
        greeting = "Hello! I'm calling from our company. How can I help you today?"
        await websocket.send_text(json.dumps({"event": "start", "text": greeting}))
        
        audio_buffer = io.BytesIO()
        
        while True:
            message = await websocket.receive_text()
            message_data = json.loads(message)
            
            if message_data["event"] == "start":
                continue
            
            if message_data["event"] == "media":
                audio_data = base64.b64decode(message_data["media"]["payload"])
                audio_buffer.write(audio_data)
                
                if audio_buffer.tell() > 8000:
                    audio_buffer.seek(0)
                    audio_chunk = audio_buffer.read()
                    audio_buffer = io.BytesIO()
                    
                    text = await agent.process_audio_to_text(audio_chunk)
                    
                    if text:
                        response_text, _, end_call = await agent.generate_response(text)
                        await websocket.send_text(json.dumps({"event": "media", "text": response_text}))
                        
                        if end_call:
                            await websocket.close()
                            break
                    
    except Exception:
        pass