from datetime import datetime, timezone, timedelta
from typing import Any

import asyncpg

from app.core.config import settings

_pool: asyncpg.Pool | None = None
PH_TZ = timezone(timedelta(hours=8))


def localize_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(PH_TZ)
    return dt.astimezone(PH_TZ)


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call init_db() at startup.")
    return _pool


def row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = localize_datetime(v)
    return d


async def ping_db() -> bool:
    try:
        async with get_pool().acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False