import firebase_admin
from firebase_admin import credentials, auth
import os
import logging
import json

logger = logging.getLogger(__name__)

def init_firebase():
    """Initialize Firebase Admin SDK using service account or environment variables."""
    # Check if a default app already exists to avoid ValueError
    if len(firebase_admin._apps) > 0:
        return

    # Priority 1: FIREBASE_SERVICE_ACCOUNT environment variable (Best for Cloud/Vercel)
    firebase_service_account = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if firebase_service_account:
        try:
            # Parse the JSON string
            cred_dict = json.loads(firebase_service_account)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized via FIREBASE_SERVICE_ACCOUNT environment variable")
            return
        except Exception as e:
            logger.error(f"Failed to initialize Firebase via env var: {e}")

    # Priority 2: Service Account JSON file in root directory 
    path_to_json = os.path.join(os.path.dirname(__file__), '..', '..', 'serviceAccountKey.json')

    if os.path.exists(path_to_json):
        cred = credentials.Certificate(path_to_json)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized via serviceAccountKey.json")
    # Priority 3: Google Application Credentials environment variable
    elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        firebase_admin.initialize_app()
        logger.info("Firebase initialized via GOOGLE_APPLICATION_CREDENTIALS")
    else:
        # Priority 4: Mock/Simulation mode for development if no creds found
        logger.warning("No Firebase credentials found. Running in simulation mode.")

def verify_firebase_token(id_token):
    """Verifies a Firebase ID token and returns the decoded claims."""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.error(f"Firebase Token Verification Error: {e}")
        return None

def create_firebase_user(email, password, display_name):
    """Creates a new user in Firebase."""
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name
        )
        return user
    except Exception as e:
        logger.error(f"Firebase User Creation Error: {e}")
        return None
