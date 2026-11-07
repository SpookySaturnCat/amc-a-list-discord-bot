import asyncio
import os
import tasks
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Initialize Environment and Intents
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook() -> None:
    # Loads cogs and initializes background tasks on startup.
    await bot.load_extension("cogs.admin")
    await bot.load_extension("cogs.user")

    # Start the background daemon for weekly schedule caching
    tasks.schedule_updater_task.start()

@bot.event
async def on_ready() -> None:
    # Fires when the bot has successfully connected to the gateway.
    print('Gateway connection established.')
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s).')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.tree.command(name="force_refresh", description="Admin override to populate weekly_schedule.json manually.")
@app_commands.checks.has_permissions(administrator=True)
async def force_refresh(interaction: discord.Interaction) -> None:
    # Manually forces an update of the SerpApi/OMDb cache data.
    await interaction.response.defer(ephemeral=True)

    # Run the blocking network task in a separate thread so it doesn't freeze the bot
    res = await asyncio.to_thread(tasks.fetch_and_cache_weekly_showtimes)

    movie_count = len(res.get('movies', []))
    await interaction.followup.send(f" Cache updated manually. Movies parsed: {movie_count}", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing from the .env file.")
    else:
        bot.run(TOKEN)