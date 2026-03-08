from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from flask import url_for, current_app
from backend.extensions import db
from backend.models.models import OAuthToken
import logging

logger = logging.getLogger(__name__)

# Scopes needed for Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_google_flow():
    """Builds the Google OAuth flow object."""
    # Note: client_secret.json should be provided in production
    client_config = {
        "web": {
            "client_id": current_app.config.get('GOOGLE_CLIENT_ID'),
            "project_id": "ai-sched",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": current_app.config.get('GOOGLE_CLIENT_SECRET'),
            "redirect_uris": [url_for('api.google_callback', _external=True)]
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES)

def save_google_token(user_id, credentials):
    """Saves or updates the Google token for a user."""
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    existing = OAuthToken.query.filter_by(user_id=user_id, provider='google').first()
    if existing:
        existing.token_json = token_data
    else:
        new_token = OAuthToken(user_id=user_id, provider='google', token_json=token_data)
        db.session.add(new_token)

    db.session.commit()

def get_calendar_service(user_id):
    """Builds the Google Calendar API service instance."""
    token_record = OAuthToken.query.filter_by(user_id=user_id, provider='google').first()
    if not token_record:
        return None

    creds = Credentials.from_authorized_user_info(token_record.token_json, SCOPES)
    return build('calendar', 'v3', credentials=creds)

def sync_appointment_to_google(appointment):
    """Creates a Google Calendar event for a specific appointment."""
    # We sync to the business owner's or staff member's calendar
    provider_id = appointment.staff.user_id if appointment.staff and appointment.staff.user_id else appointment.business.owner_id

    service = get_calendar_service(provider_id)
    if not service:
        return None

    event = {
        'summary': f'Booking: {appointment.service.name} ({appointment.customer.username})',
        'location': appointment.business.name,
        'description': f'Service booked via AI Sched. Status: {appointment.status}',
        'start': {
            'dateTime': appointment.start_time.isoformat() + 'Z',
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': appointment.end_time.isoformat() + 'Z',
            'timeZone': 'UTC',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 60},
            ],
        },
    }

    try:
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        appointment.google_event_id = created_event['id']
        db.session.commit()
        return created_event['id']
    except Exception as e:
        logger.error(f"Failed to sync to Google Calendar: {e}")
        return None
