from flask import Flask
from flask_cors import CORS
from backend.config import Config
from backend.extensions import db, bcrypt, login_manager, limiter, migrate
from flask_talisman import Talisman

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    app.config.from_object(config_class)

    # CORS — scoped to /api/* for Vercel frontend
    cors_origins = app.config.get('CORS_ORIGINS', '*')
    CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)

    # Security Headers
    Talisman(app, content_security_policy=None, force_https=app.config.get('TALISMAN_FORCE_HTTPS', True)) # Start with base headers, CSP tuned later

    from backend.services.firebase_config import init_firebase
    init_firebase()

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Import and register blueprints
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
    
    @app.context_processor
    def inject_config():
        is_firebase_enabled = bool(app.config.get('FIREBASE_API_KEY') and 
                                 app.config.get('FIREBASE_API_KEY') != 'None' and
                                 app.config.get('FIREBASE_API_KEY') != '')
        return dict(config=app.config, is_firebase_enabled=is_firebase_enabled)

    # Register custom CLI commands
    from backend.commands import register_commands
    register_commands(app)

    with app.app_context():
        db.create_all()
        # Initialize default categories
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

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
