"""
Audius Song-of-the-Day cog.

Fetches a daily track from the Audius API, persists it, and:
    - Posts an embed to every guild that has configured a SOTD channel.
    - DMs every user who has opted in via /sotd subscribe.

Guild setup (server owner or "SOTD Bot Admin" role required):
    /sotd channel <channel>  — set the channel for this server
    /sotd role [role]        — set an optional mention role (omit to clear)

User DM opt-in (works in DMs when bot is user-installed):
    /sotd subscribe          — receive daily SOTD in your DMs
    /sotd unsubscribe        — stop receiving daily SOTD in your DMs
* Users are auto-removed from DM list if they can no longer be DM'd 
(ie: app deauthorized, bot blocked or account deleted)
"""

import logging
import os
from datetime import datetime

import aiohttp
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ext import tasks

from db import (
    add_dm_user,
    del_guild_config,
    get_all_dm_users,
    get_all_guild_sotd_configs,
    get_current_sotd,
    get_sotd_history,
    is_dm_user,
    remove_dm_user,
    save_guild_config,
    save_sotd,
)

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


def _release_timestamp(date_str: str | None, style: str | None = None) -> str:
    """Convert an Audius ISO date string to a Discord long-date timestamp tag."""
    if not date_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if style is not None:
            return f"<t:{int(dt.timestamp())}:{style}>"
        return f"<t:{int(dt.timestamp())}>"
    except (ValueError, TypeError):
        return date_str


def _build_embed(sotd_data: dict, title: str = "New Song of the Day!") -> discord.Embed:
    """Build a standard SOTD embed from track data."""
    embed = discord.Embed(
        title=title,
        description=(
            f"**{sotd_data['track_title']}** by **{sotd_data['artist_name']}**\n"
            f"Genre: {sotd_data['genre']}\n"
            f"Released: {_release_timestamp(sotd_data['release_date'])} ({_release_timestamp(sotd_data['release_date'], style='R')})\n"
            f"Plays: {sotd_data['play_count']} | "
            f"Reposts: {sotd_data['repost_count']} | "
            f"Favorites: {sotd_data['favorite_count']}"
        ),
        color=discord.Color.og_blurple(),
    )
    embed.set_thumbnail(url=sotd_data["artwork_url"])
    return embed


async def _is_sotd_admin(ctx: discord.ApplicationContext) -> bool:
    """Return True if the invoker is the guild owner or has the 'SOTD Bot Admin' role."""
    if ctx.guild is None:
        return False
    if ctx.guild.owner_id == ctx.author.id:
        return True
    if not isinstance(ctx.author, discord.Member):
        return False
    admin_role = discord.utils.get(ctx.guild.roles, name="SOTD Bot Admin")
    return bool(admin_role and admin_role in ctx.author.roles)


