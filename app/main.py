from . import create_app
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from .config import settings
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
import logging
from fastapi.middleware.cors import CORSMiddleware
from app.routes.twilio_routes import router as twilio_router
import asyncio
from app.services.ai_agent import AI_SalesAgent
from app.routes.google_auth import router as google_auth_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sentence_transformer_model = None
openai_client = None

app.include_router(twilio_router)
app.include_router(google_auth_router)

ai_sales_agent = AI_SalesAgent()

def load_sentence_transformer():
    global sentence_transformer_model
    try:
        sentence_transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        pass

@app.on_event("startup")
async def startup_event():
    global openai_client
    try:
        load_sentence_transformer()
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        pass

@app.on_event("shutdown")
async def shutdown_event():
    pass

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("static/index.html") as f:
            return f.read()
    except Exception as e:
        return HTMLResponse(content="Error loading page", status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass
