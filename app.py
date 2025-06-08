import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# ===================== Google Sheets Setup =====================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)

gc = gspread.authorize(credentials)

# Open Google Sheet
SHEET_NAME = "RestaurantHistory"  # Ensure this sheet exists
WORKSHEET_NAME = "Sheet1"         # Ensure this worksheet exists
sh = gc.open(SHEET_NAME)
worksheet = sh.worksheet(WORKSHEET_NAME)

def save_to_sheet(food, restaurant, rating, address, timestamp):
    row = [timestamp, food, restaurant, rating, address]
    worksheet.append_row(row)

# ===================== Apify API Setup =====================

APIFY_API_TOKEN = st.secrets["apify_token"]["apify_token"]
ACTOR_ID = "apify/google-maps-scraper"

def fetch_restaurant_from_apify(food, location="Lagos, Nigeria"):
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items?token={APIFY_API_TOKEN}"

    payload = {
        "searchStringsArray": [f"{food} in {location}"],
        "maxCrawledPlacesPerSearch": 1,
        "includeReviews": False,
        "includeImages": False
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            result = data[0]
            name = result.get("title", "Unknown")
            rating = result.get("totalScore", 0.0)
            address = result.get("address", "Not available")
            return name, rating, address
        else:
            return None, None, None
    else:
        st.error(f"Apify error: {response.status_code} - {response.text}")
        return None, None, None

# ===================== Streamlit UI =====================

st.set_page_config(page_title="Restaurant Recommender", page_icon="🍽️")
st.title("🍽️ Restaurant Recommender with Apify + Google Sheets")

food = st.text_input("Enter food type (e.g., pizza, sushi)", placeholder="pizza")
location = st.text_input("Enter location", value="Lagos, Nigeria")

if st.button("🔍 Recommend"):
    if food:
        with st.spinner("Fetching recommendation from Apify..."):
            restaurant, rating, address = fetch_restaurant_from_apify(food, location)

        if restaurant:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success(f"**Recommended Restaurant:** {restaurant}\n\n⭐ **Rating:** {rating}\n📍 **Address:** {address}")
            save_to_sheet(food, restaurant, rating, address, timestamp)
        else:
            st.warning("No restaurant found. Try a different query.")
    else:
        st.warning("Please enter a food type.")

# ===================== Show History =====================

with st.expander("📜 View Search History"):
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        df.columns = ["Timestamp", "Food", "Restaurant", "Rating", "Address"]
        st.dataframe(df)
    else:
        st.write("No history yet.")
