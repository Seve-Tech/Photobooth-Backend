import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.db.connection import get_pool, row_to_dict
from app.models.schemas import SessionCreate, SessionResponse, SessionStatus, SessionUpdate


def _row_to_session_response(row) -> SessionResponse:
    return SessionResponse(
        id=str(row["session_uuid"]),
        status=SessionStatus(row["session_status"]),
        total_paid=float(row["paid_amount"] or 0.0),
        currency="PHP",
        customer_ref=row.get("customer_ref"),
        package_id=row["package_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_session(data: SessionCreate, branch_id: int, unit_id: int) -> SessionResponse:
    pool = get_pool()
    session_uuid = uuid.uuid4()
    now = datetime.utcnow()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Get the expected price of the package
            expected_amount = Decimal("0.00")
            if data.package_id is not None:
                pkg_row = await conn.fetchrow(
                    "SELECT price FROM packages WHERE id = $1 LIMIT 1",
                    data.package_id
                )
                if pkg_row:
                    expected_amount = pkg_row["price"]

            # Calculate statuses based on paid amount
            paid_amount = Decimal(str(data.paid_amount or 0.0))
            if paid_amount >= expected_amount and expected_amount > 0:
                payment_status = "paid"
                session_status = SessionStatus.PAID
            elif paid_amount > 0:
                payment_status = "partial"
                session_status = SessionStatus.PENDING
            else:
                payment_status = "unpaid"
                session_status = SessionStatus.PENDING

            insert_session_query = """
                INSERT INTO sessions (
                    session_uuid,
                    branch_id,
                    unit_id,
                    package_id,
                    customer_ref,
                    session_status,
                    started_at,
                    expected_amount,
                    paid_amount,
                    payment_status,
                    total_photos_taken,
                    total_prints,
                    sync_status,
                    created_at,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9, $10,
                    0, 0, 'pending', $11, $11
                )
                RETURNING *
            """

            session_row = await conn.fetchrow(
                insert_session_query,
                session_uuid,
                branch_id,
                unit_id,
                data.package_id,
                data.customer_ref,
                session_status.value,
                now,
                expected_amount,
                paid_amount,
                payment_status,
                now,
            )

            # If there's an initial payment, create a payment record and hardware log
            if paid_amount > 0:
                payment_uuid = uuid.uuid4()
                insert_payment_query = """
                    INSERT INTO payments (
                        payment_uuid,
                        session_id,
                        payment_method,
                        payment_status,
                        amount,
                        received_at,
                        sync_status,
                        created_at
                    ) VALUES ($1, $2, $3, 'completed', $4, $5, 'pending', $5)
                """
                await conn.execute(
                    insert_payment_query,
                    payment_uuid,
                    session_row["id"],
                    data.payment_method or "cash",
                    paid_amount,
                    now,
                )

                insert_log_query = """
                    INSERT INTO bill_acceptor_logs (
                        session_id,
                        denomination,
                        bill_count,
                        raw_signal,
                        hardware_status,
                        inserted_at
                    ) VALUES ($1, $2, 1, 'prepaid', 'accepted', $3)
                """
                await conn.execute(
                    insert_log_query,
                    session_row["id"],
                    paid_amount,
                    now,
                )

    return _row_to_session_response(session_row)


async def get_session(session_id: str) -> SessionResponse | None:
    pool = get_pool()

    query = """
        SELECT * FROM sessions
        WHERE session_uuid = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, uuid.UUID(session_id))

    return _row_to_session_response(row) if row else None


async def list_sessions(
    branch_id: int | None = None,
    unit_id: int | None = None,
) -> list[SessionResponse]:
    pool = get_pool()

    conditions: list[str] = []
    values: list[Any] = []

    if branch_id is not None:
        values.append(branch_id)
        conditions.append(f"branch_id = ${len(values)}")

    if unit_id is not None:
        values.append(unit_id)
        conditions.append(f"unit_id = ${len(values)}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT * FROM sessions
        {where}
        ORDER BY created_at DESC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *values)

    return [_row_to_session_response(r) for r in rows]


async def update_session(session_id: str, data: SessionUpdate) -> SessionResponse | None:
    pool = get_pool()

    updates = data.model_dump(exclude_none=True)
    if not updates:
        return await get_session(session_id)

    field_to_column: dict[str, str] = {
        "status": "session_status",
        "total_paid": "paid_amount",
    }

    set_clauses: list[str] = []
    values: list[Any] = []

    for field, value in updates.items():
        col = field_to_column.get(field, field)
        values.append(value)
        set_clauses.append(f"{col} = ${len(values)}")

    values.append(datetime.utcnow())
    set_clauses.append(f"updated_at = ${len(values)}")

    values.append(uuid.UUID(session_id))
    where_param = f"${len(values)}"

    query = f"""
        UPDATE sessions
        SET {', '.join(set_clauses)}
        WHERE session_uuid = {where_param}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)

    return _row_to_session_response(row) if row else None


async def complete_session(session_id: str) -> SessionResponse | None:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        UPDATE sessions
        SET
            session_status = 'completed',
            completed_at   = $1,
            updated_at     = $1
        WHERE session_uuid = $2
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, now, uuid.UUID(session_id))

    return _row_to_session_response(row) if row else None


async def get_active_pending_session() -> SessionResponse | None:
    pool = get_pool()
    query = """
        SELECT * FROM sessions
        WHERE session_status = 'pending' AND payment_status != 'paid'
        ORDER BY created_at DESC
        LIMIT 1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query)

    return _row_to_session_response(row) if row else None