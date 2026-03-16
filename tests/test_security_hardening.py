import pytest
from datetime import datetime, timezone, timedelta
from backend.models.models import User
from backend.extensions import db

def test_password_reset_rate_limiting(client, app):
    """Test that OTP requests are rate limited to 60 seconds."""
    with app.app_context():
        user = User(
            username="testuser",
            email="test@example.com",
            password="hashed_password",
            otp_created_at=datetime.now(timezone.utc) - timedelta(seconds=30)
        )
        db.session.add(user)
        db.session.commit()
        
        response = client.post('/forgot-password', json={'email': 'test@example.com'})
        assert response.status_code == 429
        assert b"Please wait before requesting another OTP" in response.data

def test_password_reset_otp_expiration(client, app):
    """Test that expired OTPs (10m) are rejected during reset."""
    with app.app_context():
        user = User(
            username="expireuser",
            email="expire@example.com",
            password="old_password_hash",
            email_otp="123456",
            otp_created_at=datetime.now(timezone.utc) - timedelta(minutes=11)
        )
        db.session.add(user)
        db.session.commit()
        
        response = client.post('/reset-password', json={
            'email': 'expire@example.com',
            'otp': '123456',
            'password': 'NewSecurePassword123!'
        })
        assert response.status_code == 400
        assert b"OTP expired" in response.data

def test_password_reset_success(client, app):
    """Test successful password reset with valid OTP."""
    # Use patch instead of mocker to avoid extra dependencies
    from unittest.mock import patch
    with patch('backend.routes.auth.send_password_reset_otp', return_value=True):
        with app.app_context():
            user = User(
                username="successuser",
                email="success@example.com",
                password="old_password_hash",
                email_otp="654321",
                otp_created_at=datetime.now(timezone.utc)
            )
            db.session.add(user)
            db.session.commit()
            
            response = client.post('/reset-password', json={
                'email': 'success@example.com',
                'otp': '654321',
                'password': 'NewSecurePassword123!'
            })
            assert response.status_code == 200
            assert b"Password reset successful" in response.data
            
            # Verify password was updated
            updated_user = User.query.filter_by(email='success@example.com').first()
            from backend.extensions import bcrypt
            assert bcrypt.check_password_hash(updated_user.password, 'NewSecurePassword123!')
            assert updated_user.email_otp is None
