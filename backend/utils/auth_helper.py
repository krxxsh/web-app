import logging
from functools import wraps
from flask import request, jsonify, g
from backend.services.firebase_config import verify_firebase_token
from backend.models.models import User
from backend.extensions import db

logger = logging.getLogger(__name__)

def firebase_token_required(f):
    """
    Decorator to verify Firebase ID Token in the Authorization header.
    Expects: Authorization: Bearer <token>
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"success": False, "message": "Missing or invalid Authorization header"}), 401
        
        id_token = auth_header.split('Bearer ')[1]
        decoded_token = verify_firebase_token(id_token)
        
        if not decoded_token:
            return jsonify({"success": False, "message": "Invalid or expired Firebase token (or Firebase SDK not initialized)"}), 401
        
        uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        
        # Link to local user
        user = User.query.filter_by(firebase_uid=uid).first()
        if not user:
            # Check by email to link legacy accounts
            user = User.query.filter_by(email=email).first()
            if user:
                user.firebase_uid = uid
                db.session.commit()
            else:
                # In a "Stateless" world, we might want to auto-create the user shell here
                # or require a separate registration step. For now, let's auto-create.
                from backend.extensions import bcrypt
                user = User(
                    firebase_uid=uid,
                    email=email,
                    username=email.split('@')[0],
                    password=bcrypt.generate_password_hash("firebase_managed").decode('utf-8'), # Dummy to satisfy NOT NULL constraint
                    role='pending',
                    is_verified=True
                )
                db.session.add(user)
                db.session.commit()
        
        # Set user in Flask-Login for the duration of the request
        from flask_login import login_user
        login_user(user)
        
        return f(*args, **kwargs)
    
    return decorated_function
