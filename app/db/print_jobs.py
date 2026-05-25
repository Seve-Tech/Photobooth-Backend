import uuid
from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def create_print_job(
    session_id: str,
    printer_name: str,
    copies: int = 1,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO print_jobs (
            session_id,
            printer_name,
            copies,
            print_status,
            created_at
        )
        SELECT
            s.id,
            $2,
            $3,
            'queued',
            $4
        FROM sessions s
        WHERE s.session_uuid = $1
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, uuid.UUID(session_id), printer_name, copies, now)

    if row is None:
        raise ValueError(f"Session '{session_id}' not found.")

    return row_to_dict(row)


async def update_print_job_status(
    print_job_id: int,
    status: str,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        UPDATE print_jobs
        SET
            print_status  = $1,
            error_message = $2,
            printed_at    = CASE WHEN $1 = 'completed' THEN $3 ELSE printed_at END
        WHERE id = $4
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, status, error_message, now, print_job_id)

    if row and status == "completed":
        await _increment_session_print_count(session_int_id=row["session_id"], copies=row["copies"])

    return row_to_dict(row) if row else None


async def _increment_session_print_count(session_int_id: int, copies: int) -> None:
    pool = get_pool()

    query = """
        UPDATE sessions
        SET
            total_prints = total_prints + $1,
            updated_at   = $2
        WHERE id = $3
    """

    async with pool.acquire() as conn:
        await conn.execute(query, copies, datetime.utcnow(), session_int_id)


async def list_print_jobs(session_id: str) -> list[dict[str, Any]]:
    pool = get_pool()

    query = """
        SELECT pj.*
        FROM print_jobs pj
        JOIN sessions s ON s.id = pj.session_id
        WHERE s.session_uuid = $1
        ORDER BY pj.created_at ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, uuid.UUID(session_id))

    return [row_to_dict(r) for r in rows]