import os
import logging
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_12345')
    DEFAULT_STAFF_PASSWORD = os.environ.get('DEFAULT_STAFF_PASSWORD', 'staffpassword_secure_default')
    
    # Database
    basedir = os.path.abspath(os.path.dirname(__file__))
    _db_url = os.environ.get('DATABASE_URL')
    
    if not _db_url:
        # On Vercel, the root filesystem is read-only. Use /tmp for SQLite fallback.
        if os.environ.get('VERCEL'):
            _db_url = "sqlite:////tmp/app.db"
        else:
            _db_url = f"sqlite:///{os.path.join(basedir, '../database/app.db')}"
            
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CORS (for separate Vercel frontend)
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    # HTTPS enforcement (Talisman)
    TALISMAN_FORCE_HTTPS = os.environ.get('TALISMAN_FORCE_HTTPS', 'True').lower() == 'true'

    # Base URL for absolute links (Payments, WhatsApp, etc)
    BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
    
    # Bypass configuration validation for emergency troubleshooting
    BYPASS_CONFIG_VALIDATION = os.environ.get('BYPASS_CONFIG_VALIDATION', 'False').lower() == 'true'
    
    # Authentication
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    
    # Razorpay
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'test_key_id')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'test_key_secret')
    
    # Google Calendar
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

    # Twilio (WhatsApp/SMS)
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
    
    # Google OAuth
    GOOGLE_OAUTH_REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    
    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 86400))  # 24 hours in seconds
    
    # Frontend
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://management-one-gilt.vercel.app")

    # AI (Gemini)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # AI Engine Config
    AI_SLOT_THRESHOLD = 5 # Number of recommendations
    AI_CONFLICT_RADIUS_MINS = 5 # Safety margin

    # Firebase
    FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY')
    FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN')
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID')
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
    FIREBASE_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_MESSAGING_SENDER_ID')
    FIREBASE_APP_ID = os.environ.get('FIREBASE_APP_ID')

    # Production Monitoring & Rate Limiting
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    REDIS_URL = os.environ.get('REDIS_URL')
