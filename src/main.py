"""
Bot entry-point — loads extensions, configures logging, and starts the bot.

Environment
-----------
TOKEN          - Discord bot token (required).
debug_enabled  - When set in the DB config, enables DEBUG-level logging.
"""

import asyncio
import logging
import os

import discord
import dotenv

from db import init_db, get_config

env_loaded = dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_file_handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(_file_handler)

OWNER_ID = 969254887621820526


async def main() -> None:
    """Initialise and start the Discord bot."""
    intents = discord.Intents.default()
    bot = discord.Bot(
        owner_id=OWNER_ID,
        auto_sync_commands=True,
        default_command_contexts={discord.InteractionContextType.guild},
        default_command_integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        intents=intents,
    )
    setattr(bot, "logger", logger)

    @bot.event
    async def on_ready() -> None:
        # Ensure DB tables exist before anything else
        await init_db()

        # Apply debug_enabled setting from DB config
        debug_enabled = await get_config("debug_enabled")
        if debug_enabled and debug_enabled not in ("0", "false", ""):
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled via DB config.")

        if bot.user:
            logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    for filename in os.listdir("./src/cogs"):
        if filename.endswith(".py") and not filename.startswith("__"):
            try:
                bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"Loaded extension: `{filename[:-3]}` from {filename}")
            except discord.ExtensionError as exc:
                logger.error(f"Failed to load extension {filename}: {exc}")

    if not env_loaded:
        logger.warning(
            "Couldn't load .env file. Make sure it exists and is properly formatted. "
            "Continuing with environment variables from the system."
        )

    token = os.getenv("TOKEN")
    if not token:
        logger.error(
            "TOKEN environment variable is not set. "
            "Please set it in the .env file or your system environment variables."
        )
        return

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())