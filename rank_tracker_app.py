import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import datetime
import os

# =============================
# DATABASE SETUP
# =============================
DB_DIR = "data"
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "rankings.db")

SCHEMA_VERSION = 2  # bump when schema changes


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Create schema_version table
    c.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER
        )
    """)

    # Check version
    c.execute("SELECT version FROM schema_version")
    row = c.fetchone()

    if not row:
        # Fresh DB
        c.execute("""
            CREATE TABLE rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT,
                country TEXT,
                city TEXT,
                target_url TEXT,
                rank INTEGER,
                device TEXT,
                engine TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif row[0] < SCHEMA_VERSION:
        # Migration: add missing columns
        try:
            c.execute("ALTER TABLE rankings ADD COLUMN country TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE rankings ADD COLUMN city TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE rankings ADD COLUMN device TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE rankings ADD COLUMN engine TEXT")
        except sqlite3.OperationalError:
            pass
        c.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))

    conn.commit()
    conn.close()


def save_result(keyword, country, city, target_url, rank, device, engine):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO rankings (keyword, country, city, target_url, rank, device, engine, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (keyword, country, city, target_url, rank, device, engine, datetime.datetime.now()),
    )
    conn.commit()
    conn.close()


def get_google_rank(keyword, target_url, country="us"):
    """Dummy rank checker (replace with SERP API for production)."""
    try:
        query = f"https://www.google.com/search?q={keyword}&gl={country}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(query, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        results = soup.select("div.yuRUbf a")
        for idx, link in enumerate(results, 1):
            if target_url in link["href"]:
                return idx
        return None
    except Exception as e:
        st.error(f"Error fetching rank: {e}")
        return None


# =============================
# STREAMLIT APP
# =============================

st.set_page_config(page_title="Rank Tracker App", layout="wide")

st.title("🔎 Rank Tracker App")

init_db()

keywords_input = st.text_area("Enter keywords (one per line):")
target_url = st.text_input("Enter your target URL:")

# Country and city selection
country = st.selectbox("Select Country", ["US", "CA", "AU", "PH", "IN"])
city = st.text_input("Enter City (optional):")

# Device and engine
device = st.selectbox("Device", ["Desktop", "Mobile"])
engine = st.selectbox("Search Engine", ["Google", "Bing"])

if st.button("Track Rankings"):
    if not keywords_input or not target_url:
        st.warning("Please enter keywords and target URL")
    else:
        keywords = [kw.strip() for kw in keywords_input.split("\n") if kw.strip()]
        results = []
        for kw in keywords:
            rank = get_google_rank(kw, target_url, country=country.lower())
            save_result(kw, country, city, target_url, rank, device, engine)
            results.append({"Keyword": kw, "Rank": rank})
        st.success("✅ Tracking completed!")
        df = pd.DataFrame(results)
        st.dataframe(df)

st.subheader("📊 Ranking History")
conn = sqlite3.connect(DB_FILE)
df_history = pd.read_sql_query("SELECT * FROM rankings ORDER BY date DESC", conn)
conn.close()

st.dataframe(df_history)

csv = df_history.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "rankings.csv", "text/csv")
