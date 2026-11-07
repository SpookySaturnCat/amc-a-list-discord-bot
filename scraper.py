import asyncio
import json
import os
import re
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from serpapi import GoogleSearch

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
THEATERS_FILE = os.path.join(DATA_DIR, "theaters.json")

# Synchronous helper to fetch the sitemap XML for theater directory caching
def _sync_fetch_sitemap() -> str:
    url = "https://www.amctheatres.com/sitemaps/sitemap-theatres.xml"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=10) as response:
        return response.read().decode("utf-8")

# Parses the sitemap XML into structured records and writes to data/theaters.json
def update_theater_cache() -> list[dict]:
    raw_xml = _sync_fetch_sitemap()
    soup = BeautifulSoup(raw_xml, "xml")
    loc_tags = soup.find_all("loc")

    parsed_theaters = []
    pattern = re.compile(r"amctheatres\.com/movie-theatres/([^/]+)/([^/]+)$")

    for tag in loc_tags:
        url = tag.text.strip()
        match = pattern.search(url)
        if match:
            city_slug, theater_slug = match.groups()
            display_theater = theater_slug.replace("-", " ").title()
            display_city = city_slug.replace("-", " ").title()
            full_name = f"{display_theater} ({display_city})"

            parsed_theaters.append({
                "name": full_name,
                "slug": theater_slug,
                "url": url
            })

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(THEATERS_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_theaters, f, indent=2)

    return parsed_theaters

# Asynchronous wrapper for updating local theater directory
async def fetch_theater_directory() -> list[dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, update_theater_cache)

# Loads stored theater database from data/theaters.json
def load_cached_theaters() -> list[dict]:
    if os.path.exists(THEATERS_FILE):
        with open(THEATERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# SerpApi search fetcher for theater showtimes
def _sync_fetch_google_showtimes(theater_name: str) -> list[dict]:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is missing from .env environment variables.")
        return []

    params = {
        "engine": "google",
        "q": f"{theater_name} showtimes",
        "api_key": api_key
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        showtime_data = results.get("showtimes", [])

        movies = []
        if showtime_data and len(showtime_data) > 0:
            day_schedule = showtime_data[0].get("movies", [])
            for movie in day_schedule:
                title = movie.get("name")
                poster_url = movie.get("thumbnail") or ""

                raw_times = movie.get("showing", [])
                time_strings = []
                for entry in raw_times:
                    if isinstance(entry, dict):
                        times_list = entry.get("time", [])
                        time_strings.extend(times_list)
                    elif isinstance(entry, str):
                        time_strings.append(entry)

                if title and time_strings:
                    movies.append({
                        "title": title,
                        "poster_url": poster_url,
                        "showtimes": time_strings
                    })
        return movies
    except Exception as e:
        print(f"SerpApi Execution Error: {e}")
        return []

# Asynchronous wrapper fetching theater showtimes via SerpApi
async def fetch_daily_schedule(theater_url: str) -> list[dict]:
    # Extract clean theater name from stored configuration or directory
    config_path = os.path.join(DATA_DIR, "config.json")
    theater_name = "AMC Theater"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            theater_name = cfg.get("theater_name", theater_name)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_google_showtimes, theater_name)

if __name__ == "__main__":
    results = update_theater_cache()
    print(f"Successfully cached {len(results)} theaters to {THEATERS_FILE}")