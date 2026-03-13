"""
Config cog — owner-only slash commands for reading, writing, and deleting
key/value pairs in the db config table, and managing premium status.
"""

import logging

import discord
from discord.ext import commands

from db import (
    add_premium,
    del_config,
    del_guild_config,
    del_user_config,
    get_config,
    remove_premium,
    save_config,
)

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
        return

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
        return

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
        return

    @commands.is_owner()
    @config.command(name="add-premium", description="Grant premium status to a guild or user.")
    @discord.option("id", str, description="The guild or user ID to grant premium to.", parameter_name="target_id")
    async def add_premium_cmd(self, ctx: discord.ApplicationContext, target_id: str) -> None:
        """Grant premium status to a guild or user by ID."""
        await add_premium(int(target_id))
        await ctx.respond(
            embed=discord.Embed(
                description=f"Premium granted to `{target_id}`.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )
        return

    @commands.is_owner()
    @config.command(name="remove-premium", description="Revoke premium status from a guild or user.")
    @discord.option("id", str, description="The guild or user ID to revoke premium from.", parameter_name="target_id")
    async def remove_premium_cmd(self, ctx: discord.ApplicationContext, target_id: str) -> None:
        """Revoke premium status and clear premium settings for a guild or user."""
        await remove_premium(int(target_id))
        # Clean up any premium-only config (embed color) from both tables
        await del_guild_config(int(target_id), "sotd_embed_color")
        await del_user_config(int(target_id), "sotd_embed_color")
        await ctx.respond(
            embed=discord.Embed(
                description=f"Premium revoked from `{target_id}`. Any custom settings have been cleared.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )
        return

    @commands.is_owner()
    async def clear_preferences(self, ctx: discord.ApplicationContext, target_id: str) -> None:
        """Clear all config preferences for a guild or user."""
        await del_guild_config(int(target_id), "*")
        await del_user_config(int(target_id), "*")
        await ctx.respond(
            embed=discord.Embed(
                description=f"All config preferences cleared for `{target_id}`.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )
        return


def setup(bot: discord.Bot) -> None:
    """Register the Config cog."""
    bot.add_cog(Config(bot))