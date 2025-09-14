# rank_tracker.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time
import schedule
import threading

DB_FILE = "rankings.db"

# --------------------------
# DB Setup
# --------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT,
        city TEXT,
        target_url TEXT,
        rank INTEGER,
        date TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT,
        city TEXT,
        target_url TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedule_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT,
        time TEXT
    )
    """)
    conn.commit()
    conn.close()

# --------------------------
# Scraper
# --------------------------
def build_google_url(query, city, start=0):
    uule = quote(city)  # simplified UULE for MVP
    return f"https://www.google.com/search?q={quote(query)}&num=100&start={start}&uule={uule}"

def get_rank(keyword, target_url, city):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = build_google_url(keyword, city)
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    results = soup.select("div.tF2Cxc")

    for idx, res in enumerate(results, start=1):
        link_tag = res.select_one("a")
        if link_tag and target_url in link_tag['href']:
            return idx
    return None

# --------------------------
# Save & Load
# --------------------------
def save_rank(keyword, city, target_url, rank):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO rankings (keyword, city, target_url, rank, date)
    VALUES (?, ?, ?, ?, ?)
    """, (keyword, city, target_url, rank, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def save_settings(keywords, cities, target_url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings")
    for kw in keywords:
        for city in cities:
            cursor.execute("INSERT INTO settings (keyword, city, target_url) VALUES (?, ?, ?)",
                           (kw.strip(), city.strip(), target_url.strip()))
    conn.commit()
    conn.close()

def load_settings():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM settings", conn)
    conn.close()
    return df

def save_schedule(day, time_str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedule_config")
    cursor.execute("INSERT INTO schedule_config (day, time) VALUES (?, ?)", (day, time_str))
    conn.commit()
    conn.close()

def load_schedule():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM schedule_config", conn)
    conn.close()
    if not df.empty:
        return df.iloc[0]['day'], df.iloc[0]['time']
    return None, None

def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM rankings", conn)
    conn.close()
    return df

# --------------------------
# Background Scheduler
# --------------------------
def run_weekly_job():
    settings = load_settings()
    for _, row in settings.iterrows():
        rank = get_rank(row['keyword'], row['target_url'], row['city'])
        save_rank(row['keyword'], row['city'], row['target_url'], rank)
        time.sleep(2)

def schedule_thread():
    while True:
        day, time_str = load_schedule()
        if day and time_str:
            schedule.clear()
            getattr(schedule.every(), day.lower()).at(time_str).do(run_weekly_job)
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=schedule_thread, daemon=True).start()

# --------------------------
# Streamlit UI
# --------------------------
st.title("Keyword Rank Tracker (MVP)")

init_db()

st.sidebar.header("Input Keywords & Settings")
keywords = st.sidebar.text_area("Keywords (one per line)").splitlines()
cities = st.sidebar.text_area("Cities (one per line)").splitlines()
target_url = st.sidebar.text_input("Target URL", "example.com")

if st.sidebar.button("Save Settings"):
    save_settings(keywords, cities, target_url)
    st.success("Settings saved. Scheduler will run based on your config.")

st.sidebar.header("Scheduler Settings")
day = st.sidebar.selectbox("Day of Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
time_str = st.sidebar.text_input("Time (HH:MM, 24hr)", "09:00")

if st.sidebar.button("Save Schedule"):
    save_schedule(day, time_str)
    st.success(f"Schedule saved: {day} at {time_str}")

if st.sidebar.button("Run Tracking Now"):
    with st.spinner("Fetching rankings..."):
        for kw in keywords:
            for city in cities:
                rank = get_rank(kw.strip(), target_url.strip(), city.strip())
                save_rank(kw.strip(), city.strip(), target_url.strip(), rank)
                time.sleep(2)
    st.success("Tracking completed and saved!")

# --------------------------
# Data + Charts
# --------------------------
df = load_data()
if not df.empty:
    st.subheader("Rankings Data")
    st.dataframe(df)

    st.subheader("Rank Trends")
    selected_keyword = st.selectbox("Select Keyword", df['keyword'].unique())
    selected_city = st.selectbox("Select City", df['city'].unique())

    trend = df[(df['keyword'] == selected_keyword) & (df['city'] == selected_city)]
    trend['date'] = pd.to_datetime(trend['date'])
    trend = trend.sort_values("date")

    import matplotlib.dates as mdates
    fig, ax = plt.subplots()
    ax.plot(trend['date'], trend['rank'], marker="o", linestyle="-")
    ax.invert_yaxis()
    ax.set_title(f"Ranking trend for '{selected_keyword}' in {selected_city}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rank")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)
    st.pyplot(fig)
else:
    st.info("No ranking data yet. Run a tracking first or wait for the weekly schedule.")