class AudiusSOTD(commands.Cog):
    """Background task and slash commands for the daily Audius track."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.update_sotd.start()

    def cog_unload(self) -> None:
        """Cancel the background loop when the cog is unloaded."""
        self.update_sotd.cancel()

    # ------------------------------------------------------------------
    # API helper
    # ------------------------------------------------------------------

    async def fetch_sotd_from_api(self) -> dict:
        """Fetch the latest SOTD data from the Audius API."""
        if not API_URL:
            logger.error("API_URL environment variable is not set.")
            return {"Error": "API_URL environment variable is not set."}

        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    raw = await response.json()
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

    # ------------------------------------------------------------------
    # Background task
    # ------------------------------------------------------------------

    @tasks.loop(minutes=2)
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

        embed = _build_embed(sotd_data)
        view = SOTDView(permalink=sotd_data["permalink"])

        # --- Post to all configured guild channels ---
        guild_configs = await get_all_guild_sotd_configs()
        for cfg in guild_configs:
            channel = self.bot.get_channel(cfg["channel_id"])
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning(f"Guild {cfg['guild_id']}: channel {cfg['channel_id']} not found or not a text channel.")
                continue

            role = channel.guild.get_role(cfg["role_id"]) if cfg["role_id"] else None
            mention = role.mention if isinstance(role, discord.Role) else ""
            try:
                await channel.send(mention, embed=embed, view=view)
            except discord.Forbidden:
                logger.warning(f"Guild {cfg['guild_id']}: missing permission to send in channel {cfg['channel_id']}.")
            except discord.HTTPException as exc:
                logger.error(f"Guild {cfg['guild_id']}: failed to send SOTD embed: {exc}")

        # --- DM opted-in users ---
        dm_user_ids = await get_all_dm_users()
        for user_id in dm_user_ids:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=embed, view=view)
            except discord.Forbidden:
                logger.info(f"Cannot DM user {user_id} — removing from DM list (app deauthorized or DMs disabled).")
                await remove_dm_user(user_id)
            except discord.NotFound:
                logger.warning(f"User {user_id} not found — removing from DM list.")
                await remove_dm_user(user_id)
            except discord.HTTPException as exc:
                logger.error(f"Failed to DM user {user_id}: {exc}")

    @update_sotd.before_loop
    async def before_update_sotd(self) -> None:
        """Wait for the bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()


    # --- The slash command group for all /sotd <> commands ---

    sotd = SlashCommandGroup("sotd", "Commands related to the Audius Song of the Day")

    # --- Informational commands ---

    @sotd.command(name="current", description="Get the current Song of the Day")
    async def current(self, ctx: discord.ApplicationContext) -> None:
        """Return the current SOTD, fetching from the API if none exists yet."""
        sotd_data = await get_current_sotd()

        if sotd_data is None:
            sotd_data = await self.fetch_sotd_from_api()
            if "Error" in sotd_data:
                await ctx.respond(
                    embed=discord.Embed(
                        description=sotd_data["Error"],
                        color=discord.Color.og_blurple(),
                    ),
                    ephemeral=True,
                )
                return
            await save_sotd(sotd_data)

        embed = discord.Embed(
            title=sotd_data["track_title"],
            description=(
                f"Artist: {sotd_data['artist_name']} (@{sotd_data['artist_handle']})\n"
                f"Genre: {sotd_data['genre']}\n"
                f"Released: {_release_timestamp(sotd_data['release_date'])} ({_release_timestamp(sotd_data['release_date'], style='R')})\n"
                f"Plays: {sotd_data['play_count']} | Reposts: {sotd_data['repost_count']} | Favorites: {sotd_data['favorite_count']}"
            ),
            color=discord.Color.og_blurple(),
        )
        embed.set_thumbnail(url=sotd_data["artwork_url"])
        view = SOTDView(permalink=sotd_data["permalink"])
        await ctx.respond(embed=embed, view=view)

    @sotd.command(name="history", description="Show past Songs of the Day")
    async def history(self, ctx: discord.ApplicationContext) -> None:
        """Display the last 10 SOTD entries as an embed."""
        entries = await get_sotd_history(limit=10)
        if not entries:
            await ctx.respond(
                embed=discord.Embed(
                    description="No SOTD history yet!",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
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
            color=discord.Color.og_blurple(),
        )
        await ctx.respond(embed=embed)

    # --- Guild setup commands (server owner or SOTD Bot Admin only) ---

    @sotd.command(name="set-channel", description="Set the channel where SOTD is posted for this server.", contexts=[discord.InteractionContextType.guild])
    @discord.option("channel", discord.TextChannel, description="The channel to post the SOTD in.")
    async def set_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel) -> None:
        """Set the SOTD channel for this guild."""
        if not await _is_sotd_admin(ctx):
            await ctx.respond(
                embed=discord.Embed(
                    description="You need to be the server owner or have the **SOTD Bot Admin** role to use this command.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
            return

        await save_guild_config(ctx.guild.id, "sotd_channel_id", str(channel.id))
        await ctx.respond(
            embed=discord.Embed(
                description=f"SOTD channel set to {channel.mention}. The Song of the Day will be posted there.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )

    @sotd.command(name="set-role", description="Set an optional role to mention with each SOTD post. Leave blank to remove ping.", contexts=[discord.InteractionContextType.guild])
    @discord.option("role", discord.Role, description="The role to mention (leave blank to remove).", required=False)
    async def set_role(self, ctx: discord.ApplicationContext, role: discord.Role | None = None) -> None:
        """Set or clear the SOTD mention role for this guild."""
        if not await _is_sotd_admin(ctx):
            await ctx.respond(
                embed=discord.Embed(
                    description="You need to be the server owner or have the **SOTD Bot Admin** role to use this command.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
            return

        if role is None:
            await del_guild_config(ctx.guild.id, "sotd_role_id")
            await ctx.respond(
                embed=discord.Embed(
                    description="SOTD mention role cleared.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
        else:
            await save_guild_config(ctx.guild.id, "sotd_role_id", str(role.id))
            await ctx.respond(
                embed=discord.Embed(
                    description=f"SOTD mention role set to {role.mention}.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )

    # --- User DM opt-in commands (available in DMs for user-installed accounts) ---

    @sotd.command(
        name="subscribe",
        description="Receive the daily Song of the Day directly in your DMs.",
        integration_types={discord.IntegrationType.user_install},
        contexts={discord.InteractionContextType.guild, discord.InteractionContextType.bot_dm, discord.InteractionContextType.private_channel},
    )
    async def subscribe(self, ctx: discord.ApplicationContext) -> None:
        """Opt in to receiving the daily SOTD via DM."""
        if ctx.interaction.authorizing_integration_owners.user_id is None:
            await ctx.respond(
                embed=discord.Embed(
                    description="You need to install the bot to your account before subscribing to DMs.\nUse the **Add App** button on the bot's profile to install it.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
            return

        if await is_dm_user(ctx.author.id):
            await ctx.respond(
                embed=discord.Embed(
                    description="You're already subscribed to daily SOTD DMs.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
            return

        await add_dm_user(ctx.author.id)
        await ctx.respond(
            embed=discord.Embed(
                description="You're now subscribed! You'll receive the Song of the Day in your DMs each day.\nUse `/sotd unsubscribe` at any time to stop.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )

    @sotd.command(
        name="unsubscribe",
        description="Stop receiving the daily Song of the Day in your DMs.",
        integration_types=_DM_INTEGRATION_TYPES,
        contexts=_DM_CONTEXTS,
    )
    async def unsubscribe(self, ctx: discord.ApplicationContext) -> None:
        """Opt out of receiving the daily SOTD via DM."""
        if not await is_dm_user(ctx.author.id):
            await ctx.respond(
                embed=discord.Embed(
                    description="You're not currently subscribed to SOTD DMs.",
                    color=discord.Color.og_blurple(),
                ),
                ephemeral=True,
            )
            return

        await remove_dm_user(ctx.author.id)
        await ctx.respond(
            embed=discord.Embed(
                description="You've been unsubscribed from daily SOTD DMs.",
                color=discord.Color.og_blurple(),
            ),
            ephemeral=True,
        )


def setup(bot: discord.Bot) -> None:
    """Register the AudiusSOTD cog."""
    bot.add_cog(AudiusSOTD(bot))
