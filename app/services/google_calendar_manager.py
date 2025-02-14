from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta
from ..config import settings
from google_auth_oauthlib.flow import InstalledAppFlow

class GoogleCalendarManager:
    def __init__(self):
        self.creds = None
        self.initialize_credentials()

    def initialize_credentials(self):
        self.creds = Credentials.from_authorized_user_info(
            {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN")
            },
            settings.SCOPES
        )

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                raise Exception("Invalid credentials or refresh token.")

    def create_calendar_event(self, entities):
        try:
            if not entities.get('meeting_date') or not entities.get('meeting_time'):
                return {"success": False, "error": "Missing meeting date or time"}

            service = build('calendar', 'v3', credentials=self.creds)
            date_str = entities['meeting_date']
            time_str = entities['meeting_time']

            try:
                start_datetime = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
            except ValueError:
                try:
                    start_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                except ValueError:
                    return {"success": False, "error": "Invalid date/time format"}

            event = {
                'summary': f"Sales Consultation - {entities.get('company_name', 'Potential Client')}",
                'description': f"Client Details:\nName: {entities.get('name', 'N/A')}\nEmail: {entities.get('email', 'N/A')}",
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'end': {
                    'dateTime': (start_datetime + timedelta(hours=1)).isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'attendees': [
                    {'email': entities.get('email')} if entities.get('email') else None
                ],
                'reminders': {
                    'useDefault': True
                }
            }

            event['attendees'] = [a for a in event['attendees'] if a is not None]
            created_event = service.events().insert(calendarId='primary', body=event).execute()

            return {
                "success": True,
                "event_link": created_event.get('htmlLink'),
                "event_id": created_event.get('id')
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def generate_refresh_token(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": settings.GOOGLE_REFRESH_TOKEN
            },
            scopes=self.SCOPES
        )

        creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

        return {
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "scopes": creds.scopes
        } 