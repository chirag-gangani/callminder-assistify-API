from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.services.google_calendar_manager import GoogleCalendarManager

router = APIRouter()

@router.get("/oauthcallback")
async def oauth_callback(request: Request):
    calendar_manager = GoogleCalendarManager()
    refresh_token = calendar_manager.generate_refresh_token()

    if refresh_token:
        return {"refresh_token": refresh_token}
    else:
        raise HTTPException(status_code=400, detail="Failed to retrieve refresh token") 