from flask import request
from backend.models.models import AdminActivityLog
from backend.extensions import db
from datetime import datetime, timezone

def log_admin_action(user_id, action, business_id=None, details=None):
    """
    Persists an administrative action to the audit log.
    """
    log = AdminActivityLog(
        user_id=user_id,
        business_id=business_id,
        action=action,
        details=details or {},
        ip_address=request.remote_addr,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(log)
    db.session.commit()
