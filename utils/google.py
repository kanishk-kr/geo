# google.py
import streamlit as st
import googlemaps
import pandas as pd

def get_api_key():
    return st.secrets["google_api_key"]

def search_walmart_stores(search_term):
    try:
        # Load Walmart data from CSV
        walmart_data = pd.read_csv("walmart_2018_11_06.csv")
        
        # Filter stores that match the search term (case insensitive)
        matches = walmart_data[walmart_data['name'].str.contains(search_term, case=False, na=False)]
        
        # Convert to list of dicts for easier processing
        results = []
        for _, row in matches.iterrows():
            results.append({
                "description": f"{row['name']} - {row['street_address']}, {row['city']}, {row['state']} {row['zip_code']}",
                "place_id": f"walmart_{row['name'].replace(' ', '_')}",
                "structured_formatting": {
                    "main_text": row['name'],
                    "secondary_text": f"{row['street_address']}, {row['city']}, {row['state']} {row['zip_code']}"
                },
                "walmart_data": row.to_dict()
            })
        
        return results
    except Exception as e:
        st.error(f"Error loading Walmart data: {e}")
        return []

def places_autocomplete(address, session_token):
    # Check if it's a Walmart store search (could use a special prefix like "walmart:")
    if "walmart" in address.lower():
        search_term = address.lower().replace("walmart", "").strip()
        if search_term:  # Only search if there's something after "walmart"
            return search_walmart_stores(search_term)
    
    # Otherwise do normal Google Places search
    try:
        gmaps = googlemaps.Client(key=get_api_key())
        result = gmaps.places_autocomplete(
            address,
            session_token=session_token,
        )
        return result
    except Exception as e:
        st.error(f"Google Places API error: {e}")
        return []

def get_place_details(place_id, session_token):
    # Check if it's a Walmart store place_id
    if place_id.startswith("walmart_"):
        try:
            # Get the store name from place_id
            store_name = place_id[8:].replace('_', ' ')
            
            # Load Walmart data
            walmart_data = pd.read_csv("walmart_2018_11_06.csv")
            
            # Find the matching store
            store = walmart_data[walmart_data['name'] == store_name].iloc[0]
            
            # Return in similar format to Google Places
            return {
                "result": {
                    "geometry": {
                        "location": {
                            "lat": store['latitude'],
                            "lng": store['longitude']
                        }
                    },
                    "name": store['name'],
                    "formatted_address": f"{store['street_address']}, {store['city']}, {store['state']} {store['zip_code']}",
                    "walmart_data": store.to_dict()
                }
            }
        except Exception as e:
            st.error(f"Error getting Walmart store details: {e}")
            return None
    
    # Otherwise do normal Google Places lookup
    try:
        gmaps = googlemaps.Client(key=get_api_key())
        result = gmaps.place(
            place_id,
            session_token=session_token,
        )
        return result
    except Exception as e:
        st.error(f"Google Places API error: {e}")
        return None