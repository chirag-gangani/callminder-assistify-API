import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import ClassVar

load_dotenv()

class Settings(BaseSettings):
    NGROK_URL: str = os.getenv("NGROK_URL")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    SMALLEST_API_KEY: str = os.getenv("SMALLEST_API_KEY")
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER")
    SALESFORCE_USERNAME: str = os.getenv("SALESFORCE_USERNAME")
    SALESFORCE_PASSWORD: str = os.getenv("SALESFORCE_PASSWORD")
    SALESFORCE_SECURITY: str = os.getenv("SALESFORCE_SECURITY")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_REFRESH_TOKEN: str = os.getenv("GOOGLE_REFRESH_TOKEN")
    SCOPES: ClassVar[list] = ['https://www.googleapis.com/auth/calendar']

    class Config:
        env_file = ".env"

settings = Settings()
print("NGROK URL >>>>>>>>>>>>>>>>> ", settings.NGROK_URL)