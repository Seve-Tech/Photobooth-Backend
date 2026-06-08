"""
Bill acceptor REST endpoints.

Provides an HTTP alternative to WebSocket for sending pulse signals
(useful for testing with curl/Postman) and querying payment history.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import list_payments
from app.core.security import verify_api_key
from app.models.schemas import BillAcceptedEvent, AmountSignal
from app.services.bill_acceptor import handle_amount

router = APIRouter(
    prefix="/bills",
    tags=["bills"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/amount", response_model=BillAcceptedEvent, status_code=201)
async def receive_amount(
    amount: float = Query(..., ge=0.0, description="Amount received in PHP"),
    session_id: str | None = Query(default=None, description="Active session ID"),
) -> BillAcceptedEvent:
    """
    Receive an amount signal via HTTP (alternative to WebSocket).

    Useful for:
    - Testing without a WebSocket client
    - Fallback if WebSocket is unavailable
    - The Arduino bridge can POST here if WS is not implemented on that side
    """
    signal = AmountSignal(amount=amount, received_at=datetime.utcnow())
    event = await handle_amount(signal, session_id=session_id)
    return event


@router.get("/payments", tags=["bills"])
async def get_payments(
    session_id: str | None = Query(default=None, description="Filter by session ID"),
) -> list[dict]:
    """List all recorded payment events, optionally filtered by session."""
    return await list_payments(session_id=session_id)
