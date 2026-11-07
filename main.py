import os
import tasks
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.load_extension("cogs.admin")
    await bot.load_extension("cogs.user")
    # Start the Thursday 8:30 AM loop to collect weekly movie showing data
    tasks.schedule_updater_task.start()

@bot.event
async def on_ready():
    print(f'Gateway connection established.')
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s).')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.tree.command(name="force_refresh", description="Admin override to populate weekly_schedule.json manually.")
async def force_refresh(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    res = tasks.fetch_and_cache_weekly_showtimes()
    await interaction.followup.send(f"Cache updated manually. Movies parsed: {len(res.get('movies', []))}", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing from the .env file.")
    else:
        bot.run(TOKEN)