from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import aiosqlite

from app.schemas import Source

logger = logging.getLogger(__name__)

_DB_PATH = "cache.db"


async def _init_db(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS search_cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await db.commit()


async def get_cached(key: str) -> list[Source] | None:
    """Return cached sources for key, or None if not found."""
    try:
        async with aiosqlite.connect(_DB_PATH) as db:
            await _init_db(db)
            async with db.execute(
                "SELECT value FROM search_cache WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                data = json.loads(row[0])
                return [Source(**item) for item in data]
    except Exception as exc:
        logger.warning("Cache read failed: %s", exc)
        return None


async def set_cached(key: str, sources: list[Source]) -> None:
    """Store sources under key. Silently ignores write failures."""
    try:
        value = json.dumps([s.model_dump(mode="json") for s in sources])
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(_DB_PATH) as db:
            await _init_db(db)
            await db.execute(
                "INSERT OR REPLACE INTO search_cache (key, value, created_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)
