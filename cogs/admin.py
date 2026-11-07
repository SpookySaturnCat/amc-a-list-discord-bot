import json
import os
import discord
from discord import app_commands
from discord.ext import commands
import scraper

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")

def save_config(data: dict) -> None:
    # Utility function to update data/config.json
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_config() -> dict:
    # Utility function to read data/config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
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

        for theater in theaters:
            if current.lower() in theater["name"].lower():
                choices.append(app_commands.Choice(name=theater["name"], value=theater["url"]))
            if len(choices) >= 25:
                break

        return choices

    @app_commands.command(name="set_theater", description="Configure the primary AMC theater location for this server.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.autocomplete(theater=theater_autocomplete)
    async def set_theater(self, interaction: discord.Interaction, theater: str) -> None:
        # Restricted admin command setting active theater location state.
        await interaction.response.defer(ephemeral=True)

        cached_theaters = scraper.load_cached_theaters()
        selected_record = next((t for t in cached_theaters if t["url"] == theater), None)
        display_name = selected_record["name"] if selected_record else theater

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
    async def set_theater_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        # Error handler catching missing RBAC permissions.
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Administrator permissions to use this command.",
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))