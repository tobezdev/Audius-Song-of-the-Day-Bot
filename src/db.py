"""
Lightweight async SQLite helper for persisting SOTD data.

Tables
------
sotd         - one row per day, newest first by `created_at`.
config       - global bot key/value config.
guild_config - per-guild key/value config (sotd_channel_id, sotd_role_id, sotd_embed_color).
user_config  - per-user key/value config (sotd_embed_color).
user_dm      - users who have opted in to receive daily SOTD via DM.
premium      - guild or user IDs that have premium features unlocked.
"""

import aiosqlite
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "sotd.db"

_CREATE_SOTD_TABLE = """
CREATE TABLE IF NOT EXISTS sotd (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id        TEXT    NOT NULL,
    track_title     TEXT    NOT NULL,
    artist_name     TEXT    NOT NULL,
    artist_handle   TEXT    NOT NULL,
    genre           TEXT,
    release_date    TEXT,
    play_count      INTEGER DEFAULT 0,
    repost_count    INTEGER DEFAULT 0,
    favorite_count  INTEGER DEFAULT 0,
    permalink       TEXT,
    artwork_url     TEXT,
    tags            TEXT,                                       -- JSON array stored as text
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS config (
    key             TEXT PRIMARY KEY,                           -- Keys are case insensitive and stored (generally) in snake_case
    value           TEXT
);
"""

_CREATE_GUILD_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id        TEXT    NOT NULL,
    key             TEXT    NOT NULL,
    value           TEXT,
    PRIMARY KEY (guild_id, key)
);
"""

_CREATE_USER_DM_TABLE = """
CREATE TABLE IF NOT EXISTS user_dm (
    user_id         TEXT    PRIMARY KEY
);
"""

_CREATE_PREMIUM_TABLE = """
CREATE TABLE IF NOT EXISTS premium (
    guild_or_user_id TEXT PRIMARY KEY
);
"""

_CREATE_USER_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS user_config (
    user_id         TEXT    NOT NULL,
    key             TEXT    NOT NULL,
    value           TEXT,
    PRIMARY KEY (user_id, key)
);
"""


async def init_db() -> None:
    """Create the database and tables if they don't exist yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_CONFIG_TABLE)
        await db.execute(_CREATE_SOTD_TABLE)
        await db.execute(_CREATE_GUILD_CONFIG_TABLE)
        await db.execute(_CREATE_USER_DM_TABLE)
        await db.execute(_CREATE_PREMIUM_TABLE)
        await db.execute(_CREATE_USER_CONFIG_TABLE)
        await db.commit()
    logger.info(f"Database initialised at {DB_PATH}")

    # Seed config defaults (only inserts if the key doesn't already exist)
    _defaults = {
        "debug_enabled": "0",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in _defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await db.commit()
    logger.info("Config defaults seeded.")
    return


async def save_config(key: str, value: str) -> None:
    """Set a config value by key."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO config (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
        await db.commit()
        logger.info(f"Config set: {key} = {value}")


async def get_config(key: str) -> Optional[str]:
    """Get a config value by key, or None if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else None


async def del_config(key: str) -> None:
    """Delete a config value by key."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM config WHERE key = ?", (key,))
        await db.commit()
        logger.info(f"Config deleted: {key}")


