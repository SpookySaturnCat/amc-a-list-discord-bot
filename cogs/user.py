import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional
import discord
from discord import app_commands
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_FILE = os.path.join(DATA_DIR, "weekly_schedule.json")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def get_cached_schedule() -> Dict[str, Any]:
    # Safely reads the cached weekly schedule from disk.
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"updating": False, "movies": []}

def calculate_target_date(last_updated_iso: str, selected_day_name: str) -> str:
    # Computes the DD/MM/YYYY date for the requested weekday relative to cache generation time.
    try:
        base_dt = datetime.fromisoformat(last_updated_iso)
    except ValueError:
        base_dt = datetime.now()

    target_idx = WEEKDAYS.index(selected_day_name)
    base_idx = base_dt.weekday()

    days_ahead = (target_idx - base_idx) % 7
    target_date = base_dt + timedelta(days=days_ahead)

    return target_date.strftime("%d/%m/%Y")

def sanitize_metadata(genre: Optional[str], rating: Optional[str]) -> Tuple[str, str]:
    # Sanitizes raw metadata values to ensure explicit 'Unknown' representations.
    clean_genre = genre if genre and genre.upper() not in ["GENERAL", "N/A", "NONE"] else "Unknown"
    clean_rating = rating if rating and rating.upper() not in ["N/A", "NONE"] else "Unknown"
    return clean_genre, clean_rating

def filter_future_showtimes(target_date_str: str, raw_times: List[str]) -> List[str]:
    # Filters out showtimes that have already passed relative to the current local time.
    future_times = []
    now = datetime.now()

    try:
        day, month, year = map(int, target_date_str.split('/'))
        target_date = datetime(year, month, day)
    except ValueError:
        return raw_times

    # If the target date is entirely in the past, return empty
    if target_date.date() < now.date():
        return []

    for t in raw_times:
        try:
            # Strip spaces/weird unicode spaces for parsing
            clean_t = t.replace(" ", "").replace(" ", "").lower()
            parsed_time = datetime.strptime(clean_t, "%I:%M%p").time()
            showtime_dt = datetime.combine(target_date.date(), parsed_time)

            if showtime_dt > now:
                future_times.append(t)
        except ValueError:
            # If parsing fails on an unusual string format, keep it to be safe
            future_times.append(t)
    return future_times

def build_movie_embeds(movie: Dict[str, Any]) -> List[discord.Embed]:
    # Returns a list of embeds for a single movie to bypass 6,000-character limits.
    title = movie.get("title", "Unknown Title")
    genre, rating = sanitize_metadata(movie.get("genre"), movie.get("rating"))
    poster_url = movie.get("poster_url")

    def create_base_embed(part: int = 1) -> discord.Embed:
        # Helper to spawn a fresh embed card.
        display_title = title if part == 1 else f"{title} (Part {part})"
        card = discord.Embed(
            title=display_title,
            description=f"**Genre:** {genre} | **Rating:** {rating}",
            color=discord.Color.dark_red()
        )
        if poster_url:
            card.set_thumbnail(url=poster_url)
        return card

    raw_times = movie.get("showtimes", [])
    if not raw_times:
        card = create_base_embed()
        card.add_field(name="Showtimes", value="No upcoming showtimes", inline=False)
        return [card]

    embeds = []
    current_embed = create_base_embed()
    current_embed_chars = len(current_embed.title) + len(current_embed.description)

    current_field_value = []
    current_field_chars = 0
    field_count = 0
    part = 1

    for t in raw_times:
        formatted_t = f"`{t}`"
        added_length = len(formatted_t) + (3 if current_field_value else 0)

        # Check if need a new Field (1,024 char limit) is needed
        if current_field_chars + added_length > 1024:
            field_name = "Showtimes" if field_count == 0 else "Showtimes (Cont.)"
            chunk_str = " | ".join(current_field_value)
            current_embed.add_field(name=field_name, value=chunk_str, inline=False)
            current_embed_chars += len(field_name) + len(chunk_str)

            field_count += 1
            current_field_value = [formatted_t]
            current_field_chars = len(formatted_t)

            # Check if a new Embed (6,000 char limit or 25 field limit) is needed
            if current_embed_chars > 5500 or field_count >= 25:
                embeds.append(current_embed)
                part += 1
                current_embed = create_base_embed(part)
                current_embed_chars = len(current_embed.title) + len(current_embed.description)
                field_count = 0
        else:
            current_field_value.append(formatted_t)
            current_field_chars += added_length

    # Append any leftover showtimes
    if current_field_value:
        field_name = "Showtimes" if field_count == 0 else "Showtimes (Cont.)"
        current_embed.add_field(name=field_name, value=" | ".join(current_field_value), inline=False)
        embeds.append(current_embed)

    return embeds

class UserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def movie_autocomplete(self, interaction: discord.Interaction, current: str) -> List[
        app_commands.Choice[str]]:
        # Provides autocomplete suggestions for active movies in the weekly schedule cache.
        cache = get_cached_schedule()
        if cache.get("updating"):
            return []

        all_movies = cache.get("movies", [])
        unique_titles = list(set(m.get("title") for m in all_movies if m.get("title")))

        matches = [title for title in unique_titles if current.lower() in title.lower()]
        return [app_commands.Choice(name=title, value=title) for title in matches[:25]]

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
        # Retrieves and embeds the operational schedule of all movies playing on a specific day.
        is_ephemeral = str(visible_to_all).strip().lower() != "true"
        await interaction.response.defer(ephemeral=is_ephemeral)

        cache = get_cached_schedule()
        if cache.get("updating"):
            await interaction.followup.send("**Schedule Refreshing:** Please wait for data to refresh.",
                                            ephemeral=True)
            return

        target_day = week_day.value
        target_prefix = target_day[:3].lower()

        day_movies = [
            m for m in cache.get("movies", [])
            if m.get("day", "").lower() == target_day.lower() or m.get("day", "").lower().startswith(target_prefix)
        ]

        if not day_movies:
            await interaction.followup.send(f"No showtimes found in cache for **{target_day}**.",
                                            ephemeral=is_ephemeral)
            return

        formatted_date = calculate_target_date(cache.get("last_updated", ""), target_day)

        # Build the header
        header_embed = discord.Embed(
            title=f"AMC Schedule: {target_day}",
            description=f"Showing upcoming movies scheduled for **{formatted_date}**.",
            color=discord.Color.red()
        )

        # Flatten all dynamically generated movie embeds into a single list
        all_embeds = [header_embed]
        for m in day_movies:
            # Run the raw times through our time filter
            future_times = filter_future_showtimes(formatted_date, m.get("showtimes", []))

            # Overwrite the showtimes array in memory with the filtered list, then build
            m["showtimes"] = future_times
            all_embeds.extend(build_movie_embeds(m))

        # Safely chunk by BOTH 10-embeds max AND 6,000-characters max per message
        current_chunk = []
        current_chunk_chars = 0

        for embed in all_embeds:
            embed_chars = len(embed.title or "") + len(embed.description or "")
            for field in embed.fields:
                embed_chars += len(field.name) + len(field.value)

            if len(current_chunk) >= 10 or (current_chunk_chars + embed_chars > 5800):
                await interaction.followup.send(embeds=current_chunk, ephemeral=is_ephemeral)
                current_chunk = [embed]
                current_chunk_chars = embed_chars
            else:
                current_chunk.append(embed)
                current_chunk_chars += embed_chars

        # Send any remaining chunks
        if current_chunk:
            await interaction.followup.send(embeds=current_chunk, ephemeral=is_ephemeral)

    @app_commands.command(name="movies", description="View upcoming showtimes for a specific movie this week.")
    @app_commands.describe(visible_to_all="Type 'true' to make this message visible to all users.")
    @app_commands.autocomplete(movie_title=movie_autocomplete)
    async def movies(
            self,
            interaction: discord.Interaction,
            movie_title: str,
            visible_to_all: Optional[str] = None
    ) -> None:
        # Looks up a specific movie to see when it plays throughout the week, filtering out past showtimes.
        is_ephemeral = str(visible_to_all).strip().lower() != "true"
        await interaction.response.defer(ephemeral=is_ephemeral)

        cache = get_cached_schedule()
        if cache.get("updating"):
            await interaction.followup.send("**Schedule Refreshing:** Please wait for data to refresh.",
                                            ephemeral=True)
            return

        all_movies = cache.get("movies", [])
        last_updated = cache.get("last_updated", "")

        movie_entries = [m for m in all_movies if m.get("title", "").lower() == movie_title.lower()]
        if not movie_entries:
            await interaction.followup.send(f"Could not find upcoming showtimes for **{movie_title}**.",
                                            ephemeral=is_ephemeral)
            return

        base_meta = movie_entries[0]
        genre, rating = sanitize_metadata(base_meta.get("genre"), base_meta.get("rating"))

        card = discord.Embed(
            title=f"Upcoming Showtimes: {base_meta.get('title')}",
            description=f"**Genre:** {genre} | **Rating:** {rating}\n*Showing only future times for the active schedule week.*",
            color=discord.Color.red()
        )

        if poster_url := base_meta.get("poster_url"):
            card.set_thumbnail(url=poster_url)

        has_future_showings = False

        for m in movie_entries:
            day_name = m.get("day", "")
            formatted_date = calculate_target_date(last_updated, day_name)
            future_times = filter_future_showtimes(formatted_date, m.get("showtimes", []))

            if future_times:
                has_future_showings = True
                card.add_field(name=f"{day_name} ({formatted_date})",
                               value=" | ".join([f"`{t}`" for t in future_times]), inline=False)

        if not has_future_showings:
            await interaction.followup.send(f"There are no *upcoming* showtimes left for **{movie_title}** this week.",
                                            ephemeral=is_ephemeral)
            return

        await interaction.followup.send(embed=card, ephemeral=is_ephemeral)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserCog(bot))