import random
from datetime import datetime
from backend.models.models import Appointment

def calculate_noshow_probability(customer_id, business_id, date_str, time_str, service_id):
    """
    Predictive ML heuristic to calculate no-show risk.
    In a real ML pipeline, this would call endpoint mapping to a serialized scikit-learn model,
    passing features like lead_time_days, historical_noshow_rate, weather_data.

    Here we simulate an ensemble logic model.
    """

    # Feature 1: Historical No-shows
    past_appointments = Appointment.query.filter_by(customer_id=customer_id).all()
    if not past_appointments:
        # New customers are medium risk
        history_risk = 0.50
    else:
        cancellations = [a for a in past_appointments if a.status == 'cancelled']
        history_risk = min(len(cancellations) / len(past_appointments), 1.0)

    # Feature 2: Lead time to appointment
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        lead_time_days = (target_date - datetime.today().date()).days
    except ValueError:
        lead_time_days = 7

    lead_time_risk = 0.2
    if lead_time_days > 14:
        lead_time_risk = 0.7 # Far in future increases no-show risk
    elif lead_time_days < 2:
        lead_time_risk = 0.1 # Very soon decreases risk

    # Ensemble Weighting
    final_risk_score = (history_risk * 0.6) + (lead_time_risk * 0.4)

    # Add minor stochastic noise (simulating variance in random forest)
    noise = random.uniform(-0.05, 0.05)
    final_risk_score = max(0.0, min(1.0, final_risk_score + noise))

    high_risk = final_risk_score > 0.65

    return {
        "probability": final_risk_score,
        "high_risk": high_risk,
        "recommend_deposit": high_risk
    }

def get_lapsed_customers(business_id, months_lapsed=3):
    """
    Automated CRM script.
    Finds customers who haven't booked in X months to send them a win-back hook.
    """
    # This is a stub for the CRM worker
    pass
