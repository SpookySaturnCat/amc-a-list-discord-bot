import asyncio
import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import URLError
from bs4 import BeautifulSoup
from serpapi import GoogleSearch

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
THEATERS_FILE = os.path.join(DATA_DIR, "theaters.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def _sync_fetch_sitemap() -> str:
    # Synchronous helper to fetch the sitemap XML for theater directory caching.
    url = "https://www.amctheatres.com/sitemaps/sitemap-theatres.xml"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")
    except URLError as e:
        print(f"Failed to fetch sitemap: {e}")
        return ""

def update_theater_cache() -> list[dict]:
    # Parses the sitemap XML into structured records and writes to data/theaters.json.
    raw_xml = _sync_fetch_sitemap()
    if not raw_xml:
        return load_cached_theaters()

    soup = BeautifulSoup(raw_xml, "xml")
    parsed_theaters = []
    pattern = re.compile(r"amctheatres\.com/movie-theatres/([^/]+)/([^/]+)$")

    for tag in soup.find_all("loc"):
        url = tag.text.strip()
        if match := pattern.search(url):
            city_slug, theater_slug = match.groups()
            display_theater = theater_slug.replace("-", " ").title()
            display_city = city_slug.replace("-", " ").title()

            parsed_theaters.append({
                "name": f"{display_theater} ({display_city})",
                "slug": theater_slug,
                "url": url
            })

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(THEATERS_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_theaters, f, indent=2)

    return parsed_theaters

async def fetch_theater_directory() -> list[dict]:
    # Asynchronous wrapper for updating local theater directory.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, update_theater_cache)


def load_cached_theaters() -> list[dict]:
    # Loads stored theater database from data/theaters.json.
    if os.path.exists(THEATERS_FILE):
        try:
            with open(THEATERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return []

def _sync_fetch_google_showtimes(theater_name: str) -> list[dict]:
    # SerpApi search fetcher for theater showtimes.
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

        movies = []
        if showtime_data := results.get("showtimes", []):
            for movie in showtime_data[0].get("movies", []):
                title = movie.get("name")
                poster_url = movie.get("thumbnail", "")
                time_strings = []

                for entry in movie.get("showing", []):
                    if isinstance(entry, dict):
                        time_strings.extend(entry.get("time", []))
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

async def fetch_daily_schedule() -> list[dict]:
    # Asynchronous wrapper fetching theater showtimes via SerpApi using active config.
    theater_name = "AMC Theater"
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                theater_name = json.load(f).get("theater_name", theater_name)
        except json.JSONDecodeError:
            pass

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_google_showtimes, theater_name)

if __name__ == "__main__":
    results = update_theater_cache()
    print(f"Successfully cached {len(results)} theaters to {THEATERS_FILE}")