import streamlit as st
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pandas as pd

# -------------------------
# Setup Google Sheets creds
# -------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)

# Google Sheets API service
service = build('sheets', 'v4', credentials=credentials)
sheet_id = "YOUR_SHEET_ID_HERE"  # <-- Replace with your actual Google Sheet ID

# -----------------
# Apify API settings
# -----------------
APIFY_API_TOKEN = st.secrets["apify_token"]["apify_token"]
APIFY_ACTOR_ID = "apify/google-places-reviews"  # example actor to fetch Google Places reviews

def run_apify_actor(place_id):
    """
    Run Apify actor to fetch reviews for a given Google Place ID.
    """
    url = f"https://api.apify.com/v2/actor-tasks/{APIFY_ACTOR_ID}/runs?token={APIFY_API_TOKEN}"
    payload = {
        "placeId": place_id
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    run_data = response.json()
    run_id = run_data['data']['id']
    return run_id

def get_apify_run_results(run_id):
    """
    Get results of a run after completion.
    """
    url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?token={APIFY_API_TOKEN}"
    # Polling until finished, for simplicity just a one-time get here
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def append_to_sheet(values):
    """
    Append rows to Google Sheet.
    """
    body = {
        'values': values
    }
    result = service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()
    return result

# -------------------
# Streamlit UI starts
# -------------------
st.title("Restaurant Reviews Fetcher with Apify & Google Sheets")

place_id = st.text_input("Enter Google Place ID:", "")

if st.button("Fetch Reviews"):
    if not place_id.strip():
        st.error("Please enter a valid Google Place ID.")
    else:
        with st.spinner("Starting Apify actor..."):
            try:
                run_id = run_apify_actor(place_id)
                st.success(f"Apify run started with ID: {run_id}")
            except Exception as e:
                st.error(f"Failed to start Apify actor: {e}")
                st.stop()

        with st.spinner("Fetching results... (may take a few seconds)"):
            try:
                results = get_apify_run_results(run_id)
                if not results:
                    st.warning("No reviews found or run is not completed yet.")
                    st.stop()

                # Convert to DataFrame
                df = pd.DataFrame(results)
                st.write("Fetched reviews:")
                st.dataframe(df)

                # Prepare values to append
                # Example: append review author and text columns only
                values = df[['authorName', 'text']].fillna('').values.tolist()
                append_to_sheet(values)
                st.success("Reviews appended to Google Sheet!")

            except Exception as e:
                st.error(f"Failed to fetch or save reviews: {e}")
