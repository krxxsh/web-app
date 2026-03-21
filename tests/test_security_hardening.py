import pytest
from datetime import datetime, timezone, timedelta
from backend.models.models import User
from backend.extensions import db

def test_password_reset_disabled(client, app):
    """Test that legacy password forgot/reset routes are disabled and point to Firebase."""
    response = client.post('/forgot-password', json={'email': 'test@example.com'})
    assert response.status_code == 400
    assert b"Please use the Firebase reset flow" in response.data

    response = client.post('/reset-password', json={
        'email': 'expire@example.com',
        'otp': '123456',
        'password': 'NewSecurePassword123!'
    })
    assert response.status_code == 400
    assert b"Please use the Firebase reset flow" in response.data
