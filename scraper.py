import asyncio
import json
import os
import re
import random
import urllib.parse
from datetime import datetime
from typing import List, Dict, Tuple, Any
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# System constants and directory configuration
DATA_DIR = os.path.join(str(os.path.dirname(__file__)), "data")
THEATERS_FILE = os.path.join(DATA_DIR, "theaters.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
UNIFIED_CACHE_FILE = os.path.join(DATA_DIR, "movie_schedule_and_metadata.json")

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Fetch raw AMC theater sitemap XML using urllib HTTP requests
def _sync_fetch_sitemap() -> str:
    import urllib.request
    url = "https://www.amctheatres.com/sitemaps/sitemap-theatres.xml"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"Failed to fetch sitemap: {e}")
        return ""

# Parse AMC sitemap XML and save theater location records to JSON cache
def update_theater_cache() -> list[dict]:
    raw_xml = _sync_fetch_sitemap()
    if not raw_xml:
        return load_cached_theaters()

    soup = BeautifulSoup(raw_xml, "xml")
    parsed_theaters: List[Dict[str, str]] = []
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

# Load cached AMC theater locations from disk
def load_cached_theaters() -> list[dict]:
    if os.path.exists(THEATERS_FILE):
        try:
            with open(THEATERS_FILE, "r", encoding="utf-8") as f:
                res: list[dict] = json.load(f)
                return res
        except json.JSONDecodeError:
            pass
    return []

# Sanitize title strings by stripping screening formats, tags, and special characters
def clean_title_for_search(raw_title: str) -> str:
    cleaned = re.sub(
        r"\b(IMAX|3D|2D|Dolby Cinema|Dolby|Re-Release|Release|Early Release|Early Access|Fan Event|Subbed|Dubbed|Premiere|Special Screening|Anniversary)\b",
        "", raw_title, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"[\(\)\[\]]", "", cleaned)
    cleaned = re.sub(r"[:\-\|]+$", "", cleaned.strip())
    return re.sub(r"\s+", " ", cleaned).strip()

# Format and truncate review content string with spoiler tags and hyperlink
def truncate_review_with_inline_link(text: str, url: str, max_len: int = 700) -> str:
    if len(text) <= max_len:
        return f"||{text}|| [read full review]({url})"

    truncated = text[:max_len].rsplit(" ", 1)[0]
    return f"||{truncated}...|| [read more]({url})"

# Scrape Rotten Tomatoes critic consensus score using TLS fingerprint impersonation
async def fetch_rotten_tomatoes_score(
        curl_session: AsyncSession,
        title: str,
        current_year: str,
        original_year: str
) -> tuple[str, bool]:
    clean_name = re.sub(r"[^\w\s]", "", title.lower()).replace(" ", "_")
    slug_candidates = [clean_name]

    if current_year and current_year != "Unknown":
        slug_candidates.append(f"{clean_name}_{current_year}")

    if original_year and original_year != "Unknown" and original_year != current_year:
        slug_candidates.append(f"{clean_name}_{original_year}")

    for slug in slug_candidates:
        rt_url = f"https://www.rottentomatoes.com/m/{slug}"
        try:
            resp = await curl_session.get(rt_url, impersonate="chrome120", timeout=3)  # type: ignore
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Locate score element via modern shadow DOM slots or fallback tags
                score_elem = soup.find("rt-text", {"slot": "criticsScore"}) or soup.find("score-icon-critic")
                if score_elem:
                    score_str = score_elem.text.strip()
                    if match := re.search(r"(\d{1,3})%", score_str):
                        pct = match.group(1)
                        return f"[{pct}%]({rt_url})", True

                # Secondary DOM check: Schema.org structured JSON-LD payloads
                for script in soup.find_all("script", type="application/ld+json"):
                    if "aggregateRating" in script.text:
                        if match := re.search(r'"ratingValue":\s*"(\d{1,3})"', script.text):
                            pct = match.group(1)
                            return f"[{pct}%]({rt_url})", True

            elif resp.status_code in [403, 503]:
                return "N/A", False
        except Exception:
            pass

    return "N/A", True

