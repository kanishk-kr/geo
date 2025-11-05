# main.py
import streamlit as st
# import uuid # No longer needed for session token

from groq import Groq
import datetime
import pytz
import pandas as pd
from streamlit_searchbox import st_searchbox # type: ignore
from utils.pages import set_page_config
from utils.predicthq import (
    get_api_key,
    get_predicthq_client,
    fetch_events,
    ATTENDED_CATEGORIES,
    NON_ATTENDED_CATEGORIES,
    UNSCHEDULED_CATEGORIES,
)
# Updated imports:
from utils.walmart import search_walmart_stores, get_walmart_details
from utils.osm import osm_autocomplete, get_osm_details
from utils.map import show_map
from utils.metrics import show_metrics
from dateutil.parser import parse as parse_date

def main():
    set_page_config("Location Insights")
    st.markdown("""
    <style>
    .stDataFrame {
        border: 1px solid #e1e4e8;
        border-radius: 8px;
    }
    .stDataFrame tr:hover {
        background-color: #f5f5f5;
    }
    .stSelectbox div[data-baseweb="select"] {
        margin-top: 20px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)
    
    # Initialize session state
    # We no longer need the google_session_token
    # if "google_session_token" not in st.session_state:
    #     st.session_state.google_session_token = uuid.uuid4().hex

    
    if get_api_key() is not None:
        show_address_lookup()
    else:
        st.warning("Please set a PredictHQ API Token.", icon="⚠️")


def generate_demand_insights(event, walmart_data=None):
    """Generate demand insights using Groq's ultra-fast LLM"""
    prompt = f"""
As a Walmart retail demand forecasting expert, analyze this event and provide detailed product-level predictions:

**EVENT ANALYSIS REQUEST**
- EVENT: {event['Event Title']}
- TYPE: {event['Category']}
- EXPECTED ATTENDANCE: {event['PHQ Attendance']:,}
- DATE: {event['Start Date (local tz)']}
- VENUE: {event['Venue Name']} ({event['Venue Address']})

**REQUIRED OUTPUT FORMAT**
1. Trending Products Analysis:
   - List 8-12 specific products (include brand names where relevant)
   - For each product provide:
     * Current typical Walmart inventory level
     * Recommended stock increase (% and units)
     * Price point recommendation
     * Profit margin estimate

2. Pop-up Store Feasibility:
   - ROI probability (Low/Medium/High)
   - Required inventory investment
   - Expected revenue range
   - Break-even attendance threshold

3. Generate a CSV format output with columns:
   Product Name,Category,Current Stock,Recommended Increase,Projected Demand,Price Point,Profit Margin

Example format for CSV:
\"\"\"
Product Name,Category,Current Stock,Recommended Increase,Projected Demand,Price Point,Profit Margin
Gatorade 20oz bottles,Beverages,200,+75%,350,$1.98,18%
Ozark Trail 6-Person Tent,Outdoor Gear,15,+120%,33,$89.97,32%
\"\"\"

Focus on Walmart's top-selling inventory categories and private label brands (Great Value, Mainstays, etc.) where applicable.
"""
    
    try:
        client = Groq(api_key=st.secrets["groq_api_key"])
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,  # Lower for more factual outputs
            max_tokens=2000
        )
        
        raw_output = response.choices[0].message.content
        
        # Extract CSV data if present
        csv_data = None
        if "```csv" in raw_output:
            csv_data = raw_output.split("```csv")[1].split("```")[0].strip()
        elif "Product Name,Category" in raw_output:
            csv_data = raw_output.split("Product Name,Category")[1].split("\n\n")[0]
            csv_data = "Product Name,Category" + csv_data
        
        # Create downloadable CSV
        if csv_data:
            st.download_button(
                label="📥 Download Product Recommendations",
                data=csv_data,
                file_name=f"walmart_demand_{event['Event Title'].replace(' ','_')}.csv",
                mime="text/csv"
            )
        
        return raw_output.replace("```csv", "").replace("```", "")
    
    except Exception as e:
        return f"Error generating insights: {str(e)}"

    
# Updated function
def lookup_address(text):
    if len(text) > 3:
        # Check if it's a Walmart store search
        if "walmart" in text.lower():
            search_term = text.lower().replace("walmart", "").strip()
            if search_term:
                results = search_walmart_stores(search_term)
                # Format for st_searchbox
                return [(r["description"], r["place_id"]) for r in results]
        
        # If not Walmart, do normal OSM search
        return osm_autocomplete(text)
    else:
        return []


