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
from app.services.ai_agent import AI_SalesAgent  # Import the AI_SalesAgent class

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Allow CORS for Ngrok URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the model at the module level
sentence_transformer_model = None
openai_client = None

# Include the router
app.include_router(twilio_router)

# Create a global instance of AI_SalesAgent
ai_sales_agent = AI_SalesAgent()

def load_sentence_transformer():
    global sentence_transformer_model
    try:
        # Removed logging for loading SentenceTransformer model
        sentence_transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
        # Removed logging for SentenceTransformer model loading success
    except Exception as e:
        # Removed logging for SentenceTransformer model loading error
        pass

@app.on_event("startup")
async def startup_event():
    global openai_client
    try:
        # Removed logging for startup process
        # Load the SentenceTransformer model in a separate thread
        load_sentence_transformer()
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    except Exception as e:
        # Removed logging for startup errors
        pass

@app.on_event("shutdown")
async def shutdown_event():
    # Removed logging for shutdown process
    pass

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("static/index.html") as f:  # Ensure the path is correct
            return f.read()
    except Exception as e:
        # Removed logging for reading index.html errors
        return HTMLResponse(content="Error loading page", status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Removed logging for WebSocket connection acceptance
    try:
        while True:
            data = await websocket.receive_text()
            # Log only the message received for OpenAI response generation
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        # Removed logging for WebSocket disconnection
        pass
    except Exception as e:
        # Removed logging for WebSocket handler errors
        pass
