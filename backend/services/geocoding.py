import requests
import math
import logging

logger = logging.getLogger(__name__)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the Earth 
    (specified in decimal degrees) using the Haversine formula.
    Result is in kilometers.
    """
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def get_travel_time(origin_lat, origin_lon, dest_lat, dest_lon, mode='driving'):
    """
    Gets estimated travel time in seconds between two points using OSRM.
    'origin' and 'dest' are tuples of (lat, lng).
    """
    base_url = "https://router.project-osrm.org/route/v1"
    coordinates = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    url = f"{base_url}/{mode}/{coordinates}"
    params = {
        'overview': 'false',
        'steps': 'false'
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get('code') == 'Ok' and data.get('routes'):
            # Duration is in seconds
            return data['routes'][0]['duration']
    except Exception as e:
        logger.error(f"OSRM routing error: {e}")

    # Fallback: estimate based on straight line distance (60 km/h average)
    dist_km = haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
    return (dist_km / 60.0) * 3600.0  # seconds


_GEO_CACHE = {}

def geocode_address(address):
    """
    Converts a string address into latitude and longitude using Nominatim.
    Uses a simple memory-based cache to avoid redundant API hits.
    """
    if not address:
        return None, None

    if address in _GEO_CACHE:
        return _GEO_CACHE[address]

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': address,
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'Antigravity-Appointment-Manager/1.0'
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if data:
            result = (float(data[0]['lat']), float(data[0]['lon']))
            _GEO_CACHE[address] = result
            return result
    except Exception as e:
        logger.error(f"Geocoding error: {e}")

    return None, None

def find_emergency_nearby(lat, lng, radius_m=5000):
    """
    Finds nearby hospitals, clinics, and ambulance stations using OpenStreetMap Overpass API.
    radius_m is in meters (default 5km).
    """
    overpass_url = "https://overpass-api.de/api/interpreter"

    # Query for hospitals, clinics, and ambulance stations
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lng});
      node["amenity"="clinic"](around:{radius_m},{lat},{lng});
      node["emergency"="ambulance_station"](around:{radius_m},{lat},{lng});
      way["amenity"="hospital"](around:{radius_m},{lat},{lng});
      way["amenity"="clinic"](around:{radius_m},{lat},{lng});
      way["emergency"="ambulance_station"](around:{radius_m},{lat},{lng});
    );
    out center;
    """

    try:
        response = requests.post(overpass_url, data={'data': overpass_query})
        data = response.json()

        results = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            # Get location (node has lat/lon, way has center)
            el_lat = element.get('lat') or element.get('center', {}).get('lat')
            el_lon = element.get('lon') or element.get('center', {}).get('lon')

            if not el_lat or not el_lon:
                continue

            results.append({
                'name': tags.get('name', f"Nearby {tags.get('amenity', 'Help')}"),
                'type': tags.get('amenity') or tags.get('emergency') or 'medical',
                'lat': el_lat,
                'lng': el_lon,
                'address': tags.get('addr:full') or f"{tags.get('addr:street', '')} {tags.get('addr:city', '')}".strip() or "Address not listed",
                'phone': tags.get('phone') or tags.get('contact:phone') or tags.get('emergency:phone') or "N/A"
            })
        return results
    except Exception as e:
        logger.error(f"Emergency search error: {e}")
        return []
