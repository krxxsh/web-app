from flask import Blueprint, render_template, jsonify, request
from backend.services.geocoding import find_emergency_nearby

emergency_bp = Blueprint('emergency', __name__)

@emergency_bp.route("/emergency")
def emergency():
    return render_template('emergency.html', title="Emergency Services")

@emergency_bp.route("/api/emergency/nearby", methods=['POST'])
def nearby_emergency():
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    
    if not lat or not lng:
        return jsonify({'error': 'Location required'}), 400
    
    results = find_emergency_nearby(lat, lng)
    return jsonify(results)