def show_address_lookup():
    st.markdown(
        """
        <div style='text-align: center;'>
            <div style='margin-bottom: 20px;'>
            <h1>Location Insights</h1>
            <p>Discover nearby events that will fill your tables and boost your revenue.</p>
           
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.title(st.secrets["title"])

    place_id = st_searchbox(
        lookup_address,
        placeholder="e.g. 123 Main St, Anytown, USA or Walmart ...",
        clear_on_submit=True,
        key="address",
    )

    if place_id is not None:
        show_location_insights(place_id)


# Update in main.py

# Remove the @st.cache_data decorator from this function
def show_location_insights(place_id):
    
    place_details = None
    is_walmart = False

    # Check if it's a Walmart store place_id
    if place_id.startswith("walmart_"):
        is_walmart = True
        place_details = get_walmart_details(place_id)
    else:
        # Otherwise, it's an address from OSM. Get its details.
        place_details = get_osm_details(place_id)
    
    if place_details is None:
        st.error("Could not retrieve location details")
        return

    # Unpack details (structure is the same for both)
    name = place_details["result"]["name"]
    lat = place_details["result"]["geometry"]["location"]["lat"]
    lon = place_details["result"]["geometry"]["location"]["lng"]
    address = place_details["result"]["formatted_address"]
    walmart_data = place_details["result"].get("walmart_data", {}) # Only present if is_walmart

    tz = "UTC"
    date_from = datetime.datetime.now().date()
    date_to = date_from + datetime.timedelta(days=90)
    categories = ATTENDED_CATEGORIES
    suggested_radius_industry = st.secrets["suggested_radius_industry"] if "suggested_radius_industry" in st.secrets else "accommodation"

    # Fetch data (can be cached)
    radius, radius_unit = fetch_suggested_radius(lat, lon, radius_unit="mi", industry=suggested_radius_industry)
    events = fetch_events(
        lat,
        lon,
        radius=radius,
        date_from=date_from,
        date_to=date_to,
        tz=tz,
        categories=categories,
        radius_unit=radius_unit,
    )

    # Display UI (not cached)
    st.header(f"Over the next 90 days in {name}, you could be missing out on:")
    
    show_metrics(
        lat=lat,
        lon=lon,
        radius=radius,
        radius_unit=radius_unit,
        date_from=date_from,
        date_to=date_to,
        suggested_radius={"radius": radius, "radius_unit": radius_unit},
        tz=tz
    )

    show_map(
        lat=lat,
        lon=lon,
        radius_meters=calc_meters(radius, radius_unit),
        events=events,
    )

    if is_walmart and walmart_data:
        with st.expander("Walmart Store Details"):
            st.write(f"**Address:** {address}")
            st.write(f"**Phone:** {walmart_data.get('phone_number_1', 'N/A')}")
            st.write(f"**Hours:** {walmart_data.get('open_hours', 'N/A')}")
            st.write(f"**[View on Walmart.com]({walmart_data.get('url', '')})**")

    show_events_list(events)  # This contains widgets


@st.cache_data
def fetch_suggested_radius(lat, lon, radius_unit="mi", industry="parking"):
    phq = get_predicthq_client()
    suggested_radius = phq.radius.search(location__origin=f"{lat},{lon}", radius_unit=radius_unit, industry=industry)

    return suggested_radius.radius, suggested_radius.radius_unit


def calc_meters(value, unit):
    if unit == "mi":
        return value * 1609
    if unit == "ft":
        return value * 0.3048
    elif unit == "km":
        return value * 1000
    else:
        return value


def visualize_demand(event):
    """Create visualizations for demand predictions"""
    # Example visualization - you can customize this based on your LLM response
    categories = ["Snacks", "Beverages", "Sunscreen", "Grilling Supplies", "Party Decorations"]
    demand_increase = [45, 60, 30, 55, 40]  # These would come from your LLM analysis
    
    # Create a bar chart
    chart_data = pd.DataFrame({
        "Product Category": categories,
        "Estimated Demand Increase (%)": demand_increase
    })
    
    st.bar_chart(
        chart_data,
        x="Product Category",
        y="Estimated Demand Increase (%)",
        color="#FFA500"  # Walmart blue would be #0071CE
    )
    
    # Profitability estimate
    st.metric(
        label="Estimated Profit Potential for Pop-up Store",
        value="High" if event['PHQ Attendance'] > 1000 else "Medium",
        delta=f"{event['PHQ Attendance']} attendees"
    )

def show_events_list(events):
    """Display events in a clickable dataframe with demand insights"""
    results = []
    
    for event in events["results"]:
        venue = next(filter(lambda entity: entity["type"] == "venue", event["entities"]), None)
        
        row = {
                  "Event Title": event["title"],
            "PHQ Attendance": event["phq_attendance"] if event["phq_attendance"] else 0,
            "Category": event["category"],
            "Start Date (local tz)": parse_date(event["start"])
            .astimezone(pytz.timezone(event["timezone"]))
            .strftime("%d-%b-%Y %H:%M"),
            "End Date (local tz)": parse_date(event["end"])
            .astimezone(pytz.timezone(event["timezone"]))
            .strftime("%d-%b-%Y %H:%M"),
            "Predicted End Date (local tz)": parse_date(event["predicted_end"])
            .astimezone(pytz.timezone(event["timezone"]))
            .strftime("%d-%b-%Y %H:%M")
            if "predicted_end" in event and event["predicted_end"] is not None
            else "",
            "Venue Name": venue["name"] if venue else "",
            "Venue Address": venue["formatted_address"] if venue else "",
            "Placekey": event["geo"]["placekey"] if "geo" in event and "placekey" in event["geo"] else "",
            "Predicted Event Spend": f"${event['predicted_event_spend']:,.0f}"
            if "predicted_event_spend" in event and event["predicted_event_spend"] is not None
            else "",
            "Predicted Event Spend (Hospitality)": f"${event['predicted_event_spend_industries']['hospitality']:,.0f}"
            if "predicted_event_spend_industries" in event
            and event["predicted_event_spend_industries"]["hospitality"] is not None
            else "",
        }
        results.append(row)

    events_df = pd.DataFrame(results)
    
    # Display the dataframe with clickable rows
    st.dataframe(
        events_df,
        use_container_width=True,
        hide_index=True,
        column_order=["Event Title", "PHQ Attendance", "Category", "Start Date (local tz)","End Date (local tz)","Predicted End Date (local tz)", "Predicted Event Spend", "Predicted Event Spend (Hospitality)","Venue Name", "Venue Address"],
        column_config={
            "Event Title": st.column_config.TextColumn("Event", width="medium"),
            "PHQ Attendance": st.column_config.NumberColumn("Attendance", format="%d"),
            "Category": st.column_config.TextColumn("Category"),
            "Start Date (local tz)": st.column_config.DatetimeColumn("Start Date"),
            "End Date (local tz)": st.column_config.DatetimeColumn("End Date"),
            "Predicted End Date (local tz)": st.column_config.DatetimeColumn("Predicted End Date"),
            # Use a custom format for predicted spend
            "Predicted Event Spend": st.column_config.NumberColumn("Predicted Spend", format="$%.2f"),
            "Venue Name": st.column_config.TextColumn("Venue", width="medium"),
            "Venue Address": st.column_config.TextColumn("Address", width="large"),
            "Placekey": st.column_config.TextColumn("Placekey", width="medium"),
   
            "Predicted Event Spend (Hospitality)": st.column_config.TextColumn("Hospitality Spend", width="medium"),
        }
    )
    
    # Add selectbox to choose an event for detailed analysis
    selected_event = st.selectbox(
        "Select an event for demand analysis:",
        options=events_df.to_dict('records'),
        format_func=lambda x: f"{x['Event Title']} ({x['Start Date (local tz)']})",
        index=None,
        placeholder="Select an event..."
    )
    
    if selected_event:
        with st.spinner("Generating demand insights..."):
            insights = generate_demand_insights(selected_event)
        with st.expander("🚀 Real-time Demand Forecast", expanded=True):
            st.markdown(
                f"""
                <div style="
                    background: #000000;
                    padding: 15px;
                    border-radius: 10px;
                    border-left: 4px solid #2d8b49;
                ">
                {insights}
                </div>
                """,
                unsafe_allow_html=True
            )    
        
       
        
        # Add visualization section
        st.markdown("### 📊 Demand Visualization")
        visualize_demand(selected_event)


if __name__ == "__main__":
    main()