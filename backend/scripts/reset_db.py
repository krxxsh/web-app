import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.extensions import db
from backend.models.models import BusinessCategory

def reset_database():
    app = create_app()
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Recreating all tables...")
        db.create_all()

        # Initialize default categories (mirroring app.py setup but ensuring it runs)
        print("Initializing default categories...")
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
        print("Database reset successfully.")

if __name__ == "__main__":
    reset_database()
