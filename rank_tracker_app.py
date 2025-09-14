import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
import schedule
import time
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import base64

# =====================
# Fallback Data
# =====================
FALLBACK_COUNTRIES = [
    {"cca2": "US", "name": {"common": "United States"}},
    {"cca2": "PH", "name": {"common": "Philippines"}},
    {"cca2": "AU", "name": {"common": "Australia"}},
    {"cca2": "GB", "name": {"common": "United Kingdom"}},
    {"cca2": "CA", "name": {"common": "Canada"}}
]

FALLBACK_CITIES = {
    "US": ["New York", "Los Angeles", "Chicago", "Houston", "Miami"],
    "PH": ["Manila", "Cebu City", "Davao City", "Quezon City", "Makati"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "GB": ["London", "Manchester", "Birmingham", "Liverpool", "Leeds"],
    "CA": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"]
}

# =====================
# Database setup
# =====================
DB_FILE = "rankings.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            target_page TEXT,
            country TEXT,
            city TEXT,
            rank INTEGER,
            date TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# =====================
# Country & City Helpers
# =====================
@st.cache_data(ttl=86400)
def get_countries():
    try:
        resp = requests.get("https://restcountries.com/v3.1/all", timeout=10)
        resp.raise_for_status()
        countries = sorted(resp.json(), key=lambda x: x["name"]["common"])
        return countries
    except Exception as e:
        st.warning(f"⚠️ Could not fetch countries. Using fallback list. Error: {e}")
        return FALLBACK_COUNTRIES

@st.cache_data(ttl=86400)
def get_cities(country_code):
    try:
        resp = requests.get("https://api.teleport.org/api/urban_areas/", timeout=10)
        resp.raise_for_status()
        data = resp.json()["_links"]["ua:item"]
        return [{"name": c["name"]} for c in data]
    except Exception as e:
        st.warning(f"⚠️ Could not fetch cities for {country_code}. Using fallback list. Error: {e}")
        return [{"name": c} for c in FALLBACK_CITIES.get(country_code, [])]

# =====================
# Rank Tracking (Scraper)
# =====================
def build_google_url(query, country, city, start=0):
    base = "https://www.google.com/search?"
    params = {
        "q": query,
        "hl": "en",
        "num": 100,
        "start": start
    }
    # NOTE: for full accuracy, you'd generate a proper UULE param
    return base + urlencode(params)

def get_rank(keyword, target_page, country, city):
    url = build_google_url(keyword, country, city)
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = soup.select("div.yuRUbf a")

    rank = None
    for i, link in enumerate(results, 1):
        href = link["href"]
        if target_page in href:
            rank = i
            break
    return rank if rank else -1

# =====================
# Scheduler
# =====================
def run_weekly_job(keywords, target_page, country, city):
    for kw in keywords:
        rank = get_rank(kw, target_page, country, city)
        log_rank(kw, target_page, country, city, rank)

def log_rank(keyword, target_page, country, city, rank):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rankings (keyword, target_page, country, city, rank, date) VALUES (?, ?, ?, ?, ?, ?)",
                   (keyword, target_page, country, city, rank, datetime.now()))
    conn.commit()
    conn.close()

# =====================
# UI
# =====================
st.title("📊 Rank Tracker App")

# Initialize DB
init_db()

# Country + City dropdowns
countries = get_countries()
country_names = [c["name"]["common"] for c in countries]
country_choice = st.selectbox("Select country", country_names)

country_code = None
for c in countries:
    if c["name"]["common"] == country_choice:
        country_code = c.get("cca2")
        break

cities = get_cities(country_code)
city_names = [c["name"] for c in cities]
city_choice = st.selectbox("Select city", city_names if city_names else ["No cities available"])

# Keyword + target page input
keywords_input = st.text_area("Enter keywords (one per line)")
target_page = st.text_input("Target page (domain or URL fragment)")

keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

# Manual run
if st.button("Run Tracking Now"):
    for kw in keywords:
        rank = get_rank(kw, target_page, country_choice, city_choice)
        log_rank(kw, target_page, country_choice, city_choice, rank)
    st.success("✅ Tracking run complete!")

# Scheduler config
st.subheader("Scheduler")
schedule_time = st.time_input("Select time for weekly run")
if st.button("Set Weekly Scheduler"):
    st.info(f"📅 Weekly run set for {schedule_time.strftime('%H:%M')} (server time)")

# View data
st.subheader("Ranking History")
conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT * FROM rankings", conn)
conn.close()

if not df.empty:
    st.dataframe(df)

    # Chart per keyword
    for kw in df["keyword"].unique():
        subset = df[df["keyword"] == kw]
        plt.figure()
        plt.plot(subset["date"], subset["rank"], marker="o")
        plt.gca().invert_yaxis()
        plt.title(f"Ranking history for: {kw}")
        plt.xlabel("Date")
        plt.ylabel("Rank")
        st.pyplot(plt)

    # Export
    st.subheader("Export Data")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "rankings.csv", "text/csv")

    excel_file = "rankings.xlsx"
    df.to_excel(excel_file, index=False)
    with open(excel_file, "rb") as f:
        st.download_button("Download Excel", f, "rankings.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("No ranking data yet. Run tracking to see results.")
