import streamlit as st
import requests
import pandas as pd
from transformers import pipeline
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURE STREAMLIT PAGE ---
st.set_page_config(page_title="🍽️ Restaurant Recommender", layout="wide")

# Hide default Streamlit elements
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton, .st-emotion-cache-13ln4jf, button[kind="icon"] {
        display: none !important;
    }
    .custom-footer {
        text-align: center;
        font-size: 14px;
        margin-top: 50px;
        padding: 20px;
        color: #aaa;
    }
    </style>
""", unsafe_allow_html=True)

# --- BERT Sentiment Analysis Model ---
@st.cache_resource(show_spinner=False)
def get_classifier():
    return pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

# --- GOOGLE SHEETS SETUP ---
@st.cache_resource
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Restaurant_Recommender_History").sheet1
    return sheet

def read_history():
    sheet = get_gsheet()
    return sheet.get_all_records()

def append_history(data_dict):
    food = data_dict.get("Food", "").strip()
    location = data_dict.get("Location", "").strip()
    if not food or not location:
        return
    sheet = get_gsheet()
    existing_rows = sheet.get_all_records()
    for row in existing_rows:
        if (row.get("Restaurant") == data_dict.get("Restaurant") and
            row.get("Food") == food and
            row.get("Location") == location):
            return
    row = [
        data_dict.get("Restaurant", ""),
        data_dict.get("Rating", ""),
        data_dict.get("Address", ""),
        food,
        location
    ]
    sheet.append_row(row)
    st.success("New recommendation saved to history!")

# --- SESSION STATE ---
if "page" not in st.session_state:
    st.session_state.page = "Recommend"

# --- SIDEBAR MENU ---
with st.sidebar:
    st.markdown("## 🍽️ Menu")
    if st.button("Recommend"): st.session_state.page = "Recommend"
    if st.button("Deep Learning"): st.session_state.page = "Deep Learning"
    if st.button("History"): st.session_state.page = "History"
    if st.button("About"): st.session_state.page = "About"

# --- PAGE: RECOMMEND ---
if st.session_state.page == "Recommend":
    st.title("🍽️ AI Restaurant Recommender")
    st.markdown("Find top restaurants using **Apify** and **AI sentiment analysis**.")

    col1, _ = st.columns([1, 1])
    with col1:
        food = st.text_input("🍕 Food Type", placeholder="e.g., Sushi, Pizza, Jollof")
    with col1:
        location = st.text_input("📍 Location", placeholder="e.g., Lagos, Nairobi")

    apify_api_key = st.secrets.get("apify_api_key", "")

    if st.button("🔍 Search"):
        if not food or not location:
            st.warning("⚠️ Enter both a food type and a location.")
        elif not apify_api_key:
            st.error("❌ Apify API key missing.")
        else:
            st.session_state.results = None
            with st.spinner("Scraping and analyzing..."):
                # Start Apify task to scrape reviews
                url = "https://api.apify.com/v2/actor-tasks/restaurant-review-scraper/run-sync-get-dataset-items?token=" + apify_api_key
                payload = {
                    "location": location,
                    "query": food
                }
                response = requests.post(url, json=payload)
                data = response.json()

                classifier = get_classifier()
                results = []

                for r in data[:10]:  # Limit to top 10
                    name = r.get("name", "")
                    address = r.get("address", "")
                    reviews = r.get("reviews", [])

                    sentiments = []
                    review_texts = []
                    for review in reviews[:5]:  # Analyze max 5 reviews
                        text = review.get("text", "")
                        if text:
                            sentiment = classifier(text[:512])[0]
                            stars = int(sentiment["label"].split()[0])
                            sentiments.append(stars)
                            review_texts.append(text)

                    avg_rating = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0
                    if sentiments:
                        results.append({
                            "Restaurant": name,
                            "Address": address,
                            "Rating": avg_rating,
                            "Stars": "⭐" * int(round(avg_rating)),
                            "Reviews": len(sentiments),
                            "Tips": review_texts
                        })

                if results:
                    df = pd.DataFrame([{
                        "Restaurant": r["Restaurant"],
                        "Address": r["Address"],
                        "Rating": r["Rating"],
                        "Stars": r["Stars"],
                        "Reviews": r["Reviews"]
                    } for r in results])
                    df.index += 1
                    st.session_state.results = results
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("No valid reviews found.")

    # --- DISPLAY RESULTS ---
    if st.session_state.get("results"):
        top3 = sorted(st.session_state.results, key=lambda x: x["Rating"], reverse=True)[:3]
        st.divider()
        st.subheader("🏅 Top Picks")

        cols = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(top3):
            with cols[i]:
                st.markdown(f"### {medals[i]} {r['Restaurant']}")
                st.markdown(f"**📍 Address:** {r['Address']}")
                st.markdown(f"**⭐ Rating:** {r['Rating']}")
                for tip in r["Tips"]:
                    st.markdown(f"- _{tip}_")

        # Save top recommendation
        top = max(st.session_state.results, key=lambda x: x["Rating"])
        append_history({
            "Restaurant": top["Restaurant"],
            "Rating": top["Rating"],
            "Address": top["Address"],
            "Food": food,
            "Location": location
        })

# --- PAGE: DEEP LEARNING ---
elif st.session_state.page == "Deep Learning":
    st.title("🤖 Deep Learning Explained")
    st.markdown("""
    This app uses **BERT** (Bidirectional Encoder Representations from Transformers) for sentiment analysis.

    - We collect restaurant reviews using **Apify**.
    - Analyze them using **HuggingFace BERT** to estimate a rating.
    - Recommend top-rated restaurants based on AI scores.
    """)

# --- PAGE: HISTORY ---
elif st.session_state.page == "History":
    st.title("📚 Recommendation History")
    history = read_history()
    if history:
        df_hist = pd.DataFrame(history)
        df_hist.index += 1
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("No history yet. Run a search first.")

# --- PAGE: ABOUT ---
elif st.session_state.page == "About":
    st.title("ℹ️ About This App")
    st.markdown("""
    This project uses:
    - **Apify** for scraping restaurant data
    - **HuggingFace Transformers** for sentiment analysis
    - **Google Sheets** to store your recommendation history

    Developed using **Streamlit Cloud**.
    """)

# --- FOOTER ---
st.markdown('<div class="custom-footer">© 2025 AI Restaurant Recommender</div>', unsafe_allow_html=True)
