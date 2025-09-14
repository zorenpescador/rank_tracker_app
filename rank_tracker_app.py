import streamlit as st
import requests
from bs4 import BeautifulSoup
import base64
import urllib.parse
import pandas as pd
import time

# --- Generate UULE parameter for city ---
def generate_uule(city_name):
    city_bytes = city_name.encode("utf-8")
    encoded_city = base64.urlsafe_b64encode(city_bytes).decode("utf-8")
    return f"w+CAIQICI{encoded_city}"

# --- Get SERP Results ---
def get_serp_results(keyword, city, num_results=10):
    uule = generate_uule(city)
    query = urllib.parse.quote_plus(keyword)
    url = f"https://www.google.com/search?q={query}&num={num_results}&uule={uule}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for idx, div in enumerate(soup.select("div.yuRUbf a"), start=1):
        link = div.get("href")
        title = div.text
        results.append({"Rank": idx, "Title": title, "URL": link})

    return results

# --- Check Target Page Ranking ---
def check_ranking(keyword, target_url, city):
    serp = get_serp_results(keyword, city)
    for result in serp:
        if target_url in result["URL"]:
            return result["Rank"], result["URL"]
    return None, None

# --- Streamlit UI ---
st.set_page_config(page_title="Rank Tracker MVP", page_icon="📊", layout="wide")

st.title("📊 Rank Tracker MVP (Free Scraper + UULE)")
st.write("Track rankings by **keywords**, **target page**, and **city-level location** (via UULE).")

# User input
keywords_input = st.text_area("Keywords (one per line)", "insurance\nseo tools\nbest gym near me")
target_url = st.text_input("Target Page (URL)", "https://moneymatterswithzoren.com/")
city = st.text_input("City", "Cebu, Philippines")

if st.button("Track Rankings"):
    keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
    all_data = []

    with st.spinner("Fetching rankings..."):
        for kw in keywords:
            rank, found_url = check_ranking(kw, target_url, city)
            all_data.append({
                "Keyword": kw,
                "City": city,
                "Target URL": target_url,
                "Rank": rank if rank else "Not in Top 10",
                "Found URL": found_url if found_url else "-"
            })
            time.sleep(2)  # prevent being blocked

    df = pd.DataFrame(all_data)
    st.dataframe(df)

    # Download CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Results (CSV)",
        data=csv,
        file_name="rank_tracking_results.csv",
        mime="text/csv",
    )
