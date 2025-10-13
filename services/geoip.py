import os
import geoip2.database
from typing import Optional, Dict

# Path to GeoLite2 database
GEOIP_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'GeoLite2-City.mmdb')

def get_location_from_ip(ip: str) -> Optional[Dict[str, str]]:
    """
    Get location information from IP address using local GeoLite2 database only
    Returns dict with 'country' and 'city' keys, or None if failed
    """
    if not ip or ip in ['127.0.0.1', '::1', 'localhost']:
        return None
    
    # Only use local database
    if not os.path.exists(GEOIP_DB_PATH):
        return None
    
    try:
        with geoip2.database.Reader(GEOIP_DB_PATH) as reader:
            response = reader.city(ip)
            country = response.country.name
            city = response.city.name
            
            # Handle cases where city might be None but country exists
            if not country:
                return None
            
            # Try to get subdivision (state/region) if city is not available
            subdivision = None
            if not city and response.subdivisions:
                subdivision = response.subdivisions.most_specific.name
            
            return {
                'country': country,
                'country_code': response.country.iso_code,
                'city': city if city else subdivision,
                'has_coordinates': bool(response.location and response.location.latitude)
            }
    except Exception as e:
        print(f"Error getting location for IP {ip}: {e}")
        return None

def format_location(location: Optional[Dict[str, str]]) -> str:
    """
    Format location info for display
    """
    if not location:
        return "—"
    
    country = location.get('country')
    city = location.get('city')
    
    if not country:
        return "—"
    
    # If we have both city and country
    if city:
        return f"{city}, {country}"
    # If we only have country
    else:
        return f"{country} (region)"

def get_country_flag(country_code: str) -> str:
    """
    Convert country code to flag emoji
    """
    if not country_code or len(country_code) != 2:
        return "🏳️"
    
    # Convert country code to flag emoji
    # Each letter is converted to regional indicator symbol
    flag = ""
    for char in country_code.upper():
        flag += chr(ord(char) - ord('A') + ord('🇦'))
    
    return flag

