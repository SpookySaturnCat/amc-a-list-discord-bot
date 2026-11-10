import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import discord
from discord import app_commands
from discord.ext import commands

# Path setup and constants
DATA_DIR = os.path.join(str(os.path.dirname(__file__)), "..", "data")
CACHE_FILE = os.path.join(DATA_DIR, "movie_schedule_and_metadata.json")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Read stored schedule payload from local JSON cache
def get_cached_data() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                res: Dict[str, Any] = json.load(f)
                return res
        except Exception:
            pass
    return {"updating": False, "schedule": [], "metadata": {}}

# Calculate target DD/MM/YYYY date relative to cache generation timestamp
def calculate_target_date(last_updated_iso: str, selected_day_name: str) -> str:
    try:
        base_dt = datetime.fromisoformat(last_updated_iso)
    except ValueError:
        base_dt = datetime.now()

    target_idx = WEEKDAYS.index(selected_day_name)
    base_idx = base_dt.weekday()

    days_ahead = (target_idx - base_idx) % 7
    target_date = base_dt + timedelta(days=days_ahead)

    return target_date.strftime("%d/%m/%Y")

# Filter out showtimes that have already passed relative to system time
def filter_future_showtimes(target_date_str: str, raw_times: List[str]) -> List[str]:
    future_times: List[str] = []
    now = datetime.now()

    try:
        day, month, year = map(int, target_date_str.split('/'))
        target_date = datetime(year, month, day)
    except ValueError:
        return raw_times

    if target_date.date() < now.date():
        return []

    for t in raw_times:
        try:
            clean_t = t.replace(" ", "").lower()
            parsed_time = datetime.strptime(clean_t, "%I:%M%p").time()
            showtime_dt = datetime.combine(target_date.date(), parsed_time)

            if showtime_dt > now:
                future_times.append(t)
        except ValueError:
            future_times.append(t)
    return future_times

# Modular helper method to construct standardized base embeds and headers
def create_base_embed(
    title: str,
    meta: dict,
    subtitle_suffix: str = "",
    color: discord.Color = discord.Color.from_rgb(255, 182, 193)
) -> discord.Embed:
    year = meta.get("year", "Unknown")
    runtime = meta.get("runtime", "Unknown")
    genre = meta.get("genre", "Unknown")
    rating = meta.get("rating", "Unknown")
    poster = meta.get("poster_url")

    sub_header = f"**Genre:** {genre} | **Runtime:** {runtime} | **Rating:** {rating}"
    if subtitle_suffix:
        sub_header = f"{sub_header}\n{subtitle_suffix}"

    embed = discord.Embed(
        title=f"{title} ({year})",
        description=sub_header,
        color=color
    )
    if poster:
        embed.set_thumbnail(url=poster)
    return embed

# Construct Embed representation displaying aggregated critic ratings
def build_critic_review_embed(title: str, meta: dict) -> discord.Embed:
    critics = meta.get("critic_scores", {})
    avg_10 = float(critics.get("combined_average_10", 0.0) or 0.0)
    suffix = f"**Combined Critic Average:** {avg_10:.2f} / 10.00"

    embed = create_base_embed(
        title=f"{title} — Critic Ratings",
        meta=meta,
        subtitle_suffix=suffix,
        color=discord.Color.from_rgb(70, 130, 180)
    )

    embed.add_field(name="Rotten Tomatoes", value=critics.get("rotten_tomatoes", "N/A"), inline=True)
    embed.add_field(name="IMDb", value=critics.get("imdb", "N/A"), inline=True)
    embed.add_field(name="Metacritic", value=critics.get("metacritic", "N/A"), inline=True)
    return embed

# Construct Embed representation displaying TMDb audience score and sample reviews
def build_user_review_embed(title: str, meta: dict) -> discord.Embed:
    user_data = meta.get("user_scores", {})
    tmdb_score = user_data.get("tmdb_user_score", "N/A")
    reviews = user_data.get("reviews", [])
    suffix = f"**TMDB Audience Score:** {tmdb_score}"

    embed = create_base_embed(
        title=f"{title} — User Reviews",
        meta=meta,
        subtitle_suffix=suffix,
        color=discord.Color.from_rgb(255, 215, 0)
    )

    if not reviews:
        embed.add_field(name="No Reviews", value="No cached user reviews available for this title.", inline=False)
    else:
        for rev in reviews[:5]:
            score_str = rev.get("author_score", "N/A")
            reviewer = rev.get("reviewer", "Audience Member")
            text = rev.get("text", "")
            embed.add_field(name=f"Author: {reviewer} | Score: {score_str}", value=text, inline=False)

    return embed

