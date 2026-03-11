import os
import pytest
from unittest.mock import patch

# Set environment variables BEFORE importing the app to avoid loading production config
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test_secret'
os.environ['FIREBASE_API_KEY'] = 'fake'
os.environ['FIREBASE_AUTH_DOMAIN'] = 'fake'
os.environ['FIREBASE_PROJECT_ID'] = 'fake'
os.environ['FIREBASE_STORAGE_BUCKET'] = 'fake'
os.environ['FIREBASE_MESSAGING_SENDER_ID'] = 'fake'
os.environ['FIREBASE_APP_ID'] = 'fake'

from backend.app import create_app
from backend.extensions import db

@pytest.fixture
def app():
    # Mock firebase initialization to avoid external calls
    with patch('backend.services.firebase_config.init_firebase'):
        app = create_app()
        app.config.update({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TALISMAN_FORCE_HTTPS": False
        })

        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
