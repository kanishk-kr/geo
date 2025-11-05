# utils/walmart.py
import streamlit as st
import pandas as pd

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
            })
        
        return results
    except Exception as e:
        st.error(f"Error loading Walmart data: {e}")
        return []

def get_walmart_details(place_id):
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
                # *** THE FIX IS HERE: Changed row['zip_code'] to store['zip_code'] ***
                "formatted_address": f"{store['street_address']}, {store['city']}, {store['state']} {store['zip_code']}",
                "walmart_data": store.to_dict()
            }
        }
    except Exception as e:
        st.error(f"Error getting Walmart store details: {e}")
        return None