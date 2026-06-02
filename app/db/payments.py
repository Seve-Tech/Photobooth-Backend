import uuid
from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict
from app.models.schemas import BillAcceptedEvent


async def save_payment(event: BillAcceptedEvent) -> dict[str, Any]:
    pool = get_pool()
    payment_uuid = uuid.uuid4()
    now = datetime.utcnow()

    async with pool.acquire() as conn:
        async with conn.transaction():

            insert_payment = """
                INSERT INTO payments (
                    payment_uuid,
                    session_id,
                    payment_method,
                    payment_status,
                    amount,
                    reference_number,
                    received_at,
                    sync_status,
                    created_at
                )
                SELECT
                    $1,
                    s.id,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9
                FROM sessions s
                WHERE s.session_uuid = $2
                RETURNING *
            """

            row = await conn.fetchrow(
                insert_payment,
                payment_uuid,
                uuid.UUID(event.session_id),
                event.payment_method,
                event.payment_status or "completed",
                event.amount,
                event.reference_number,
                event.received_at or now,
                "pending",
                now,
            )

            if row is None:
                raise ValueError(f"Session '{event.session_id}' not found; payment not recorded.")

            update_session_paid = """
                UPDATE sessions
                SET
                    paid_amount    = paid_amount + $1,
                    payment_status = CASE
                        WHEN paid_amount + $1 >= expected_amount THEN 'paid'
                        ELSE 'partial'
                    END,
                    session_status = CASE
                        WHEN paid_amount + $1 >= expected_amount THEN 'paid'
                        ELSE session_status
                    END,
                    updated_at = $2
                WHERE session_uuid = $3
            """

            await conn.execute(update_session_paid, event.amount, now, uuid.UUID(event.session_id))

    return row_to_dict(row)


async def list_payments(session_id: str | None = None) -> list[dict[str, Any]]:
    pool = get_pool()

    if session_id:
        query = """
            SELECT
                p.*,
                s.session_uuid AS session_uuid
            FROM payments p
            JOIN sessions s ON s.id = p.session_id
            WHERE s.session_uuid = $1
            ORDER BY p.created_at DESC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, uuid.UUID(session_id))
    else:
        query = """
            SELECT
                p.*,
                s.session_uuid AS session_uuid
            FROM payments p
            JOIN sessions s ON s.id = p.session_id
            ORDER BY p.created_at DESC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

    return [row_to_dict(r) for r in rows]