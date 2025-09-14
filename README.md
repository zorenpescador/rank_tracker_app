# Rank Tracker App

A simple keyword rank tracking tool built with Streamlit.  
Tracks keywords across multiple cities and countries, stores logs in SQLite, and visualizes results.

### Features
- National + city-level keyword tracking (UULE parameter)
- Auto-scheduler (weekly runs)
- SQLite logging
- Charts for ranking history
- Export results to CSV/Excel
- Dynamic country/city selection (via GeoDB API with fallback)

### Setup
```bash
git clone https://github.com/zorenpescador/rank_tracker_app.git
cd rank_tracker_app
pip install -r requirements.txt
streamlit run rank_tracker_app.py