# Fetch IMDb, Metacritic, and secondary Rotten Tomatoes ratings from OMDb API
async def fetch_omdb_critic_scores(
        session: aiohttp.ClientSession,
        imdb_id: str,
        title: str,
        year: str
) -> dict:
    omdb_key = os.getenv("OMDB_API_KEY", "trilogy")
    encoded_title = urllib.parse.quote(title)

    scores_data: Dict[str, Any] = {
        "rotten_tomatoes_fallback": "N/A",
        "imdb": "N/A",
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else f"https://www.imdb.com/find/?q={encoded_title}",
        "metacritic": "N/A",
        "metacritic_url": f"https://www.metacritic.com/search/{encoded_title}/",
        "combined_average_10": 0.0
    }

    query_urls: List[str] = []
    if imdb_id:
        query_urls.append(f"https://www.omdbapi.com/?i={imdb_id}&apikey={omdb_key}")

    if year and year != "Unknown":
        query_urls.append(f"https://www.omdbapi.com/?t={encoded_title}&y={year}&apikey={omdb_key}")

    query_urls.append(f"https://www.omdbapi.com/?t={encoded_title}&apikey={omdb_key}")

    headers = {"User-Agent": "Mozilla/5.0"}
    for url in query_urls:
        try:
            async with session.get(url, headers=headers, timeout=3) as resp:
                data = await resp.json(content_type=None)

                if data.get("Response") == "True":
                    normalized_scores: List[float] = []

                    # Parse IMDb score
                    if imdb_rating := data.get("imdbRating"):
                        if imdb_rating.lower() == "tbd":
                            scores_data["imdb"] = f"[TBD]({scores_data['imdb_url']})"
                        elif imdb_rating != "N/A":
                            try:
                                score_num = float(imdb_rating)
                                scores_data["imdb"] = f"[{score_num}/10]({scores_data['imdb_url']})"
                                normalized_scores.append(score_num)
                            except ValueError:
                                pass

                    # Parse Metacritic score & Rotten Tomatoes fallback rating array
                    found_meta = False
                    for r in data.get("Ratings", []):
                        source = r.get("Source", "")
                        val = r.get("Value", "").strip()

                        if source == "Metacritic":
                            found_meta = True
                            if val.lower() == "tbd":
                                scores_data["metacritic"] = f"[TBD]({scores_data['metacritic_url']})"
                            elif "/100" in val:
                                try:
                                    meta_num = float(val.split("/")[0])
                                    scores_data["metacritic"] = f"[{val}]({scores_data['metacritic_url']})"
                                    normalized_scores.append(meta_num / 10.0)
                                except ValueError:
                                    pass

                        elif source == "Rotten Tomatoes" and "%" in val:
                            rt_url = f"https://www.rottentomatoes.com/search?search={encoded_title}"
                            scores_data["rotten_tomatoes_fallback"] = f"[{val}]({rt_url})"

                    # Handle unindexed Metacritic states explicitly
                    if not found_meta or str(data.get("Metascore", "")).lower() == "tbd":
                        if scores_data["metacritic"] == "N/A":
                            scores_data["metacritic"] = f"[TBD]({scores_data['metacritic_url']})"

                    if normalized_scores:
                        scores_data["combined_average_10"] = round(sum(normalized_scores) / len(normalized_scores), 2)
                        return scores_data
        except Exception:
            pass

    return scores_data

