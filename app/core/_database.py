"""
— DEPRECATED — 

This file was the in-memory stub used before the real PostgreSQL layer (app/db/) was built.
Nothing in the application imports from here anymore. It can be safely deleted.

Replace any stale imports with the equivalents from app.db:
    from app.core.database import create_session   →  from app.db import create_session
    from app.core.database import get_session       →  from app.db import get_session
    from app.core.database import list_sessions     →  from app.db import list_sessions
    from app.core.database import update_session    →  from app.db import update_session
    from app.core.database import save_payment      →  from app.db import save_payment
    from app.core.database import list_payments     →  from app.db import list_payments
    from app.core.database import ping_db           →  from app.db import ping_db
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
