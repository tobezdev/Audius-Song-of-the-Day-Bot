"""
Global error handler cog.

Catches all unhandled application-command errors, responds with a
user-friendly message, and logs the full traceback with a unique (ish)
error code for tracing.
"""

import logging
import random
import string

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class ErrorHandler(commands.Cog):
    """Catch-all listener for application command errors."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, error: discord.DiscordException
    ) -> None:
        """Handle any unhandled error from a slash command invocation."""
        error_code = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        message = None

        match error:
            case commands.CommandNotFound():
                message = "That command doesn't exist."
            case commands.MissingRequiredArgument():
                message = "You forgot to include a required argument."
            case commands.BadArgument():
                message = "One or more arguments were invalid or in the wrong format."
            case commands.DisabledCommand():
                message = "That command is currently disabled."
            case commands.NoPrivateMessage():
                message = "This command can't be used in DMs."
            case commands.MissingPermissions() | commands.BotMissingPermissions():
                message = "You or the bot lack the required permissions."
            case commands.CommandOnCooldown():
                message = "That command is on cooldown. Try again later."
            case commands.MaxConcurrencyReached():
                message = "Too many people are using this command at once."
            case commands.NotOwner():
                message = "Only the bot owner can use this command."
            case commands.CheckFailure() | discord.CheckFailure():
                message = "You don't meet the requirements to use this command."
            case commands.CommandInvokeError() | discord.ApplicationCommandInvokeError():
                message = "An unexpected error occurred while running that command."
            case discord.Forbidden():
                message = "I don't have permission to do that."
            case discord.NotFound():
                message = "That resource couldn't be found."
            case discord.HTTPException():
                message = "A request to Discord's API failed unexpectedly."
            case _:
                message = f"An unknown error (`{error.__class__.__name__}`) occurred."

        message += (
            f"\nIf this error persists, please contact a member of staff. "
            f"Quote error code **`{error_code}`** when doing so."
        )

        try:
            await ctx.respond(
                embed=discord.Embed(description=message, color=discord.Color.og_blurple()),
                ephemeral=True,
            )
        except (discord.InteractionResponded, discord.NotFound, discord.HTTPException):
            pass

        logger.error(
            f"[{error_code}] Error in command '{ctx.command}' "
            f"with user {ctx.user} (@{ctx.user.id}): {error}",
            exc_info=error,
        )


def setup(bot: discord.Bot) -> None:
    """Register the ErrorHandler cog."""
    bot.add_cog(ErrorHandler(bot))