# Incorporate TMDb metadata, critic ratings, and user reviews concurrently for a title
async def async_fetch_tmdb_metadata_and_reviews(
        aio_session: aiohttp.ClientSession,
        curl_session: AsyncSession,
        movie_title: str
) -> tuple[dict, bool]:
    tmdb_key = os.getenv("TMDB_API_KEY")
    search_title = clean_title_for_search(movie_title)
    current_year = str(datetime.now().year)

    default_data: Dict[str, Any] = {
        "year": current_year,
        "original_year": current_year,
        "runtime": "Unknown",
        "genre": "Unknown",
        "rating": "Unknown",
        "poster_url": "https://images.amctheatres.com/amc-website/static/images/fallback/poster-placeholder.png",
        "overview": "No overview available.",
        "cast": [],
        "director": "Unknown",
        "critic_scores": {
            "rotten_tomatoes": "N/A",
            "imdb": "N/A",
            "metacritic": "N/A",
            "combined_average_10": 0.0
        },
        "user_scores": {
            "tmdb_user_score": "N/A",
            "reviews": []
        }
    }

    if not tmdb_key:
        return default_data, True

    encoded_title = urllib.parse.quote(search_title)
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_key}&query={encoded_title}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with aio_session.get(search_url, headers=headers, timeout=4) as resp:
            search_data = await resp.json()
            results = search_data.get("results", [])

            if not results:
                return default_data, True

            movie_info = results[0]
            tmdb_id = movie_info.get("id")

            if vote_avg := movie_info.get("vote_average"):
                if vote_avg > 0:
                    default_data["user_scores"]["tmdb_user_score"] = f"{round(vote_avg * 10)}%"

            details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={tmdb_key}&append_to_response=credits,external_ids,release_dates"
            async with aio_session.get(details_url, headers=headers, timeout=4) as det_resp:
                det_data = await det_resp.json()

                rel_date = str(det_data.get("release_date") or "")
                orig_year = rel_date[:4] if len(rel_date) >= 4 else current_year
                default_data["year"] = current_year
                default_data["original_year"] = orig_year

                # Extract regional content rating certification
                rel_dates_data = det_data.get("release_dates", {}).get("results", [])
                for country in rel_dates_data:
                    if country.get("iso_3166_1") == "US":
                        for release in country.get("release_dates", []):
                            cert = release.get("certification")
                            if cert:
                                default_data["rating"] = cert
                                break

                imdb_id = det_data.get("external_ids", {}).get("imdb_id", "") or ""

                # Execute OMDb score fetch and RT scraper in parallel
                omdb_task = fetch_omdb_critic_scores(aio_session, imdb_id, search_title, orig_year)
                rt_task = fetch_rotten_tomatoes_score(curl_session, search_title, current_year, orig_year)

                omdb_scores, (rt_score_str, rt_healthy) = await asyncio.gather(omdb_task, rt_task)

                # Fall back to OMDb array score if web scraper returns N/A
                if rt_score_str == "N/A" and omdb_scores.get("rotten_tomatoes_fallback") != "N/A":
                    rt_score_str = omdb_scores["rotten_tomatoes_fallback"]

                omdb_scores.pop("rotten_tomatoes_fallback", None)
                default_data["critic_scores"] = omdb_scores
                default_data["critic_scores"]["rotten_tomatoes"] = rt_score_str

                # Normalize valid 10-point numeric scores to calculate aggregate average
                normalized: List[float] = []
                if imdb_str := omdb_scores.get("imdb"):
                    if imdb_str != "N/A" and "TBD" not in imdb_str:
                        if m := re.search(r"(\d\.\d)", imdb_str):
                            normalized.append(float(m.group(1)))

                if meta_str := omdb_scores.get("metacritic"):
                    if meta_str != "N/A" and "TBD" not in meta_str:
                        if m := re.search(r"(\d{1,3})", meta_str):
                            normalized.append(float(m.group(1)) / 10.0)

                if rt_score_str != "N/A" and "TBD" not in rt_score_str:
                    if m := re.search(r"(\d{1,3})%", rt_score_str):
                        normalized.append(float(m.group(1)) / 10.0)

                if normalized:
                    default_data["critic_scores"]["combined_average_10"] = round(sum(normalized) / len(normalized), 2)

                if run_mins := det_data.get("runtime"):
                    hrs, mins = divmod(run_mins, 60)
                    default_data["runtime"] = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"

                if genres := det_data.get("genres"):
                    default_data["genre"] = ", ".join([g["name"] for g in genres[:3]])

                if poster_path := det_data.get("poster_path"):
                    default_data["poster_url"] = f"{TMDB_IMAGE_BASE}{poster_path}"

                if overview := det_data.get("overview"):
                    default_data["overview"] = overview

                credits = det_data.get("credits", {})
                default_data["cast"] = [member["name"] for member in credits.get("cast", [])[:5]]

                for crew_member in credits.get("crew", []):
                    if crew_member.get("job") == "Director":
                        default_data["director"] = crew_member.get("name", "Unknown")
                        break

            # Ingest TMDb community user reviews
            reviews_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/reviews?api_key={tmdb_key}"
            async with aio_session.get(reviews_url, headers=headers, timeout=4) as rev_resp:
                rev_data = await rev_resp.json()

                raw_reviews: List[Dict[str, str]] = []
                for rev in rev_data.get("results", []):
                    author = rev.get("author_details", {}).get("username") or rev.get("author", "Audience Reviewer")
                    rating_val = rev.get("author_details", {}).get("rating")

                    author_score_str = f"{round(float(rating_val), 1)}/10.0" if rating_val is not None else "N/A"
                    content = str(rev.get("content") or "").strip()
                    rev_url = rev.get("url", f"https://www.themoviedb.org/movie/{tmdb_id}")

                    if content:
                        formatted_text = truncate_review_with_inline_link(content, rev_url)
                        raw_reviews.append({
                            "author_score": author_score_str,
                            "reviewer": author,
                            "text": formatted_text
                        })

                default_data["user_scores"]["reviews"] = random.sample(raw_reviews, min(len(raw_reviews), 5))

            return default_data, rt_healthy

    except Exception as e:
        print(f"Async Metadata Fetch Error for {movie_title}: {e}")

    return default_data, True