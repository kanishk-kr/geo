# utils/osm.py
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Initialize Nominatim geocoder
# user_agent is required and should be unique to your app
geolocator = Nominatim(user_agent="walmart-demand-forecasting-app-v1")

# Add rate limiting to avoid getting blocked (1 request per second)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

@st.cache_data
def osm_autocomplete(address):
    """
    Get autocomplete suggestions from Nominatim.
    Nominatim's 'geocode' with limit=5 works well for this.
    """
    if not address or len(address) < 3:
        return []
    
    try:
        # We ask for 5 results, exactly_one=False
        locations = geocode(address, exactly_one=False, limit=5)
        if not locations:
            return []
        
        # Format for st_searchbox: (description, place_id)
        # We'll use the full address as the 'place_id' for simplicity
        return [(loc.address, loc.address) for loc in locations]
    
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return []

@st.cache_data
def get_osm_details(address):
    """
    Get details for a specific address.
    Since we used the address as the 'place_id', we just geocode it again.
    """
    try:
        location = geocode(address)
        if not location:
            return None
        
        # Format the result to match the structure our app expects
        return {
            "result": {
                "geometry": {
                    "location": {
                        "lat": location.latitude,
                        "lng": location.longitude
                    }
                },
                "name": address.split(',')[0], # Use first part of address as name
                "formatted_address": location.address
            }
        }
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return None