import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import scraper

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Gateway connection established.')
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s).')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.tree.command(name="ping", description="Regression test for gateway connectivity.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! The Gateway is online.", ephemeral=True)

@bot.tree.command(name="testscrape", description="Tests the aiohttp and BeautifulSoup scraping foundation.")
async def testscrape(interaction: discord.Interaction):
    # Network requests take time; defer the interaction to prevent Discord's 3-second timeout error
    await interaction.response.defer(ephemeral=True)

    # Await the external scraping function
    result = await scraper.fetch_sample_data()

    # Return the scraped payload to the user
    await interaction.followup.send(f"**Scraper Results:**\n{result}")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing from the .env file.")
    else:
        bot.run(TOKEN)