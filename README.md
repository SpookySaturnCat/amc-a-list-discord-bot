# AMC Movie Planner Discord Bot

A lightweight, asynchronous Discord bot designed to streamline group movie outings. This bot dynamically ingests local AMC theater showtimes via SerpApi into a scheduled weekly JSON cache, enriches metadata (posters, ratings, genres) using zero-key API fallbacks, fetches real-time movie reviews via OMDb, and automates weekly polls while keeping your server chat clean using ephemeral slash commands with optional public visibility.

## Implementation Status

| Feature / Module | Status | Description                                                              |
| :--- | :--- |:-------------------------------------------------------------------------|
| **SerpApi Schedule Ingestion** | Implemented | Weekly fetching using `gl="us"` and `hl="en"` parameters.                |
| **JSON Schedule Cache** | Implemented | Persistent storage in `data/weekly_schedule.json`.                       |
| **Metadata Fallbacks** | Implemented | Zero-key enrichment for posters, genres, and ratings via OMDb/Wikipedia. |
| **Explicit Error Standards** | Implemented | Uses "Unknown" placeholders when data is unavailable.                    |
| **/showtimes Command** | Implemented | Day-based lookup with dynamic, limit-bypassing embed pagination.         |
| **/movies Command** | Implemented | Title-based lookup with autocomplete and past-showtime filtering.        |
| **/force_refresh Command** | Implemented | Manual admin override to rebuild schedule cache on demand.               |
| **Thursday 8:30 AM Daemon** | Implemented | Automated background task in `tasks.py` (`discord.ext.tasks`).           |
| **Theater Config Management** | Implemented | Dynamic configuration persistence in `data/config.json`.                 |
| **/set_theater Command** | Implemented | Admin configuration command to set target theater dynamically.           |
| **/upcoming Command** | In Progress | Upcoming release parser mapped to configured theater state.              |
| **/review Command** | In Progress | Real-time OMDb scores and review metadata aggregator.                    |
| **!information / !help Command** | In Progress | Guild help manual detailing commands, cache schedules, and usage flags.  |
| **Weekly Discord Polls** | In Progress | Automated native Discord poll creation in designated planning channel.   |
| **Automated Discord Events** | In Progress | Creation of native Discord Events based on winning poll results.         |
| **Discussion Threads** | In Progress | Automatic public thread creation linked to planning events.              |
| **Role Ping System** | In Progress | Dynamic `@movie goer` role mentions for group alerts.                    |

## Features

### Cost & Performance Optimization
- **Low API Footprint:** Utilizes a persistent weekly JSON cache (`data/weekly_schedule.json`) updated automatically every Thursday at 8:30 AM, restricting external calls to ~4 SerpApi queries per month.
- **US Regional Enforcement:** Enforces `gl="us"` and `hl="en"` API parameters to ensure localized, U.S. English schedules regardless of bot host geographic location.
- **Sub-Second Response Times:** Users read directly from local cached data, eliminating live scraping delay.

### Administrator Controls
- **Dynamic Theater Selection:** Use `/set_theater` to set your target local AMC theater string saved directly in `data/config.json`. (Implemented)
- **Manual Cache Override:** Administrators can invoke `/force_refresh` to manually rebuild the weekly schedule cache at any time. (Implemented)
- **Error Alerts:** If an API query fails or metadata extraction encounters errors, the bot fails gracefully and logs diagnostic output. (Implemented)

### User Commands
All user commands default to ephemeral (visible only to the user invoking them) to prevent chat clutter. Users can optionally append a visibility flag `true` to post the results publicly for the group to see.

- **`/showtimes [week_day] [visibility]`**: View all movies playing on a specific day of the active schedule week (Thursday through Wednesday). (Implemented)
  - **Dynamic Date Headers:** Displays exact DD/MM/YYYY calendar dates calculated relative to the weekly cache timestamp.
  - **Limitless Pagination Architecture:** Dynamically chunks showtime strings across fields (bypassing the 1,024-char limit), splits movies across multiple embeds (bypassing the 25-field limit), and batches sends across multiple messages (bypassing the 10-embed and 6,000-char limits) so that absolutely zero data is ever truncated, no matter how large the theater is.
  - **Compact Embed UI:** Uses `set_thumbnail()` to pin small ~80x80px poster graphics to embed corners without clogging chat channels.

- **`/movies [movie_title] [visibility]`**: Fetches upcoming showtimes for a specific film. (Implemented)
  - **Smart Autocomplete:** The `[movie_title]` parameter features Discord Autocomplete, suggesting currently playing movies at your active theater as you type.
  - **Time-Filtering:** Automatically filters out and hides showtimes that have already passed relative to the user's current local time.
  - **Accurate Metadata & Fallbacks:** Movie entries are enriched via OMDb and Wikipedia REST API lookups. Missing data is explicitly displayed as `Unknown`.

- **`/upcoming [visibility]`**: Fetches "Coming Soon" releases for the configured location. (In Progress)
- **`/review [movie_title] [visibility]`**: Pings the free OMDb API to fetch movie reviews and aggregate scores. (In Progress)
- **`!information / !help`**: Displays an interactive command guide, cache status, and privacy visibility instructions for server members. (In Progress)

### Automation
- **Weekly Movie Poll:** A background task using `discord.ext.tasks` wakes up every Thursday at 8:30 AM, pulls the upcoming week's showtimes, updates the cache, and posts a native Discord poll in your designated `#movie-planning` channel. (In Progress)
- **Automated Scheduling:** Dynamically generates Discord Events based on winning poll results. (In Progress)
- **Discussion Threads:** Automatically spins up dedicated public threads for movie coordination and spoiler-safe chatting. (In Progress)
- **Targeted Notifications:** Pings a specific `@movie goer` role for all polls, threads, and events to avoid server-wide notification fatigue. (In Progress)

## Tech Stack
- **Language:** Python 3.10+
- **Discord API:** `discord.py` (for Slash Commands, Prefix Commands, Autocomplete, Embeds, and Tasks)
- **Data Ingestion:** `serpapi` (Google Search Engine API wrapper)
- **Metadata Fallbacks:** Wikimedia REST API & OMDb Public Mirror (`urllib` JSON processing)
- **Networking:** `asyncio` and `urllib` (Asynchronous HTTP requests and thread-isolated network execution)
- **External APIs:** SerpApi, OMDb API

## Installation & Setup

**1. Prerequisites**
- Python 3.10 or higher
- A Discord Bot Token (Get one from the Discord Developer Portal)
- A SerpApi Key (Get one from SerpApi)
- A free OMDb API Key (Get one from OMDb)

**2. Clone the Repository**
```bash
git clone [https://github.com/yourusername/amc-discord-bot.git](https://github.com/yourusername/amc-discord-bot.git)
cd amc-discord-bot