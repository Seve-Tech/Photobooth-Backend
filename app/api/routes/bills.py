"""
Bill acceptor REST endpoints.

Provides an HTTP alternative to WebSocket for sending pulse signals
(useful for testing with curl/Postman) and querying payment history.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.core.database import list_payments
from app.models.schemas import BillAcceptedEvent, PulseSignal
from app.services.bill_acceptor import handle_pulse

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("/pulse", response_model=BillAcceptedEvent, status_code=201)
async def receive_pulse(
    pulse_count: int = Query(..., ge=1, description="Number of pulses from bill acceptor"),
    session_id: str | None = Query(default=None, description="Active session ID"),
) -> BillAcceptedEvent:
    """
    Receive a pulse signal via HTTP (alternative to WebSocket).

    Useful for:
    - Testing without a WebSocket client
    - Fallback if WebSocket is unavailable
    - The Arduino bridge can POST here if WS is not implemented on that side
    """
    signal = PulseSignal(pulse_count=pulse_count, received_at=datetime.utcnow())
    event = await handle_pulse(signal, session_id=session_id)
    return event


@router.get("/payments", tags=["bills"])
async def get_payments(
    session_id: str | None = Query(default=None, description="Filter by session ID"),
) -> list[dict]:
    """List all recorded payment events, optionally filtered by session."""
    return await list_payments(session_id=session_id)
