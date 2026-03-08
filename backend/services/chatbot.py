import google.generativeai as genai
from flask import current_app
import json
from datetime import datetime

def extract_booking_intent(user_text):
    """
    Uses Gemini AI to extract structured booking details from natural language text.
    Example: "I want to book a hair cut for tomorrow at 10 AM"
    """
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        return {"error": "AI API Key not configured"}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')

    prompt = f"""
    Extract booking details from this text and return ONLY a JSON object.
    Text: "{user_text}"
    Current Date: {datetime.now().strftime('%Y-%m-%d')}

    The JSON should contain:
    - service_name: string or null
    - date: YYYY-MM-DD or null
    - time: HH:MM (24h format) or null
    - action: "book", "cancel", "check_availability", or "other"
    """

    try:
        response = model.generate_content(prompt)
        # Attempt to find JSON in response
        response_text = response.text
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(response_text[start:end])
        return {"error": "Could not parse AI response"}
    except Exception as e:
        return {"error": str(e)}

def generate_chatbot_response(intent, context):
    """Generates a human-friendly response based on the extracted intent."""
    if intent.get('action') == 'book':
        if not intent.get('date') or not intent.get('time'):
            return "Sure! Which date and time were you thinking of?"
        return f"Got it. Looking for a slot for {intent['service_name']} on {intent['date']} at {intent['time']}. One moment..."
    elif intent.get('action') == 'check_availability':
        return "I can check that for you. What service are you interested in?"

    return "I'm here to help with your bookings. You can say things like 'Book a massage for Friday at 4pm'."
