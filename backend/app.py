from flask import Flask
from backend.config import Config
from backend.extensions import db, bcrypt, login_manager

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Import and register blueprints
    from backend.routes.auth import auth_bp
    from backend.routes.main import main_bp
    from backend.routes.admin import admin_bp
    from backend.routes.api import api_bp
    from backend.routes.staff import staff_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(staff_bp)

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