# Interactive Discord UI View providing select dropdown navigation between movie details
class MovieDetailView(discord.ui.View):
    def __init__(self, title: str, meta: dict, schedule_entries: list, last_updated: str):
        super().__init__(timeout=180)
        self.title = title
        self.meta = meta
        self.schedule_entries = schedule_entries
        self.last_updated = last_updated

    @discord.ui.select(
        placeholder="Choose a view mode...",
        options=[
            discord.SelectOption(label="Upcoming Showtimes", value="showtimes"),
            discord.SelectOption(label="Cast & Crew", value="cast"),
            discord.SelectOption(label="Critic Reviews", value="critic_reviews"),
            discord.SelectOption(label="User Reviews", value="user_reviews")
        ]
    )
    # Update active interaction message embed based on select dropdown choice
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]

        if choice == "showtimes":
            embed = create_base_embed(
                title=f"{self.title} — Showtimes",
                meta=self.meta,
                color=discord.Color.from_rgb(255, 182, 193)
            )

            has_showings = False
            for entry in self.schedule_entries:
                day_name = str(entry.get("day") or "")
                formatted_date = calculate_target_date(self.last_updated, day_name)
                future_times = filter_future_showtimes(formatted_date, entry.get("showtimes") or [])

                if future_times:
                    has_showings = True
                    embed.add_field(
                        name=f"{day_name} ({formatted_date})",
                        value=" | ".join([f"`{t}`" for t in future_times]),
                        inline=False
                    )

            if not has_showings:
                embed.add_field(name="Showtimes", value="No upcoming showtimes remaining this week.", inline=False)

        elif choice == "cast":
            director = self.meta.get("director", "Unknown")
            cast_list = self.meta.get("cast", [])
            overview = self.meta.get("overview", "No overview provided.")

            embed = create_base_embed(
                title=f"{self.title} — Cast & Details",
                meta=self.meta,
                subtitle_suffix=f"\n*{overview}*",
                color=discord.Color.from_rgb(186, 85, 211)
            )

            embed.add_field(name="Director", value=director, inline=True)
            embed.add_field(
                name="Top Cast",
                value="\n".join([f"• {actor}" for actor in cast_list]) if cast_list else "Cast info unavailable.",
                inline=False
            )

        elif choice == "critic_reviews":
            embed = build_critic_review_embed(self.title, self.meta)

        elif choice == "user_reviews":
            embed = build_user_review_embed(self.title, self.meta)

        await interaction.response.edit_message(embed=embed, view=self)

