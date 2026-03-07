from datetime import datetime
from backend.extensions import db
from backend.models.models import Waitlist
from backend.services.notifications import notify_waitlist_open

def svc_join_waitlist(user_id, business_id, service_id):
    """Adds a user to the waitlist for a specific service."""
    existing = Waitlist.query.filter_by(
        user_id=user_id, 
        business_id=business_id, 
        service_id=service_id, 
        notified=False
    ).first()
    
    if not existing:
        entry = Waitlist(
            user_id=user_id, 
            business_id=business_id, 
            service_id=service_id, 
            request_date=datetime.now()
        )
        db.session.add(entry)
        db.session.commit()
        return True
    return False

def handle_cancellation(business_id, service_id):
    """Finds and notifies users when a slot opens up."""
    entries = Waitlist.query.filter_by(
        business_id=business_id, 
        service_id=service_id, 
        notified=False
    ).order_by(Waitlist.request_date.asc()).all()
    
    for entry in entries:
        notify_waitlist_open(entry)
        entry.notified = True
        
    db.session.commit()
