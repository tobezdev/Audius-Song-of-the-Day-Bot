"""
Latency cog — simple owner-only ping command for checking bot responsiveness.
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class Ping(commands.Cog):
    """Ping command to check bot latency."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @commands.is_owner()
    @commands.slash_command(name="ping", description="Check the bot's latency.")
    async def check(self, ctx: discord.ApplicationContext) -> None:
        """Check the bot's latency."""
        latency_ms = round(self.bot.latency * 1000)
        await ctx.respond(f"{latency_ms}ms", ephemeral=True, delete_after=10)


def setup(bot: discord.Bot) -> None:
    """Register the Ping cog."""
    bot.add_cog(Ping(bot))