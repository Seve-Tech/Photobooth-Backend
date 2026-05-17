"""
Database stub.

Right now everything is stored in-memory so the app runs
without a real DB while the DB layer is being built.

When the DB is ready:
1. Replace the in-memory dicts below with your ORM session/queries.
2. Keep the same function signatures — the rest of the app won't need to change.
3. Set DATABASE_URL in .env and uncomment the engine/session setup.
"""

import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import (
    BillAcceptedEvent,
    SessionCreate,
    SessionResponse,
    SessionStatus,
    SessionUpdate,
)

# ---------------------------------------------------------------------------
# In-memory "tables" — replace with real DB calls later
# ---------------------------------------------------------------------------

_sessions: dict[str, dict[str, Any]] = {}
_payments: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


async def create_session(data: SessionCreate) -> SessionResponse:
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    record: dict[str, Any] = {
        "id": session_id,
        "status": SessionStatus.PENDING,
        "total_paid": 0.0,
        "currency": "PHP",
        "customer_ref": data.customer_ref,
        "package_id": data.package_id,
        "created_at": now,
        "updated_at": now,
    }
    _sessions[session_id] = record
    return SessionResponse(**record)


async def get_session(session_id: str) -> SessionResponse | None:
    record = _sessions.get(session_id)
    if record is None:
        return None
    return SessionResponse(**record)


async def list_sessions() -> list[SessionResponse]:
    return [SessionResponse(**r) for r in _sessions.values()]


async def update_session(session_id: str, data: SessionUpdate) -> SessionResponse | None:
    record = _sessions.get(session_id)
    if record is None:
        return None

    updates = data.model_dump(exclude_none=True)
    record.update(updates)
    record["updated_at"] = datetime.utcnow()
    return SessionResponse(**record)


# ---------------------------------------------------------------------------
# Payment / bill-accepted logging
# ---------------------------------------------------------------------------


async def save_payment(event: BillAcceptedEvent) -> dict[str, Any]:
    record = event.model_dump()
    record["id"] = str(uuid.uuid4())
    _payments.append(record)
    return record


async def list_payments(session_id: str | None = None) -> list[dict[str, Any]]:
    if session_id:
        return [p for p in _payments if p.get("session_id") == session_id]
    return list(_payments)


# ---------------------------------------------------------------------------
# Health check helper
# ---------------------------------------------------------------------------


async def ping_db() -> bool:
    """
    Returns True if DB is reachable.
    Replace with a real connectivity check (e.g. SELECT 1) when DB is ready.
    """
    return True  # in-memory always "works"
