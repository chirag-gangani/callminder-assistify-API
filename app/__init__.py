from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .routes import call_routes, twilio_routes, websocket_routes
from .logging_config import setup_logging

def create_app() -> FastAPI:
    app = FastAPI()
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Include routers
    app.include_router(call_routes.router)
    app.include_router(twilio_routes.router)
    app.include_router(websocket_routes.router)
    
    # Setup logging
    setup_logging()
    
    return app