import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import schedule
import threading
import time
import datetime

DB_FILE = "rankings.db"

# =============================
# DATABASE SETUP
# =============================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            city TEXT,
            country TEXT,
            target_url TEXT,
            rank INTEGER,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# =============================
# SCRAPER FUNCTION
# =============================
def get_google_rank(keyword, target_url, country="us", city=None, top_n=100):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.google.com/search?q={keyword}&num={top_n}&gl={country}"

    if city:
        # Basic city encoding placeholder
        url += f"&uule={city}"

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    results = soup.find_all("a")

    rank = None
    for i, link in enumerate(results[:top_n], start=1):
        href = link.get("href")
        if href and target_url in href:
            rank = i
            break
    return rank

# =============================
# SAVE TO DB
# =============================
def save_result(keyword, country, city, target_url, rank):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO rankings (keyword, country, city, target_url, rank) VALUES (?, ?, ?, ?, ?)",
        (keyword, country, city, target_url, rank),
    )
    conn.commit()
    conn.close()

# =============================
# COUNTRY & CITY API
# =============================
def get_countries():
    url = "https://countriesnow.space/api/v0.1/countries/positions"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        return sorted([c["name"] for c in data.get("data", [])])
    except Exception as e:
        st.warning(f"⚠️ Could not fetch countries. Using fallback list. Error: {e}")
        return ["United States", "Philippines", "Australia", "India"]

def get_cities(country):
    url = "https://countriesnow.space/api/v0.1/countries/cities"
    try:
        resp = requests.post(url, json={"country": country}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("data"):
            return sorted(data["data"])
    except Exception as e:
        st.warning(f"⚠️ Could not fetch cities for {country}. Using fallback list. Error: {e}")
        if country == "Philippines":
            return ["Manila", "Cebu", "Davao"]
        elif country == "United States":
            return ["New York", "Los Angeles", "Chicago"]
        return []
    return []

# =============================
# STREAMLIT APP UI
# =============================
st.title("📊 Rank Tracker App (MVP)")

keywords_input = st.text_area("Enter keywords (one per line):")
target_url = st.text_input("Enter your target URL:")

countries = get_countries()
selected_country = st.selectbox("Select country", countries)

cities = get_cities(selected_country)
selected_city = st.selectbox("Select city", cities)

schedule_time = st.time_input("Select time for weekly auto-run", value=datetime.time(9, 0))

if st.button("Run Tracking Now"):
    if keywords_input and target_url:
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
        results = []

        for kw in keywords:
            rank = get_google_rank(kw, target_url, country=selected_country[:2].lower(), city=selected_city)
            save_result(kw, selected_country, selected_city, target_url, rank)
            results.append({"Keyword": kw, "Rank": rank})

        st.success("✅ Tracking completed!")
        df = pd.DataFrame(results)
        st.dataframe(df)

        # Chart (latest distribution)
        st.subheader("📈 Rank Distribution (Latest Run)")
        fig, ax = plt.subplots()
        df.plot(kind="bar", x="Keyword", y="Rank", ax=ax, legend=False)
        plt.gca().invert_yaxis()
        st.pyplot(fig)

# =============================
# HISTORICAL TREND
# =============================
if st.checkbox("📜 Show Historical Trends"):
    conn = sqlite3.connect(DB_FILE)
    df_hist = pd.read_sql_query("SELECT * FROM rankings ORDER BY date ASC", conn)
    conn.close()

    if not df_hist.empty:
        st.subheader("📉 Historical Rank Trends")
        fig, ax = plt.subplots()

        for kw in df_hist["keyword"].unique():
            kw_data = df_hist[df_hist["keyword"] == kw]
            ax.plot(kw_data["date"], kw_data["rank"], marker="o", label=kw)

        plt.gca().invert_yaxis()
        ax.legend()
        st.pyplot(fig)
    else:
        st.info("No historical data yet.")

# =============================
# BACKGROUND SCHEDULER
# =============================
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

def weekly_task():
    if keywords_input and target_url:
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
        for kw in keywords:
            rank = get_google_rank(kw, target_url, country=selected_country[:2].lower(), city=selected_city)
            save_result(kw, selected_country, selected_city, target_url, rank)

schedule.every().monday.at(schedule_time.strftime("%H:%M")).do(weekly_task)
threading.Thread(target=run_scheduler, daemon=True).start()
