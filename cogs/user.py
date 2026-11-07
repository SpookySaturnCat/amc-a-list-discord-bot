import json
import os
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_FILE = os.path.join(DATA_DIR, "weekly_schedule.json")

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def get_cached_schedule() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"updating": False, "movies": []}

def calculate_target_date(last_updated_iso: str, selected_day_name: str) -> str:
    """Calculates the dynamic DD/MM/YYYY date for the selected weekday relative to cache baseline."""
    try:
        base_dt = datetime.fromisoformat(last_updated_iso)
    except Exception:
        base_dt = datetime.now()

    target_idx = WEEKDAYS.index(selected_day_name)
    base_idx = base_dt.weekday()

    days_ahead = (target_idx - base_idx) % 7
    target_date = base_dt + timedelta(days=days_ahead)

    return target_date.strftime("%d/%m/%Y")


class UserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="movies", description="View local AMC schedule from Thursday-Thursday cache.")
    @app_commands.choices(week_day=[
        app_commands.Choice(name="Thursday", value="Thursday"),
        app_commands.Choice(name="Friday", value="Friday"),
        app_commands.Choice(name="Saturday", value="Saturday"),
        app_commands.Choice(name="Sunday", value="Sunday"),
        app_commands.Choice(name="Monday", value="Monday"),
        app_commands.Choice(name="Tuesday", value="Tuesday"),
        app_commands.Choice(name="Wednesday", value="Wednesday"),
    ])
    async def movies(
            self,
            interaction: discord.Interaction,
            week_day: app_commands.Choice[str],
            visibility: str = None
    ):
        is_ephemeral = True if not visibility or visibility.strip().lower() != "visable" else False
        await interaction.response.defer(ephemeral=is_ephemeral)

        cache = get_cached_schedule()

        if cache.get("updating"):
            await interaction.followup.send(
                "⏳ **Schedule Refreshing:** Please wait for data to refresh. Weekly updates occur Thursdays at 8:30 AM.",
                ephemeral=True
            )
            return

        all_movies = cache.get("movies", [])
        target_day = week_day.value
        target_prefix = target_day[:3].lower()

        day_movies = [
            m for m in all_movies
            if m.get("day", "").lower() == target_day.lower() or m.get("day", "").lower().startswith(target_prefix)
        ]

        if not day_movies:
            await interaction.followup.send(
                f"No showtimes found in cache for **{target_day}**. Run `/force_refresh` to update cache.",
                ephemeral=is_ephemeral
            )
            return

        last_updated_str = cache.get("last_updated", "")
        formatted_date = calculate_target_date(last_updated_str, target_day)

        embeds = []

        # Header Embed (No emoji, dynamic DD/MM/YYYY date display)
        header = discord.Embed(
            title=f"AMC Schedule: {target_day}",
            description=f"Showing movies scheduled for **{formatted_date}**.",
            color=discord.Color.red()
        )
        embeds.append(header)

        for m in day_movies[:9]:
            genre = m.get("genre", "Unknown")
            rating = m.get("rating", "Unknown")

            if not genre or genre.upper() in ["GENERAL", "N/A", "NONE"]:
                genre = "Unknown"

            if not rating or rating.upper() in ["N/A", "NONE"]:
                rating = "Unknown"

            card = discord.Embed(
                title=m["title"],
                description=f"**Genre:** {genre} | **Rating:** {rating}",
                color=discord.Color.dark_red()
            )
            times = " | ".join([f"`{t}`" for t in m["showtimes"][:8]])
            card.add_field(name="Showtimes", value=times if times else "No times listed", inline=False)

            if m.get("poster_url"):
                card.set_thumbnail(url=m["poster_url"])

            embeds.append(card)

        await interaction.followup.send(embeds=embeds, ephemeral=is_ephemeral)

async def setup(bot: commands.Bot):
    await bot.add_cog(UserCog(bot))