async def save_sotd(sotd: dict) -> int:
    """Insert a new SOTD row and return its row id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO sotd
                (track_id, track_title, artist_name, artist_handle,
                genre, release_date, play_count, repost_count,
                favorite_count, permalink, artwork_url, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sotd["track_id"],
                sotd["track_title"],
                sotd["artist_name"],
                sotd["artist_handle"],
                sotd.get("genre"),
                sotd.get("release_date"),
                sotd.get("play_count", 0),
                sotd.get("repost_count", 0),
                sotd.get("favorite_count", 0),
                sotd.get("permalink"),
                sotd.get("artwork_url"),
                json.dumps(sotd.get("tags", [])),
            ),
        )
        await db.commit()
        logger.info(f"Saved SOTD #{cursor.lastrowid}: {sotd['track_title']}")
        return cursor.lastrowid  # type: ignore[return-value]


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert a sqlite Row into the same dict shape the cog expects."""
    return {
        "track_id": row["track_id"],
        "track_title": row["track_title"],
        "artist_name": row["artist_name"],
        "artist_handle": row["artist_handle"],
        "genre": row["genre"],
        "release_date": row["release_date"],
        "play_count": row["play_count"],
        "repost_count": row["repost_count"],
        "favorite_count": row["favorite_count"],
        "permalink": row["permalink"],
        "artwork_url": row["artwork_url"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "created_at": row["created_at"],
    }


async def get_current_sotd() -> Optional[dict]:
    """Return the most recent SOTD entry, or None if the table is empty."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sotd ORDER BY created_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_dict(row) if row else None


async def get_sotd_history(limit: int = 10) -> list[dict]:
    """Return the last *limit* SOTD entries, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sotd ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Per-guild configuration helpers
# ---------------------------------------------------------------------------

async def get_guild_config(guild_id: int, key: str) -> Optional[str]:
    """Get a per-guild config value, or None if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT value FROM guild_config WHERE guild_id = ? AND key = ?",
            (str(guild_id), key),
        ) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else None


async def save_guild_config(guild_id: int, key: str, value: str) -> None:
    """Set a per-guild config value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO guild_config (guild_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value
            """,
            (str(guild_id), key, value),
        )
        await db.commit()
        logger.info(f"Guild config set: guild={guild_id} {key} = {value}")


async def del_guild_config(guild_id: int, key: str) -> None:
    """Delete a per-guild config value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM guild_config WHERE guild_id = ? AND key = ?",
            (str(guild_id), key),
        )
        await db.commit()
        logger.info(f"Guild config deleted: guild={guild_id} {key}")


async def get_all_guild_sotd_configs() -> list[dict]:
    """Return all guilds that have a sotd_channel_id set, with their optional role_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT guild_id, value AS channel_id FROM guild_config WHERE key = 'sotd_channel_id' AND value != ''",
        ) as cursor:
            channel_rows = await cursor.fetchall()

        results = []
        for row in channel_rows:
            async with db.execute(
                "SELECT value FROM guild_config WHERE guild_id = ? AND key = 'sotd_role_id'",
                (row["guild_id"],),
            ) as role_cursor:
                role_row = await role_cursor.fetchone()
            results.append({
                "guild_id": int(row["guild_id"]),
                "channel_id": int(row["channel_id"]),
                "role_id": int(role_row["value"]) if role_row and role_row["value"] else None,
            })
        return results


# ---------------------------------------------------------------------------
# User DM opt-in helpers
# ---------------------------------------------------------------------------

async def add_dm_user(user_id: int) -> None:
    """Add a user to the DM SOTD list."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_dm (user_id) VALUES (?)",
            (str(user_id),),
        )
        await db.commit()
        logger.info(f"DM SOTD user added: {user_id}")


async def remove_dm_user(user_id: int) -> None:
    """Remove a user from the DM SOTD list."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_dm WHERE user_id = ?", (str(user_id),))
        await db.commit()
        logger.info(f"DM SOTD user removed: {user_id}")


async def get_all_dm_users() -> list[int]:
    """Return all user IDs opted in to DM SOTD."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id FROM user_dm") as cursor:
            rows = await cursor.fetchall()
            return [int(row["user_id"]) for row in rows]


async def is_dm_user(user_id: int) -> bool:
    """Return True if the user is opted in to DM SOTD."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT 1 FROM user_dm WHERE user_id = ?", (str(user_id),)
        ) as cursor:
            return await cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# Premium helpers
# ---------------------------------------------------------------------------

async def add_premium(guild_or_user_id: int) -> None:
    """Grant premium status to a guild or user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO premium (guild_or_user_id) VALUES (?)",
            (str(guild_or_user_id),),
        )
        await db.commit()
        logger.info(f"Premium added: {guild_or_user_id}")


async def remove_premium(guild_or_user_id: int) -> None:
    """Revoke premium status from a guild or user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM premium WHERE guild_or_user_id = ?",
            (str(guild_or_user_id),),
        )
        await db.commit()
        logger.info(f"Premium removed: {guild_or_user_id}")


async def is_premium(guild_or_user_id: int) -> bool:
    """Return True if the guild or user has premium status."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM premium WHERE guild_or_user_id = ?",
            (str(guild_or_user_id),),
        ) as cursor:
            return await cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# Per-user configuration helpers
# ---------------------------------------------------------------------------

async def get_user_config(user_id: int, key: str) -> Optional[str]:
    """Get a per-user config value, or None if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT value FROM user_config WHERE user_id = ? AND key = ?",
            (str(user_id), key),
        ) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else None


async def save_user_config(user_id: int, key: str, value: str) -> None:
    """Set a per-user config value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_config (user_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value
            """,
            (str(user_id), key, value),
        )
        await db.commit()
        logger.info(f"User config set: user={user_id} {key} = {value}")


async def del_user_config(user_id: int, key: str) -> None:
    """Delete a per-user config value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM user_config WHERE user_id = ? AND key = ?",
            (str(user_id), key),
        )
        await db.commit()
        logger.info(f"User config deleted: user={user_id} {key}")
