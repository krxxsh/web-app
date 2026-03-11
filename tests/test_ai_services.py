import pytest
from unittest.mock import MagicMock, patch
from backend.services.chatbot import extract_booking_intent

def test_extract_intent_no_api_key(app):
    """Test that the chatbot returns an error when no GEMINI_API_KEY is configured."""
    with app.app_context():
        # Ensure GEMINI_API_KEY is not in config
        app.config['GEMINI_API_KEY'] = None
        
        result = extract_booking_intent("I want to book something")
        assert "error" in result
        assert result["error"] == "AI API Key not configured"

@patch('google.generativeai.GenerativeModel')
@patch('google.generativeai.configure')
def test_extract_intent_mocked_success(mock_configure, mock_model, app):
    """Test successful extraction with mocked Gemini AI."""
    with app.app_context():
        app.config['GEMINI_API_KEY'] = 'fake_key'
        
        # Mocking the AI response
        mock_instance = mock_model.return_value
        mock_response = MagicMock()
        mock_response.text = '{"service_name": "Haircut", "date": "2026-03-20", "time": "14:00", "action": "book"}'
        mock_instance.generate_content.return_value = mock_response
        
        result = extract_booking_intent("Book haircut for March 20 at 2pm")
        
        assert result["service_name"] == "Haircut"
        assert result["action"] == "book"
        assert result["date"] == "2026-03-20"
        assert result["time"] == "14:00"
