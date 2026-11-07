import asyncio
import json
import os
import re
import urllib.parse
from urllib.request import Request, urlopen
from datetime import datetime, timedelta
from discord.ext import tasks
from serpapi import GoogleSearch

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_FILE = os.path.join(DATA_DIR, "weekly_schedule.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

DAY_PREFIXES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday"
}

# In-memory lookup cache to avoid repeating HTTP calls for identical titles across days
MOVIE_METADATA_CACHE = {}

def _resolve_dynamic_day(raw_day_str: str, base_time: datetime) -> str:
    """Dynamically converts 'Today', 'Tomorrow', 'Mon', 'Thu', etc. into full weekday names."""
    if not raw_day_str:
        return base_time.strftime("%A")

    clean_str = raw_day_str.strip().lower()

    if "today" in clean_str:
        return base_time.strftime("%A")
    if "tomorrow" in clean_str:
        return (base_time + timedelta(days=1)).strftime("%A")

    for prefix, full_name in DAY_PREFIXES.items():
        if clean_str.startswith(prefix):
            return full_name

    return raw_day_str.strip()

def _fetch_movie_metadata(title: str) -> dict:
    """
    Queries OMDb mirror and Wikipedia summary endpoints to fetch
    genre, MPAA rating, and clean direct .jpg/.png poster links in a single pass.
    """
    if title in MOVIE_METADATA_CACHE:
        return MOVIE_METADATA_CACHE[title]

    default_meta = {
        "genre": "Unknown",
        "rating": "Unknown",
        "poster_url": "https://images.amctheatres.com/amc-website/static/images/fallback/poster-placeholder.png"
    }

    # Primary lookup: Public OMDb mirror endpoint
    encoded_title = urllib.parse.quote(title)
    omdb_url = f"https://www.omdbapi.com/?t={encoded_title}&apikey=trilogy"

    try:
        req = Request(omdb_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("Response") == "True":
                genre = data.get("Genre")
                rating = data.get("Rated")
                poster = data.get("Poster")

                if genre and genre != "N/A":
                    default_meta["genre"] = genre

                if rating and rating != "N/A":
                    default_meta["rating"] = rating

                if poster and poster != "N/A" and poster.startswith("http"):
                    default_meta["poster_url"] = poster

                MOVIE_METADATA_CACHE[title] = default_meta
                return default_meta
    except Exception:
        pass

    # Secondary fallback: Wikipedia summary API with (film) disambiguation support
    queries_to_try = [title, f"{title} (film)", f"{title} (movie)"]
    for query_term in queries_to_try:
        clean_title = urllib.parse.quote(query_term)
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_title}"

        try:
            req = Request(wiki_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("type") == "disambiguation":
                    continue

                extract = data.get("extract", "")

                genre_match = re.search(
                    r"\b(action|comedy|drama|horror|thriller|animated|animation|sci-fi|family|adventure|documentary|musical|fantasy|crime|mystery|romance)\b",
                    extract,
                    re.I
                )
                if genre_match:
                    found_genre = genre_match.group(1).capitalize()
                    default_meta["genre"] = "Sci-Fi" if found_genre.lower() == "sci-fi" else found_genre

                thumbnail_obj = data.get("thumbnail", {})
                img_source = thumbnail_obj.get("source", "")
                if img_source and (img_source.endswith(".jpg") or img_source.endswith(".png") or img_source.endswith(
                        ".jpeg") or "upload.wikimedia.org" in img_source):
                    default_meta["poster_url"] = img_source

                MOVIE_METADATA_CACHE[title] = default_meta
                return default_meta
        except Exception:
            pass

    MOVIE_METADATA_CACHE[title] = default_meta
    return default_meta

def fetch_and_cache_weekly_showtimes() -> dict:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is missing from environment.")
        return {"status": "error", "message": "Missing API Key", "movies": []}

    theater_name = "AMC Theater"
    custom_location = None

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            theater_name = cfg.get("theater_name", theater_name)
            custom_location = cfg.get("location")

    now = datetime.now()

    os.makedirs(DATA_DIR, exist_ok=True)
    temp_cache = {"updating": True, "last_updated": now.isoformat(), "movies": []}
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(temp_cache, f, indent=2)

    query = f"{theater_name} showtimes"
    params = {
        "engine": "google",
        "q": query,
        "hl": "en",
        "gl": "us",
        "api_key": api_key
    }

    if custom_location:
        params["location"] = custom_location

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        showtime_data = results.get("showtimes", [])

        movies_list = []
        if showtime_data and isinstance(showtime_data, list):
            for day_entry in showtime_data:
                raw_day = day_entry.get("day", "")
                resolved_day = _resolve_dynamic_day(raw_day, now)

                for movie in day_entry.get("movies", []):
                    title = movie.get("name")
                    if not title:
                        continue

                    # Retrieve metadata (genre, rating, poster URL)
                    meta = _fetch_movie_metadata(title)

                    raw_times = movie.get("showing", [])
                    time_strings = []
                    for entry in raw_times:
                        if isinstance(entry, dict):
                            time_strings.extend(entry.get("time", []))
                        elif isinstance(entry, str):
                            time_strings.append(entry)

                    movies_list.append({
                        "day": resolved_day,
                        "raw_day_source": raw_day,
                        "title": title,
                        "genre": meta["genre"],
                        "rating": meta["rating"],
                        "poster_url": meta["poster_url"],
                        "showtimes": time_strings
                    })

        final_cache = {
            "updating": False,
            "last_updated": now.isoformat(),
            "movies": movies_list
        }

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_cache, f, indent=2)

        print(f"Weekly cache successfully populated with {len(movies_list)} entries.")
        return final_cache

    except Exception as e:
        print(f"Failed to fetch weekly showtimes: {e}")
        error_cache = {"updating": False, "error": str(e), "movies": []}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(error_cache, f, indent=2)
        return error_cache

@tasks.loop(minutes = 1)
async def schedule_updater_task():
    now = datetime.now()
    if now.weekday() == 3 and now.hour == 8 and now.minute == 30:
        print("Triggering Thursday 8:30 AM weekly schedule cache refresh...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, fetch_and_cache_weekly_showtimes)