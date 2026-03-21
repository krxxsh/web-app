from flask import current_app
import google.generativeai as genai
import os
import logging
from datetime import datetime, timedelta
from backend.models.models import Appointment, Business

logger = logging.getLogger(__name__)

def get_genai_model():
    api_key = current_app.config.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "MOCK_KEY")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

def analyze_sentiment(text):
    """
    Analyzes feedback text and returns structured sentiment data.
    """
    if not text:
        return {"sentiment": "neutral", "key_issues": []}

    prompt = f"""
    Analyze the following customer feedback for a service business.
    Return only a JSON object with:
    - sentiment: (positive, negative, neutral)
    - score: (0 to 1)
    - key_issues: (list of issues like 'wait time', 'cleanliness', 'price', etc.)
    - user_reflection: (a short personalized thank-you message based on their mood)

    Feedback: "{text}"
    """

    try:
        if os.environ.get("GEMINI_API_KEY") == "MOCK_KEY":
             return {"sentiment": "positive", "score": 0.9, "key_issues": [], "user_reflection": "Thanks for your kind words!"}

        response = get_genai_model().generate_content(prompt)
        # Placeholder for real parsing logic (assuming strong JSON output from Flash)
        import json
        return json.loads(response.text.replace('```json', '').replace('```', ''))
    except Exception as e:
        logger.error(f"AI Sentiment Error: {e}")
        return {"sentiment": "neutral", "score": 0.5, "key_issues": [], "user_reflection": "Thank you for your feedback!"}

def predict_wait_time(business_id):
    """
    Calculates dynamic wait time based on current arrived vs booked appointments.
    """
    business = Business.query.get(business_id)
    if not business:
        return 0

    now = datetime.now()
    # Find active sessions (arrived but not yet finished)
    active = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.status == 'arrived',
        Appointment.start_time <= now,
        Appointment.end_time >= now - timedelta(minutes=60) # roughly within last hour
    ).count()

    # Base wait from metadata + congestion factor
    base_wait = business.typical_wait_time or 15
    congestion = active * 5 # 5 mins per active customer

    return base_wait + congestion

def get_smart_recommendations(user_id, business_id=None):
    """
    Suggests services based on user history and time of day.
    """
    # Simple logic: Most booked service historically
    history = Appointment.query.filter_by(customer_id=user_id).all()
    if not history:
        return []

    counts = {}
    for a in history:
        counts[a.service_id] = counts.get(a.service_id, 0) + 1

    sorted_svcs = sorted(counts, key=counts.get, reverse=True)
    return sorted_svcs[:2] # Top 2 service IDs
