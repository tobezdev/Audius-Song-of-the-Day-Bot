"""
Audius Song-of-the-Day cog.

Fetches a daily track from the Audius API, persists it, and posts an embed to the configured channel,
a ping of the configured role and a link to listen to the track on Audius (integrates with App on Mobile/Desktop
and falls back to opening in browser).
"""

import logging
import os

import aiohttp
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ext import tasks

from db import get_config, get_current_sotd, get_sotd_history, save_sotd

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")


class SOTDView(discord.ui.View):
    """View with a 'Listen on Audius!' link button."""

    def __init__(self, permalink: str | None = None):
        super().__init__(timeout=None)
        if permalink:
            self.add_item(discord.ui.Button(
                label="Listen on Audius!",
                url=permalink,
                style=discord.ButtonStyle.link,
            ))


class AudiusSOTD(commands.Cog):
    """Background task and slash commands for the daily Audius track."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.update_sotd.start()

    def cog_unload(self) -> None:
        """Cancel the background loop when the cog is unloaded."""
        self.update_sotd.cancel()

    # API helper
    async def fetch_sotd_from_api(self) -> dict:
        """Fetch the latest SOTD data from the Audius API."""
        if not API_URL:
            logger.error("API_URL environment variable is not set.")
            return {"Error": "API_URL environment variable is not set."}

        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    raw = await response.json()
                    # The Audius API wraps results in a "data" key
                    tracks = raw.get("data", raw) if isinstance(raw, dict) else raw
                    if not tracks or (isinstance(tracks, list) and len(tracks) == 0):
                        logger.error("SOTD API returned an empty result set.")
                        return {"Error": "SOTD API returned an empty result set."}

                    track = tracks[0] if isinstance(tracks, list) else tracks
                    return {
                        "track_id": track["id"],
                        "track_title": track["title"],
                        "artist_name": track["user"]["name"],
                        "artist_handle": track["user"]["handle"],
                        "genre": track["genre"],
                        "release_date": track["release_date"],
                        "play_count": track["play_count"],
                        "repost_count": track["repost_count"],
                        "favorite_count": track["favorite_count"],
                        "permalink": f"https://audius.co{track['permalink']}",
                        "artwork_url": track["artwork"]["1000x1000"],
                        "tags": track["tags"].split(",") if track["tags"] else [],
                    }
                else:
                    logger.error(f"Failed to fetch SOTD: {response.status}")
                    return {"Error": f"Failed to fetch SOTD: {response.status}"}

    # Background task
    @tasks.loop(hours=24)
    async def update_sotd(self) -> None:
        """Fetch, persist, and announce a new SOTD once per day."""
        sotd_data = await self.fetch_sotd_from_api()
        if "Error" in sotd_data:
            logger.error(sotd_data["Error"])
            return

        # Only save if the track actually changed
        current = await get_current_sotd()
        if current and current["track_id"] == sotd_data["track_id"]:
            logger.info("SOTD unchanged — skipping DB insert.")
            return

        await save_sotd(sotd_data)
        logger.info(f"Updated SOTD: {sotd_data['track_title']} by {sotd_data['artist_name']}")

        channel_id = await get_config("sotd_channel_id")
        role_id = await get_config("sotd_role_id")

        channel = self.bot.get_channel(int(channel_id)) if channel_id else None
        role = None

        if role_id and channel:
            channel = self.bot.get_channel(int(channel_id)) if channel_id else None
            if channel and isinstance(channel, discord.TextChannel):
                role = channel.guild.get_role(int(role_id))

        if channel and isinstance(channel, discord.TextChannel):
            embed = discord.Embed(
                title="New Song of the Day!",
                description=(
                    f"**{sotd_data['track_title']}** by **{sotd_data['artist_name']}**\n"
                    f"Genre: {sotd_data['genre']}\n"
                    f"Release Date: {sotd_data['release_date']}\n"
                    f"Plays: {sotd_data['play_count']} | Reposts: {sotd_data['repost_count']} | Favorites: {sotd_data['favorite_count']}"
                ),
                color=discord.Color.random(),
            )
            embed.set_thumbnail(url=sotd_data["artwork_url"])
            view = SOTDView(permalink=sotd_data["permalink"])
            await channel.send(
                role.mention if role and isinstance(role, discord.Role) else "",
                embed=embed,
                view=view,
            )

    @update_sotd.before_loop
    async def before_update_sotd(self) -> None:
        """Wait for the bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()

    # Slash commands
    sotd = SlashCommandGroup("sotd", "Commands related to the Audius Song of the Day")

    @sotd.command(name="current", description="Get the current Song of the Day")
    async def current(self, ctx: discord.ApplicationContext) -> None:
        """Return the current SOTD, fetching from the API if none exists yet."""
        sotd_data = await get_current_sotd()

        if sotd_data is None:
            # DB is empty (first run) — try a live fetch & persist it
            sotd_data = await self.fetch_sotd_from_api()
            if "Error" in sotd_data:
                await ctx.respond(sotd_data["Error"])
                return
            await save_sotd(sotd_data)

        embed = discord.Embed(
            title=sotd_data["track_title"],
            description=(
                f"Artist: {sotd_data['artist_name']} (@{sotd_data['artist_handle']})\n"
                f"Genre: {sotd_data['genre']}\n"
                f"Release Date: {sotd_data['release_date']}\n"
                f"Plays: {sotd_data['play_count']} | Reposts: {sotd_data['repost_count']} | Favorites: {sotd_data['favorite_count']}"
            ),
            color=discord.Color.random(),
        )
        embed.set_thumbnail(url=sotd_data["artwork_url"])
        view = SOTDView(permalink=sotd_data["permalink"])
        await ctx.respond(embed=embed, view=view)

    @sotd.command(name="history", description="Show past Songs of the Day")
    async def history(self, ctx: discord.ApplicationContext) -> None:
        """Display the last 10 SOTD entries as an embed."""
        entries = await get_sotd_history(limit=10)
        if not entries:
            await ctx.respond("No SOTD history yet!", ephemeral=True)
            return

        lines = []
        for i, entry in enumerate(entries, start=1):
            if i >= 6 and len(entries) > 10:
                lines.append(f"...and {len(entries) - 5} more!")
                break
            lines.append(
                f"**{i}.** [{entry['track_title']}]({entry['permalink']}) — "
                f"{entry['artist_name']} (@{entry['artist_handle']})"
            )

        embed = discord.Embed(
            title="Song of the Day History",
            description="\n".join(lines),
            color=discord.Color.random(),
        )
        await ctx.respond(embed=embed)


def setup(bot: discord.Bot) -> None:
    """Register the AudiusSOTD cog."""
    bot.add_cog(AudiusSOTD(bot))