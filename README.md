# AMC Movie Planner Discord Bot

A lightweight, asynchronous Discord bot designed to streamline group movie outings. This bot dynamically scrapes local AMC theater data, fetches real-time movie reviews via OMDb, and automates weekly polls while keeping your server chat clean using ephemeral slash commands with optional public visibility.

## Features

### Administrator Controls
- **Dynamic Theater Selection:** Use `/set_theater` with Discord Autocomplete to instantly search and select your local AMC theater from a dynamically updated, locally cached list of all AMC locations.
- **Smart Caching:** The bot scrapes the AMC sitemap in the background to keep the theater database up to date without rate-limiting or slow response times.
- **Error Alerts:** If AMC updates their website structure and breaks the scraper, the bot fails gracefully and sends a direct message to the admin.

### User Commands
*All user commands default to ephemeral (visible only to the user invoking them) to prevent chat clutter. Users can optionally append a visibility flag `visable` to post the results publicly for the group to see.*
- **`/movies [visibility]`**: Scrapes the selected AMC theater's daily schedule and returns an embedded list of all movies playing that current day.
- **`/showtimes [movie] [date] [visibility]`**: Fetches showtimes for a specific film on a given date. 
  * The `[movie]` parameter features Discord Autocomplete, suggesting currently playing movies at your theater as you type. 
  * The `[date]` parameter accepts a simple `mm/dd` format and automatically infers the current year.
- **`/upcoming [visibility]`**: Fetches "Coming Soon" releases for the configured location.
- **`/review [movie_title] [visibility]`**: Pings the free OMDb API to fetch movie reviews.

### Automation
- **Weekly Movie Poll:** A background task using `discord.ext.tasks` wakes up once a week, pulls the upcoming weeks showtimes, and automatically posts a native Discord poll in your designated `#movie-planning` channel to help the group decide what to watch.
- **Automated Scheduling:** Dynamically generates Discord Events based on winning poll results.
- **Discussion Threads:** Automatically spins up dedicated public threads for movie coordination and spoiler-safe chatting.
- **Targeted Notifications:** Pings a specific @movie goer role for all polls, threads, and events to avoid server-wide notification fatigue.

## Tech Stack
- **Language:** Python 3.10+
- **Discord API:** `discord.py` (for Slash Commands, Autocomplete, and Tasks)
- **Web Scraping:** `BeautifulSoup4` with `lxml` parser (HTML/XML parsing)
- **Networking:** `aiohttp` and `urllib` (Asynchronous HTTP requests and thread-isolated network execution)
- **External APIs:** [OMDb API](https://www.omdbapi.com/)

## Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- A Discord Bot Token (Get one from the [Discord Developer Portal](https://discord.com/developers/applications))
- A free OMDb API Key (Get one [here](https://www.omdbapi.com/apikey.aspx))

### 2. Clone the Repository
```bash
git clone [https://github.com/yourusername/amc-discord-bot.git](https://github.com/yourusername/amc-discord-bot.git)
cd amc-discord-bot   