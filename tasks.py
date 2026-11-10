import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Set, Tuple, Dict, Any, List
from discord.ext import tasks
from serpapi import GoogleSearch
import aiohttp
from curl_cffi.requests import AsyncSession
from scraper import async_fetch_tmdb_metadata_and_reviews

# Data directory paths
DATA_DIR = os.path.join(str(os.path.dirname(__file__)), "data")
CACHE_FILE = os.path.join(DATA_DIR, "movie_schedule_and_metadata.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Day prefix mapping for relative query strings
DAY_PREFIXES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday"
}

# Map dynamic day strings ('Today', 'Tomorrow', prefix matches) to full weekday names
def _resolve_dynamic_day(raw_day_str: str, base_time: datetime) -> str:
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

# Execute concurrent metadata and review extraction for all ingested movie titles
async def _fetch_all_metadata_async(unique_titles: Set[str]) -> Tuple[Dict[str, Any], bool]:
    async with aiohttp.ClientSession() as aio_session:
        async with AsyncSession() as curl_session:  # type: ignore
            tasks_list = [
                async_fetch_tmdb_metadata_and_reviews(aio_session, curl_session, title)
                for title in unique_titles
            ]
            results = await asyncio.gather(*tasks_list)

            metadata_map: Dict[str, Any] = {}
            rt_health_checks: List[bool] = []

            for title, (meta_data, is_healthy) in zip(unique_titles, results):
                metadata_map[title] = meta_data
                rt_health_checks.append(is_healthy)

            # Mark RT scraper health status broken if failure rate exceeds 25% threshold
            failed_count = rt_health_checks.count(False)
            rt_overall_healthy = failed_count < (len(unique_titles) * 0.25)

            return metadata_map, rt_overall_healthy

# Scrape theater schedule data via SerpApi and populate unified metadata JSON cache
def fetch_and_cache_weekly_showtimes() -> Dict[str, Any]:
    start_time = time.perf_counter()
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return {"status": "error", "message": "Missing API Key", "schedule": [], "metadata": {}, "elapsed_seconds": 0.0}

    theater_name = "AMC Theater"
    custom_location = None

    # Load active guild theater configuration override if present
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                theater_name = cfg.get("theater_name", theater_name)
                custom_location = cfg.get("location")
        except json.JSONDecodeError:
            pass

    now = datetime.now()
    os.makedirs(DATA_DIR, exist_ok=True)

    params = {
        "engine": "google",
        "q": f"{theater_name} showtimes",
        "hl": "en",
        "gl": "us",
        "api_key": api_key
    }
    if custom_location:
        params["location"] = custom_location

    try:
        # Ingest schedule payload from SerpApi Google search engine
        results = GoogleSearch(params).get_dict()
        schedule_list: List[Dict[str, Any]] = []
        unique_titles: Set[str] = set()

        if showtime_data := results.get("showtimes", []):
            for day_entry in showtime_data:
                resolved_day = _resolve_dynamic_day(day_entry.get("day", ""), now)

                for movie in day_entry.get("movies", []):
                    title = movie.get("name")
                    if not title:
                        continue

                    unique_titles.add(title)
                    time_strings: List[str] = []
                    for entry in movie.get("showing", []):
                        if isinstance(entry, dict):
                            time_strings.extend(entry.get("time", []))
                        elif isinstance(entry, str):
                            time_strings.append(entry)

                    schedule_list.append({
                        "day": resolved_day,
                        "title": title,
                        "showtimes": time_strings
                    })

        # Safely resolve event loop execution context for metadata enrichment tasks
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                metadata_map, rt_healthy = asyncio.run_coroutine_threadsafe(
                    _fetch_all_metadata_async(unique_titles), loop
                ).result()
            else:
                metadata_map, rt_healthy = loop.run_until_complete(_fetch_all_metadata_async(unique_titles))
        except RuntimeError:
            metadata_map, rt_healthy = asyncio.run(_fetch_all_metadata_async(unique_titles))

        elapsed_seconds = round(time.perf_counter() - start_time, 2)
        final_cache: Dict[str, Any] = {
            "updating": False,
            "last_updated": now.isoformat(),
            "elapsed_seconds": elapsed_seconds,
            "rt_status": "healthy" if rt_healthy else "broken",
            "schedule": schedule_list,
            "metadata": metadata_map
        }

        # Write cache to disk
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_cache, f, indent=2)

        print(f"Unified cache populated in {elapsed_seconds}s (RT Status: {'Healthy' if rt_healthy else 'BROKEN'}).")
        return final_cache

    except Exception as e:
        elapsed_seconds = round(time.perf_counter() - start_time, 2)
        print(f"Failed to fetch weekly schedule: {e}")
        error_cache: Dict[str, Any] = {"updating": False, "error": str(e), "elapsed_seconds": elapsed_seconds, "schedule": [], "metadata": {}}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(error_cache, f, indent=2)
        return error_cache

# Automated background daemon enforcing Thursday 8:30 AM schedule cache rebuilds
@tasks.loop(minutes=1)
async def schedule_updater_task() -> None:
    now = datetime.now()
    if now.weekday() == 3 and now.hour == 8 and now.minute == 30:
        print("Triggering Thursday 8:30 AM weekly schedule cache refresh...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, fetch_and_cache_weekly_showtimes)