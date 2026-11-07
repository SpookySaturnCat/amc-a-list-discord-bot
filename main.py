import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables securely from .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize gateway with standard intents (NFR-6: No elevated message_content intent)
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Gateway connection established.')
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        # Syncing slash commands globally
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s).')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# Basic test command adhering to FR-3.5/3.6 (ephemeral by default)
@bot.tree.command(name="ping", description="Regression test for gateway connectivity.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! The AMC Coordinator Gateway is online.", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN is missing from the .env file.")
    else:
        bot.run(TOKEN)