# Cog grouping end-user commands for movie lookups, schedules, and reviews
class UserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Typeahead search handler populating Discord slash command options from cached titles
    async def movie_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        cache = get_cached_data()
        if cache.get("updating"):
            return []

        all_movies = list((cache.get("metadata") or {}).keys())
        matches = [t for t in all_movies if current.lower() in t.lower()]
        return [app_commands.Choice(name=t, value=t) for t in matches[:25]]

    # Slash command querying metadata and showtimes for a specific title
    @app_commands.command(name="movie", description="View movie information with interactive options.")
    @app_commands.describe(visible_to_all="Type 'true' to make this message visible to all users.")
    @app_commands.autocomplete(movie_title=movie_autocomplete)
    async def movie(
            self,
            interaction: discord.Interaction,
            movie_title: str,
            visible_to_all: Optional[str] = None
    ) -> None:
        is_ephemeral = str(visible_to_all).strip().lower() != "true"
        await interaction.response.defer(ephemeral=is_ephemeral)

        cache = get_cached_data()
        metadata_map: Dict[str, Any] = cache.get("metadata") or {}
        schedule_list: List[Dict[str, Any]] = cache.get("schedule") or []
        last_updated = str(cache.get("last_updated") or "")

        meta = None
        matched_title = movie_title
        for title_key, data in metadata_map.items():
            if title_key.lower() == movie_title.lower():
                meta = data
                matched_title = title_key
                break

        if not meta:
            await interaction.followup.send(f"Could not find information for **{movie_title}**.", ephemeral=is_ephemeral)
            return

        schedule_entries = [m for m in schedule_list if str(m.get("title") or "").lower() == matched_title.lower()]

        embed = create_base_embed(
            title=matched_title,
            meta=meta,
            subtitle_suffix=f"\n*{meta.get('overview', '')}*"
        )

        view = MovieDetailView(matched_title, meta, schedule_entries, last_updated)
        await interaction.followup.send(embed=embed, view=view, ephemeral=is_ephemeral)

    # Slash command retrieving theater showtimes scheduled for a specific weekday
    @app_commands.command(name="showtimes", description="View all movies playing on a specific day.")
    @app_commands.describe(visible_to_all="Type 'true' to make this message visible to all users.")
    @app_commands.choices(week_day=[
        app_commands.Choice(name=day, value=day) for day in WEEKDAYS
    ])
    async def showtimes(
            self,
            interaction: discord.Interaction,
            week_day: app_commands.Choice[str],
            visible_to_all: Optional[str] = None
    ) -> None:
        is_ephemeral = str(visible_to_all).strip().lower() != "true"
        await interaction.response.defer(ephemeral=is_ephemeral)

        cache = get_cached_data()
        if cache.get("updating"):
            await interaction.followup.send("Schedule Refreshing: Please wait for data to refresh.", ephemeral=True)
            return

        target_day = week_day.value
        schedule_list: List[Dict[str, Any]] = cache.get("schedule") or []
        metadata_map: Dict[str, Any] = cache.get("metadata") or {}
        last_updated = str(cache.get("last_updated") or "")

        day_entries = [m for m in schedule_list if str(m.get("day") or "").lower() == target_day.lower()]

        if not day_entries:
            await interaction.followup.send(f"No showtimes found in cache for **{target_day}**.", ephemeral=is_ephemeral)
            return

        formatted_date = calculate_target_date(last_updated, target_day)

        embed = discord.Embed(
            title=f"AMC Schedule: {target_day}",
            description=f"Showing upcoming movies scheduled for **{formatted_date}**.",
            color=discord.Color.red()
        )

        for entry in day_entries:
            title = str(entry.get("title") or "Unknown")
            meta = metadata_map.get(title) or {}
            genre = meta.get("genre", "Unknown")
            runtime = meta.get("runtime", "Unknown")
            rating = meta.get("rating", "Unknown")

            future_times = filter_future_showtimes(formatted_date, entry.get("showtimes") or [])
            if future_times:
                times_str = " | ".join([f"`{t}`" for t in future_times])
                embed.add_field(
                    name=f"{title} ({runtime})",
                    value=f"**Genre:** {genre} | **Rating:** {rating}\n{times_str}",
                    inline=False
                )

        await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)

    # Slash command displaying audience reviews or aggregate critic ratings
    @app_commands.command(name="reviews", description="View user or critic reviews for a specific movie.")
    @app_commands.describe(
        movie_title="The title of the movie.",
        review_type="Select Critic Reviews or User Reviews.",
        visible_to_all="Type 'true' to make this message visible to all users."
    )
    @app_commands.choices(review_type=[
        app_commands.Choice(name="Critic Reviews", value="critic"),
        app_commands.Choice(name="User Reviews", value="user")
    ])
    @app_commands.autocomplete(movie_title=movie_autocomplete)
    async def reviews(
            self,
            interaction: discord.Interaction,
            movie_title: str,
            review_type: app_commands.Choice[str],
            visible_to_all: Optional[str] = None
    ) -> None:
        is_ephemeral = str(visible_to_all).strip().lower() != "true"
        await interaction.response.defer(ephemeral=is_ephemeral)

        cache = get_cached_data()
        metadata_map: Dict[str, Any] = cache.get("metadata") or {}

        meta = None
        matched_title = movie_title
        for title_key, data in metadata_map.items():
            if title_key.lower() == movie_title.lower():
                meta = data
                matched_title = title_key
                break

        if not meta:
            await interaction.followup.send(f"No cached data available for **{movie_title}**.", ephemeral=is_ephemeral)
            return

        mode = review_type.value
        if mode == "critic":
            embed = build_critic_review_embed(matched_title, meta)
        else:
            embed = build_user_review_embed(matched_title, meta)

        await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserCog(bot))