# Rank Tracker App

A Streamlit app to track keyword rankings in Google at both national and city levels.  

### Features
- Country + city dropdowns (RESTCountries + Teleport APIs, with fallbacks)
- Scraper-based Google rank tracking (top 100 results)
- SQLite logging
- Weekly scheduler
- Ranking history charts
- Export to CSV & Excel

### Run locally
```bash
pip install -r requirements.txt
streamlit run rank_tracker_app.py
