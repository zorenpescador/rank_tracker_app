import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
import schedule
import time
import threading
from datetime import datetime
import json

# =====================
# CONFIG
# =====================
API_HOST = "https://wft-geo-db.p.rapidapi.com/v1/geo"
HEADERS = {
    "X-RapidAPI-Key": "YOUR_API_KEY",   # replace with your RapidAPI key
    "X-RapidAPI-Host": "wft-geo-db.p.rapidapi.com"
}

DB_NAME = "ranktracker.db"

FALLBACK_COUNTRIES = [
    {"code": "US", "name": "United States"},
    {"code": "PH", "name": "Philippines"},
    {"code": "AU", "name": "Australia"},
    {"code": "GB", "name": "United Kingdom"},
    {"code": "CA", "name": "Canada"}
]

FALLBACK_CITIES = {
    "US": ["New York", "Los Angeles", "Chicago", "Houston", "Miami"],
    "PH": ["Manila", "Cebu City", "Davao City", "Quezon City", "Makati"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "GB": ["London", "Manchester", "Birmingham", "Liverpool", "Leeds"],
    "CA": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"]
}

# =====================
# DB Setup
# =====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT,
                    target_page TEXT,
                    country TEXT,
                    city TEXT,
                    rank INTEGER,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS locations_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    country_code TEXT,
                    country_name TEXT,
                    cities_json TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

# Save cities into DB cache
def save_cities_cache(country_code, country_name, cities):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM locations_cache WHERE country_code=?", (country_code,))
    c.execute("INSERT INTO locations_cache (country_code, country_name, cities_json) VALUES (?, ?, ?)",
              (country_code, country_name, json.dumps(cities)))
    conn.commit()
    conn.close()

# Load cities from DB cache
def load_cities_cache(country_code):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT cities_json FROM locations_cache WHERE country_code=?", (country_code,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

# =====================
# GeoDB Helpers (with caching + fallback + SQLite cache)
# =====================
@st.cache_data(ttl=86400)  # cache for 1 day
def get_countries():
    try:
        url = f"{API_HOST}/countries"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        resp.raise_for_status()
        countries = resp.json()["data"]
        return countries
    except Exception:
        st.warning("⚠️ Could not fetch countries from API. Using fallback list.")
        return FALLBACK_COUNTRIES

@st.cache_data(ttl=86400)  # cache for 1 day
def get_cities(country_code, country_name):
    try:
        url = f"{API_HOST}/countries/{country_code}/cities"
        params = {"limit": 50, "sort": "-population"}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=5)
        resp.raise_for_status()
        cities = [c["name"] for c in resp.json()["data"]]
        save_cities_cache(country_code, country_name, cities)  # save to DB
        return cities
    except Exception:
        st.warning(f"⚠️ Could not fetch cities for {country_name}. Using cached/fallback list.")
        cached = load_cities_cache(country_code)
        if cached:
            return cached
        return FALLBACK_CITIES.get(country_code, [])

# =====================
# Google Scraper (basic)
# =====================
def fetch_rank(keyword, target_page, country, city, max_results=100):
    query = keyword.replace(" ", "+")
    url = f"https://www.google.com/search?q={query}&num={max_results}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    results = soup.find_all("a")
    rank = None
    for i, link in enumerate(results):
        href = link.get("href")
        if href and target_page in href:
            rank = i + 1
            break
    return rank if rank else -1

# =====================
# Scheduler
# =====================
def run_tracker(keywords, target_page, country, city):
    for kw in keywords:
        rank = fetch_rank(kw, target_page, country, city)
        save_rank(kw, target_page, country, city, rank)

def save_rank(keyword, target_page, country, city, rank):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO rankings (keyword, target_page, country, city, rank) VALUES (?, ?, ?, ?, ?)",
              (keyword, target_page, country, city, rank))
    conn.commit()
    conn.close()

def schedule_task(keywords, target_page, country, city, interval):
    schedule.every(interval).weeks.do(run_tracker, keywords, target_page, country, city)

    def loop():
        while True:
            schedule.run_pending()
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True)
    t.start()

# =====================
# Streamlit UI
# =====================
st.title("Rank Tracker MVP (Scheduler + SQLite + Charts + Dynamic Locations)")

init_db()

# --- Input section
keywords_input = st.text_area("Enter keywords (comma-separated)")
target_page = st.text_input("Enter target page URL")

# Country dropdown
countries = get_countries()
country_names = [c["name"] for c in countries]
country = st.selectbox("Select country", country_names)

city = None
if country:
    country_code = [c["code"] for c in countries if c["name"] == country][0]
    cities = get_cities(country_code, country)
    city = st.selectbox("Select city", cities)

interval = st.number_input("Schedule interval (weeks)", min_value=1, max_value=52, value=1)

if st.button("Start Tracking"):
    if keywords_input and target_page and country and city:
        keywords = [k.strip() for k in keywords_input.split(",")]
        schedule_task(keywords, target_page, country, city, interval)
        st.success(f"Tracking started for {len(keywords)} keywords in {city}, {country}")

# --- Show results
if st.button("Show Logs"):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM rankings ORDER BY date DESC", conn)
    conn.close()
    st.dataframe(df)

    if not df.empty:
        # --- Download buttons
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="rankings_log.csv",
            mime="text/csv"
        )

        excel = df.to_excel("rankings_log.xlsx", index=False, engine="openpyxl")
        with open("rankings_log.xlsx", "rb") as f:
            st.download_button(
                label="📊 Download Excel",
                data=f,
                file_name="rankings_log.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # --- Chart
        fig, ax = plt.subplots()
        for kw in df["keyword"].unique():
            subset = df[df["keyword"] == kw]
            ax.plot(subset["date"], subset["rank"], marker="o", label=kw)
        ax.invert_yaxis()
        ax.set_ylabel("Rank (lower is better)")
        ax.set_title("Keyword Ranking Over Time")
        ax.legend()
        st.pyplot(fig)
