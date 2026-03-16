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

    # AI (Gemini)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Mail
    MAIL_SERVER = 'smtp.sendgrid.net'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'apikey'
    MAIL_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'notifications@ai-sched.com')
    
    @staticmethod
    def validate():
        """Validates critical infrastructure configurations."""
        is_prod = os.environ.get('VERCEL') == '1' or os.environ.get('FLASK_ENV') == 'production'
        if is_prod:
            missing = []
            if not os.environ.get('SENDGRID_API_KEY'):
                missing.append('SENDGRID_API_KEY')
            
            if missing:
                error_msg = f"Critical environment variables missing: {', '.join(missing)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            if not os.environ.get('MAIL_DEFAULT_SENDER'):
                logger.warning("PROD WARNING: MAIL_DEFAULT_SENDER is missing. Using fallback.")
    
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
