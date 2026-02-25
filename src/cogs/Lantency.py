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
    @commands.slash_command(name="check-latency", description="Check the bot's latency.")
    async def check_latency(self, ctx: discord.ApplicationContext) -> None:
        """Check the bot's latency."""
        latency_ms = round(self.bot.latency * 1000)
        await ctx.respond(
            embed=discord.Embed(
                description=f"Pong! `{latency_ms}ms`",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
            delete_after=10,
        )


def setup(bot: discord.Bot) -> None:
    """Register the Ping cog."""
    bot.add_cog(Ping(bot))