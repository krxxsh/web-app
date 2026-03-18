import logging
import traceback
import sys

# Configure logging to stdout for Vercel
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from flask import Flask, jsonify
from flask_cors import CORS
from backend.config import Config
from backend.extensions import db, bcrypt, login_manager, limiter, migrate
from flask_talisman import Talisman
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

# Initialize Sentry
sentry_dsn = Config.SENTRY_DSN if hasattr(Config, 'SENTRY_DSN') else None
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    app.config.from_object(config_class)
    
    # app.config.from_object(config_class) # Line 35 above

    # CORS — scoped to /api/* for Vercel frontend
    cors_origins = app.config.get('CORS_ORIGINS', '*')
    frontend_url = app.config.get("FRONTEND_URL", "*")
    cors_origins_list = [frontend_url] if frontend_url != "*" else "*"
    CORS(app, resources={r"/api/*": {"origins": cors_origins_list}, r"/auth/*": {"origins": cors_origins_list}}, supports_credentials=False)

    # Security Headers - Comprehensive CSP
    csp = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            'https://cdn.jsdelivr.net',
            'https://www.gstatic.com',
            'https://apis.google.com',
            'https://accounts.google.com',
            'https://checkout.razorpay.com',
            'https://cdnjs.cloudflare.com'
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'font-src': [
            "'self'",
            'https://fonts.gstatic.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'img-src': [
            "'self'",
            'data:',
            'https://*.googleapis.com',
            'https://*.gstatic.com',
            'https://*.googleusercontent.com'
        ],
        'connect-src': [
            "'self'",
            'https://*.vercel.app',
            'https://*.render.com',
            'https://*.sentry.io',
            'https://*.google-analytics.com',
            'https://*.googleapis.com',
            'https://*.firebaseio.com',
            'https://*.firebaseapp.com',
            'https://identitytoolkit.googleapis.com'
        ],
        'frame-src': [
            "'self'",
            'https://api.razorpay.com',
            'https://accounts.google.com',
            'https://*.firebaseapp.com'
        ]
    }
    
    Talisman(app, 
             content_security_policy=csp, 
             force_https=app.config.get('TALISMAN_FORCE_HTTPS', not app.debug),
             strict_transport_security=not app.debug,
             session_cookie_secure=not app.debug,
             content_security_policy_nonce_in=['script-src'])

    @app.route("/api/ping")
    def ping():
        return jsonify({"status": "ok", "message": "Backend is alive"}), 200

    @app.route("/api/debug-env")
    def debug_env():
        return jsonify({
            "database_url_configured": bool(app.config.get('SQLALCHEMY_DATABASE_URI')),
            "firebase_configured": bool(app.config.get('FIREBASE_API_KEY')),
            "firebase_project_id": app.config.get('FIREBASE_PROJECT_ID'),
            "is_vercel": os.environ.get('VERCEL') == '1',
            "python_version": sys.version
        }), 200

    try:
        from backend.services.firebase_config import init_firebase
        init_firebase()
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Import and register blueprints
    try:
        from backend.routes.auth import auth_bp
        from backend.routes.main import main_bp
        from backend.routes.admin import admin_bp
        from backend.routes.api import api_bp
        from backend.routes.staff import staff_bp
        from backend.routes.explore import explore_bp
        from backend.routes.emergency import emergency_bp
        from backend.routes.verify import verify_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        app.register_blueprint(verify_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(api_bp, url_prefix='/api')
        app.register_blueprint(staff_bp)
        app.register_blueprint(explore_bp)
        app.register_blueprint(emergency_bp)

        from flask_login import current_user
        from flask import redirect, request

        @app.before_request
        def check_role_selection():
            # Paths allowed without role selection
            OPEN_PATHS = {
                '/select-role',
                '/logout',
                '/login',
                '/register',
                '/admin/login',
                '/forgot-password',
                '/reset-password',
                '/dev-login',
                '/dev-register',
            }
            path = request.path

            # Allow static assets, open paths, and all /api/* calls
            if (path.startswith('/static') or
                    path.startswith('/api/') or
                    path in OPEN_PATHS):
                return

            if current_user.is_authenticated and current_user.role == 'pending':
                return redirect('/select-role')
    except Exception as e:
        logger.error(f"Failed to register blueprints: {e}")
        logger.error(traceback.format_exc())

    @app.context_processor
    def inject_config():
        is_firebase_enabled = bool(app.config.get('FIREBASE_API_KEY') and 
                                 app.config.get('FIREBASE_API_KEY') != 'None' and
                                 app.config.get('FIREBASE_API_KEY') != '')
        return dict(config=app.config, is_firebase_enabled=is_firebase_enabled)

    # Register custom CLI commands
    from backend.commands import register_commands
    register_commands(app)

    # DB initialization logic wrapped in try-except

    try:
        with app.app_context():
            logger.info("Running database initialization...")
            db.create_all()
            from backend.models.models import BusinessCategory
            if not BusinessCategory.query.first():
                defaults = [
                    ('Health', '🏥', True),
                    ('Salon', '✂️', False),
                    ('Legal', '⚖️', False),
                    ('Auto', '🚗', False),
                    ('Education', '🎓', False)
                ]
                for name, icon, is_health in defaults:
                    cat = BusinessCategory(name=name, icon=icon, is_health_related=is_health)
                    db.session.add(cat)
                db.session.commit()
                logger.info("Default categories seeded.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error(traceback.format_exc())

    return app

try:
    app = create_app()
except Exception as e:
    import traceback
    error_text = str(e)
    error_tb = traceback.format_exc()
    logger.error(f"Application creation failed: {error_text}")
    logger.error(error_tb)
    # Fallback app for diagnostics if main one fails
    app = Flask(__name__)
    @app.route("/", defaults={'path': ''})
    @app.route("/<path:path>")
    def error_page(path):
        error_msg = f"CRITICAL_STARTUP_ERROR: {path}<br><br>Exception: {error_text}<br><pre>{error_tb}</pre>"
        return error_msg, 500

if __name__ == '__main__':
    app.run(debug=True)
