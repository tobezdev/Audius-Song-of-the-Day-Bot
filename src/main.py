"""
Bot entry-point — loads extensions, configures logging, and starts the bot.

Environment
-----------
TOKEN          - Discord bot token (required).

CLI Flags
---------
--debug, -d           - Force-enable DEBUG-level logging.
--disable-cogs, -dc   - Space-separated list of cog names to skip loading
                        (without the .py extension).
--output-stream, -o   - File path to mirror log output to, or '.' to
                        stream to the terminal.
"""

import argparse
import asyncio
import logging
import os
import sys

import discord
import dotenv

from db import init_db

env_loaded = dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_file_handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(_file_handler)

OWNER_ID = 969254887621820526


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Audius SOTD Discord Bot")
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Force-enable DEBUG-level logging.",
    )
    parser.add_argument(
        "-dc", "--disable-cogs",
        nargs="+",
        default=[],
        metavar="COG",
        help="One or more cog names (without .py) to skip loading.",
    )
    parser.add_argument(
        "-t", "--token",
        help="Discord bot token (overrides TOKEN environment variable)."
    )
    parser.add_argument(
        "-o", "--output-stream",
        help="Optional file path to write the bot's output stream (stdout and stderr) or '.' for terminal output."
    )
    return parser.parse_args()


async def main() -> None:
    """Initialise and start the Discord bot."""
    args = parse_args()


    # Apply --debug flag immediately
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging force-enabled via --debug flag.")

    # Apply --output-stream flag
    if args.output_stream:
        if args.output_stream.strip().lower() == ".":
            stream_handler = logging.StreamHandler(sys.stdout)
        else:
            stream_handler = logging.StreamHandler(open(args.output_stream, "w", encoding="utf-8"))
        stream_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
        logger.addHandler(stream_handler)

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

        if bot.user:
            logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    disabled_cogs = {name.lower() for name in args.disable_cogs}

    for filename in os.listdir("./src/cogs"):
        if filename.endswith(".py") and not filename.startswith("__"):
            cog_name = filename[:-3]
            if cog_name.lower() in disabled_cogs:
                logger.info(f"Skipping disabled cog: `{cog_name}`")
                continue
            try:
                bot.load_extension(f"cogs.{cog_name}")
                logger.info(f"Loaded extension: `{cog_name}` from {filename}")
            except discord.ExtensionError as exc:
                logger.error(f"Failed to load extension {filename}: {exc}")

    if not env_loaded:
        logger.warning(
            "Couldn't load .env file. Make sure it exists and is properly formatted. "
            "Continuing with environment variables from the system."
        )

    token = args.token or os.getenv("TOKEN")
    if not token:
        logger.error(
            "TOKEN environment variable is not set. "
            "Please set it in the .env file or your system environment variables."
        )
        return

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())