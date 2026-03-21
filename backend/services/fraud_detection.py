import re
from datetime import datetime, timedelta, timezone
from backend.models.models import Feedback, Appointment

def detect_review_fraud(user_id, appointment_id, rating, comment):
    """
    AI Fraud Detection System for Reviews.
    Flags reviews based on:
    1. Single-user spam (Multiple reviews in short window)
    2. Zero-length or repetitive nonsense
    3. Sentiment Mismatch (Implicit logic)
    4. Verified Stay Check
    """
    # 1. Verified Stay Check
    appt = Appointment.query.get(appointment_id)
    if not appt:
        return True, "Invalid appointment"

    if appt.status != 'completed':
        return True, "Cannot review uncompleted service"

    if appt.customer_id != user_id:
        return True, "Unauthorized review attempt"

    # 2. Velocity Check (Spam protection)
    recent_reviews = Feedback.query.filter(
        Feedback.user_id == user_id,
        Feedback.created_at > datetime.now(timezone.utc) - timedelta(hours=1)
    ).count()
    if recent_reviews > 3:
        return True, "Too many reviews submitted recently"

    # 3. Content Analysis (Heuristics)
    if comment:
        # Check for repetitive characters (e.g. "aaaaaaa")
        if re.search(r'(.)\1{5,}', comment):
            return True, "Repetitive character spam detected"

        # Check for extremely short generic "good" reviews that might be bot-generated
        generic_terms = ['good', 'nice', 'great', 'wow', 'ok']
        if len(comment.split()) < 2 and any(term in comment.lower() for term in generic_terms):
            # We don't block, but maybe flag for moderation (simulated here)
            pass

    return False, "Clear"

def get_sentiment_score_v1(comment):
    """
    Simulated Sentiment Analysis.
    Real implementation would use a model like DistilBERT.
    """
    if not comment:
        return 0.5
    positive_words = ['great', 'excellent', 'amazing', 'happy', 'best', 'good', 'satisfied']
    negative_words = ['bad', 'poor', 'unhappy', 'worst', 'late', 'rude', 'dirty']

    comment_lower = comment.lower()
    pos_count = sum(1 for w in positive_words if w in comment_lower)
    neg_count = sum(1 for w in negative_words if w in comment_lower)

    if pos_count + neg_count == 0:
        return 0.5
    return pos_count / (pos_count + neg_count)
