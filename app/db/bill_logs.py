import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def log_bill_accepted(
    session_id: str,
    denomination: Decimal,
    bill_count: int = 1,
    raw_signal: str | None = None,
    hardware_status: str | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO bill_acceptor_logs (
            session_id,
            denomination,
            bill_count,
            raw_signal,
            hardware_status,
            inserted_at
        )
        SELECT
            s.id,
            $2,
            $3,
            $4,
            $5,
            $6
        FROM sessions s
        WHERE s.session_uuid = $1
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, uuid.UUID(session_id), denomination, bill_count, raw_signal, hardware_status, now)

    if row is None:
        raise ValueError(f"Session '{session_id}' not found.")

    return row_to_dict(row)


async def list_bill_logs(session_id: str) -> list[dict[str, Any]]:
    pool = get_pool()

    query = """
        SELECT bl.*
        FROM bill_acceptor_logs bl
        JOIN sessions s ON s.id = bl.session_id
        WHERE s.session_uuid = $1
        ORDER BY bl.inserted_at ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, uuid.UUID(session_id))

    return [row_to_dict(r) for r in rows]


async def get_session_total_inserted(session_id: str) -> Decimal:
    pool = get_pool()

    query = """
        SELECT
            COALESCE(SUM(bl.denomination * bl.bill_count), 0) AS total_inserted
        FROM bill_acceptor_logs bl
        JOIN sessions s ON s.id = bl.session_id
        WHERE s.session_uuid = $1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, uuid.UUID(session_id))

    return Decimal(str(row["total_inserted"]))