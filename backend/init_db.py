import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.extensions import db
from backend.models.models import User, Business, Service, Staff, Appointment, Resource, Waitlist

app = create_app()

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables from scratch...")
    db.create_all()
    print("Database initialized successfully with the latest schema!")
