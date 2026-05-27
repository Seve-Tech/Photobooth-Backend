from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def enqueue_sync(
    table_name: str,
    record_id: int,
    operation_type: str,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO sync_queue (
            table_name,
            record_id,
            operation_type,
            sync_status,
            retry_count,
            created_at
        ) VALUES ($1, $2, $3, 'pending', 0, $4)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, table_name, record_id, operation_type, now)

    return row_to_dict(row)


async def list_pending_sync(limit: int = 50) -> list[dict[str, Any]]:
    pool = get_pool()

    query = """
        SELECT * FROM sync_queue
        WHERE sync_status = 'pending'
        ORDER BY created_at ASC
        LIMIT $1
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit)

    return [row_to_dict(r) for r in rows]


async def mark_sync_done(sync_id: int) -> dict[str, Any] | None:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        UPDATE sync_queue
        SET
            sync_status = 'synced',
            synced_at   = $1
        WHERE id = $2
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, now, sync_id)

    return row_to_dict(row) if row else None


async def mark_sync_failed(sync_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        UPDATE sync_queue
        SET
            sync_status = 'failed',
            retry_count = retry_count + 1
        WHERE id = $1
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, sync_id)

    return row_to_dict(row) if row else None


async def get_sync_stats() -> dict[str, Any]:
    pool = get_pool()

    query = """
        SELECT
            sync_status,
            COUNT(*) AS count
        FROM sync_queue
        GROUP BY sync_status
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    return {r["sync_status"]: r["count"] for r in rows}