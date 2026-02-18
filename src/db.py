"""
Lightweight async SQLite helper for persisting SOTD data.

Tables
------
sotd - one row per day, newest first by `created_at`.
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


async def init_db() -> None:
    """Create the database and tables if they don't exist yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_CONFIG_TABLE)
        await db.execute(_CREATE_SOTD_TABLE)
        await db.commit()
    logger.info(f"Database initialised at {DB_PATH}")

    # Seed config defaults (only inserts if the key doesn't already exist)
    _defaults = {
        "sotd_channel_id": "",
        "sotd_role_id": "",
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
