from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

from app.schemas import FinalResult

logger = logging.getLogger(__name__)

_DB_PATH = "evaluations.db"


async def _init_db(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_space TEXT NOT NULL,
            result_json TEXT NOT NULL,
            evaluated_at TEXT NOT NULL
        )
        """
    )
    await db.commit()


def _normalise(product_space: str) -> str:
    return product_space.strip().lower()


async def save_result(result: FinalResult) -> None:
    """Persist a FinalResult. Silently ignores failures."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        normalised = _normalise(result.product_space)
        result_json = result.model_dump_json()
        async with aiosqlite.connect(_DB_PATH) as db:
            await _init_db(db)
            await db.execute(
                "INSERT INTO evaluations (product_space, result_json, evaluated_at) VALUES (?, ?, ?)",
                (normalised, result_json, now),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Persistence write failed: %s", exc)


async def load_latest(product_space: str) -> FinalResult | None:
    """Return the most recent result for a product_space, or None."""
    try:
        normalised = _normalise(product_space)
        async with aiosqlite.connect(_DB_PATH) as db:
            await _init_db(db)
            async with db.execute(
                "SELECT result_json FROM evaluations WHERE product_space = ? ORDER BY id DESC LIMIT 1",
                (normalised,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return FinalResult.model_validate_json(row[0])
    except Exception as exc:
        logger.warning("Persistence read failed: %s", exc)
        return None
