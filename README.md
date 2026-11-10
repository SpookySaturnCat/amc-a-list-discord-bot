# AMC Movie Planner Discord Bot

A high-performance, asynchronous Discord bot designed to streamline group movie outings. This bot dynamically ingests local AMC theater showtimes via SerpApi into a scheduled weekly JSON cache, enriches metadata (posters, ratings, genres) using a multi-tier scraper fallback system, fetches movie reviews, and automates weekly polls while keeping your server chat clean using ephemeral slash commands with optional public visibility.

## Implementation Status

| Feature / Module | Status | Description |
| :--- | :--- | :--- |
| **SerpApi Schedule Ingestion** | Implemented | Weekly fetching using `gl="us"` and `hl="en"` parameters. |
| **Async JSON Schedule Cache** | Implemented | Persistent unified storage in `data/movie_schedule_and_metadata.json` updated in ~2.6s. |
| **Multi-Tier Scraper Fallbacks** | Implemented | Automated fallback chain (Rotten Tomatoes slug -> year-append -> OMDb array fallback). |
| **Explicit Error & TBD Standards** | Implemented | Explicitly renders `[TBD]` for unindexed scores and `Unknown` placeholders for missing metadata. |
| **/showtimes Command** | Implemented | Day-based lookup with dynamic, limit-bypassing embed pagination. |
| **/movies Command** | Implemented | Title-based lookup with autocomplete and past-showtime filtering. |
| **/reviews Command** | Implemented | Aggregate critic and user reviews fetcher with shared embed visual parity. |
| **/force_refresh Command** | Implemented | Manual admin override with in-channel Diagnostic Sentinel status alerts (`HEALTHY`/`BROKEN`). |
| **Thursday 8:30 AM Daemon** | Implemented | Automated background task in `tasks.py` (`discord.ext.tasks`). |
| **Theater Config Management** | Implemented | Dynamic configuration persistence in `data/config.json`. |
| **/set_theater Command** | Implemented | Admin configuration command to set target theater dynamically. |
| **/upcoming Command** | In Progress | Upcoming release parser mapped to configured theater state. |
| **!information / !help Command** | In Progress | Guild help manual detailing commands, cache schedules, and usage flags. |
| **Weekly Discord Polls** | In Progress | Automated native Discord poll creation in designated planning channel. |
| **Automated Discord Events** | In Progress | Creation of native Discord Events based on winning poll results. |
| **Discussion Threads** | In Progress | Automatic public thread creation linked to planning events. |
| **Role Ping System** | In Progress | Dynamic `@movie goer` role mentions for group alerts. |

## Features

### Cost & Performance Optimization
- **High-Performance Async Pipeline:** Fully non-blocking ingestion stack using `aiohttp` and `curl_cffi`, reducing full cache rebuild execution time from ~14.2s to ~2.63s.
- **Low API Footprint:** Utilizes a persistent weekly JSON cache (`data/movie_schedule_and_metadata.json`) updated automatically every Thursday at 8:30 AM, restricting external calls to ~4 SerpApi queries per month.
- **US Regional Enforcement:** Enforces `gl="us"` and `hl="en"` API parameters to ensure localized, U.S. English schedules regardless of bot host geographic location.
- **Sub-Second Response Times:** Users read directly from local cached data, eliminating live scraping delay.

### Administrator Controls
- **Dynamic Theater Selection:** Use `/set_theater` to set your target local AMC theater string saved directly in `data/config.json`. (Implemented)
- **Manual Cache Override:** Administrators can invoke `/force_refresh` to manually rebuild the weekly schedule cache on demand. (Implemented)
- **Diagnostic Sentinel:** Automated health reporting in `/force_refresh` status output that flags scrapers as `HEALTHY` or `BROKEN` and displays in-channel alerts if DOM structure changes. (Implemented)

### User Commands
All user commands default to ephemeral (visible only to the user invoking them) to prevent chat clutter. Users can optionally append a visibility flag `true` (`visible_to_all: true`) to post the results publicly for the group to see.

- **`/showtimes [week_day] [visible_to_all]`**: View all movies playing on a specific day of the active schedule week (Thursday through Wednesday). (Implemented)
  - **Dynamic Date Headers:** Displays exact DD/MM/YYYY calendar dates calculated relative to the weekly cache timestamp.
  - **Limitless Pagination Architecture:** Dynamically chunks showtime strings across fields (bypassing the 1,024-char limit), splits movies across multiple embeds (bypassing the 25-field limit), and batches sends across multiple messages (bypassing the 10-embed and 6,000-char limits) so that zero data is truncated.
  - **Compact Embed UI:** Uses `set_thumbnail()` to pin small ~80x80px poster graphics to embed corners without clogging chat channels.

- **`/movies [movie_title] [visible_to_all]`**: Fetches upcoming showtimes and metadata for a specific film. (Implemented)
  - **Smart Autocomplete:** The `[movie_title]` parameter features Discord Autocomplete, suggesting currently playing movies at your active theater as you type.
  - **Time-Filtering:** Automatically filters out and hides showtimes that have already passed relative to local time.
  - **Regex Sanitization:** Strips event tags ("Early Release", "Special Screening", "Anniversary") for clean metadata fetching.

- **`/reviews [movie_title] [review_type] [visible_to_all]`**: Displays aggregated critic scores (Rotten Tomatoes, IMDb, Metacritic, Combined 10-point Average) or TMDb audience reviews with identical visual styling to the `/movies` command tabs. (Implemented)
- **`/upcoming [visible_to_all]`**: Fetches "Coming Soon" releases for the configured location. (In Progress)
- **`!information / !help`**: Displays an interactive command guide, cache status, and privacy visibility instructions for server members. (In Progress)

### Automation
- **Weekly Web Scrape Caching** Asynchronously pulls data from the web to update `data/movie_schedule_and_metadata.json` every Thursday at 8:30 AM. (Implemented)
- **Weekly Movie Poll:** A background task using `discord.ext.tasks` wakes up every Thursday at 8:30 AM, posts a native Discord poll in your designated `#movie-planning` channel. (In Progress)
- **Automated Scheduling:** Dynamically generates Discord Events based on winning poll results. (In Progress)
- **Discussion Threads:** Automatically spins up dedicated public threads for movie coordination and spoiler-safe chatting. (In Progress)
- **Targeted Notifications:** Pings a specific `@movie goer` role for all polls, threads, and events to avoid server-wide notification fatigue. (In Progress)

## Tech Stack
- **Language:** Python 3.10+
- **Discord API:** `discord.py` (Slash Commands, Autocomplete, Embeds, Tasks)
- **Asynchronous Networking:** `aiohttp` and `curl_cffi` (TLS impersonation for scraper resilience)
- **HTML DOM Parser:** `BeautifulSoup4` (lxml / html.parser backend)
- **Data Ingestion:** `serpapi` (Google Search Engine API wrapper)
- **Metadata APIs:** TMDb API, OMDb API, and Wikipedia REST API

## Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- A Discord Bot Token (from Discord Developer Portal)
- A SerpApi Key
- An OMDb API Key
- A TMDb API Key

### 2. Clone the Repository
```bash
git clone [https://github.com/yourusername/amc-discord-bot.git](https://github.com/yourusername/amc-discord-bot.git)
cd amc-discord-bot