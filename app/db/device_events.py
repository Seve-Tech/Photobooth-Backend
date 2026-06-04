from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def log_device_event(
    unit_id: int,
    event_type: str,
    message: str,
    severity: str = "info",
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO device_events (
            unit_id,
            event_type,
            severity,
            message,
            created_at
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, unit_id, event_type, severity, message, now)

    return row_to_dict(row)


async def count_device_events(
    unit_id: int,
    severity: str | None = None,
) -> int:
    """Return the total number of device events for a unit (optionally filtered by severity)."""
    pool = get_pool()

    if severity:
        query = """
            SELECT COUNT(*) FROM device_events
            WHERE unit_id = $1 AND severity = $2
        """
        async with pool.acquire() as conn:
            return await conn.fetchval(query, unit_id, severity) or 0
    else:
        query = """
            SELECT COUNT(*) FROM device_events
            WHERE unit_id = $1
        """
        async with pool.acquire() as conn:
            return await conn.fetchval(query, unit_id) or 0


async def list_device_events(
    unit_id: int,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return a paginated page of device events ordered by most-recent first."""
    pool = get_pool()

    if severity:
        query = """
            SELECT * FROM device_events
            WHERE unit_id = $1 AND severity = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, unit_id, severity, limit, offset)
    else:
        query = """
            SELECT * FROM device_events
            WHERE unit_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, unit_id, limit, offset)

    return [row_to_dict(r) for r in rows]