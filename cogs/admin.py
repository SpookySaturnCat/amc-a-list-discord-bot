import json
import os
import scraper
import discord
from discord import app_commands
from discord.ext import commands

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")

def save_config(data: dict):
    # Utility function to update data/config.json.
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_config() -> dict:
    # Utility function to read data/config.json.
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def theater_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        # Fast local typeahead search backing the /set_theater command.
        theaters = scraper.load_cached_theaters()
        choices = []

        # Filter cached theater list matching user input string
        for theater in theaters:
            if current.lower() in theater["name"].lower():
                choices.append(app_commands.Choice(name=theater["name"], value=theater["url"]))
            if len(choices) >= 25:  # Discord limits autocomplete options to 25 items max
                break

        return choices

    @app_commands.command(name="set_theater", description="Configure the primary AMC theater location for this server.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.autocomplete(theater=theater_autocomplete)
    async def set_theater(self, interaction: discord.Interaction, theater: str):
        """Restricted admin command setting active theater location state."""
        # Defer interaction to avoid timeouts during file operations
        await interaction.response.defer(ephemeral=True)

        # Retrieve human-readable theater name matching selected URL
        cached_theaters = scraper.load_cached_theaters()
        selected_record = next((t for t in cached_theaters if t["url"] == theater), None)

        display_name = selected_record["name"] if selected_record else theater

        # Update configuration state file
        config = load_config()
        config["theater_url"] = theater
        config["theater_name"] = display_name
        save_config(config)

        embed = discord.Embed(
            title="Configuration Updated",
            description=f"Primary server theater successfully set to:\n**{display_name}**\n`{theater}`",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @set_theater.error
    async def set_theater_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Error handler catching missing RBAC permissions.
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Administrator permissions to use this command.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))