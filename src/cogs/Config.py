"""
Config cog — owner-only slash commands for reading, writing, and deleting key/value pairs in the db config table.
"""

import logging

import discord
from discord.ext import commands

from db import del_config, get_config, save_config

logger = logging.getLogger(__name__)


class Config(commands.Cog):
    """Config command to manage bot settings."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    config = discord.SlashCommandGroup("config", "Manage bot configuration settings.")

    @commands.is_owner()
    @config.command(name="get", description="Get the value of a config key.")
    async def get_config(self, ctx: discord.ApplicationContext, key: str) -> None:
        """Get the value of a config key."""
        value = await get_config(key)
        if value is not None:
            description = f"`{key}` = `{value}`"
        else:
            description = f"No config value found for key `{key}`."
        await ctx.respond(
            embed=discord.Embed(description=description, color=discord.Color.og_blurple()),
            ephemeral=True,
        )

    @commands.is_owner()
    @config.command(name="set", description="Set the value of a config key.")
    async def set_config(self, ctx: discord.ApplicationContext, key: str, value: str) -> None:
        """Set the value of a config key."""
        await save_config(key.lower(), value)
        await ctx.respond(
            embed=discord.Embed(
                description=f"`{key}` set to `{value}`.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )

    @commands.is_owner()
    @config.command(name="delete", description="Delete a config key.")
    async def delete_config(self, ctx: discord.ApplicationContext, key: str) -> None:
        """Delete a config key."""
        await del_config(key)
        await ctx.respond(
            embed=discord.Embed(
                description=f"Config key `{key}` deleted.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )


def setup(bot: discord.Bot) -> None:
    """Register the Config cog."""
    bot.add_cog(Config(bot))