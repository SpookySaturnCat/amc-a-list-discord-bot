import os
import asyncio
import tasks
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment configuration variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize Discord client with default gateway intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Load application extension cogs and initialize background loop tasks
@bot.event
async def setup_hook() -> None:
    await bot.load_extension("cogs.admin")
    await bot.load_extension("cogs.user")
    tasks.schedule_updater_task.start()

# Handle post-connection initialization and slash command tree synchronization
@bot.event
async def on_ready() -> None:
    print('Gateway connection established.')
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s).')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# Administrative command to trigger an immediate off-schedule refresh of theater cache
@bot.tree.command(name="force_refresh", description="Admin override to populate movie_schedule_and_metadata.json manually.")
@app_commands.checks.has_permissions(administrator=True)
async def force_refresh(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)

    # Execute CPU/IO-bound schedule scraper in a separate thread pool
    res: dict = await asyncio.to_thread(tasks.fetch_and_cache_weekly_showtimes)

    showtimes_count = len(res.get('schedule') or [])
    movies_count = len(res.get('metadata') or {})
    elapsed = res.get('elapsed_seconds', 0.0)
    rt_status = str(res.get('rt_status') or 'healthy').lower()

    status_msg = (
        f"Cache updated manually in **{elapsed}s**.\n"
        f"Showtimes: {showtimes_count} | Movies: {movies_count}\n"
        f"Rotten Tomatoes Scraper: **{rt_status.upper()}**"
    )

    # Append warning payload if scraper health checks flagged issues
    if rt_status == "broken":
        status_msg += "\n⚠️ *Alert: Rotten Tomatoes DOM structure changed or Cloudflare TLS protection triggered. Scores returning N/A.*"

    await interaction.followup.send(status_msg, ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing from the .env file.")
    else:
        bot.run(TOKEN)