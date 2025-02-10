import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    SMALLEST_API_KEY: str = os.getenv("SMALLEST_API_KEY")
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER")
    NGROK_URL: str = os.getenv("NGROK_URL")

    class Config:
        env_file = ".env"
        
print("NGROK URL--->>>>",os.getenv("NGROK_URL"))
settings = Settings()