"""
Bill acceptor service.

Responsible for:
1. Translating pulse counts to PHP denominations.
2. Persisting the payment event.
3. Broadcasting the event to all WebSocket subscribers.
"""

import logging
from datetime import datetime

from app.core.config import settings
from app.core.database import save_payment, update_session
from app.models.schemas import (
    BillAcceptedEvent,
    PaymentStatus,
    PulseSignal,
    SessionUpdate,
    SessionStatus,
    WSMessage,
    WSMessageType,
)
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


def resolve_amount(pulse_count: int) -> float | None:
    """
    Look up the PHP amount for a given pulse count.
    Returns None if the pulse count is not in the configured map.
    """
    return settings.bill_pulse_map.get(pulse_count)


async def handle_pulse(signal: PulseSignal, session_id: str | None = None) -> BillAcceptedEvent:
    """
    Core handler: receive a pulse signal, validate it, persist it,
    and notify all WebSocket listeners.

    Args:
        signal:     The raw pulse data from Arduino.
        session_id: The active photobooth session (if known).

    Returns:
        The processed BillAcceptedEvent.
    """
    amount = resolve_amount(signal.pulse_count)

    if amount is None:
        logger.warning("Unknown pulse count received: %d", signal.pulse_count)
        event = BillAcceptedEvent(
            pulse_count=signal.pulse_count,
            amount=0.0,
            status=PaymentStatus.REJECTED,
            received_at=signal.received_at,
            session_id=session_id,
        )
    else:
        logger.info(
            "Bill accepted — pulses: %d, amount: PHP %.2f, session: %s",
            signal.pulse_count,
            amount,
            session_id,
        )
        event = BillAcceptedEvent(
            pulse_count=signal.pulse_count,
            amount=amount,
            status=PaymentStatus.VALIDATED,
            received_at=signal.received_at,
            session_id=session_id,
        )

        # Update session total if a session is active
        if session_id:
            await _credit_session(session_id, amount)

    # Persist the payment event
    await save_payment(event)

    # Notify all WebSocket clients
    ws_message = WSMessage(
        type=WSMessageType.BILL_ACCEPTED,
        payload=event.model_dump(mode="json"),
    )
    await manager.broadcast(ws_message.model_dump_json())

    return event


async def _credit_session(session_id: str, amount: float) -> None:
    """Add the paid amount to the session and mark it as PAID."""
    from app.core.database import get_session

    session = await get_session(session_id)
    if session is None:
        logger.warning("Session %s not found while crediting payment", session_id)
        return

    new_total = session.total_paid + amount
    await update_session(
        session_id,
        SessionUpdate(status=SessionStatus.PAID, total_paid=new_total),
    )

    # Broadcast the session update too
    from app.core.database import get_session as gs
    updated = await gs(session_id)
    if updated:
        ws_message = WSMessage(
            type=WSMessageType.SESSION_UPDATED,
            payload=updated.model_dump(mode="json"),
        )
        await manager.broadcast(ws_message.model_dump_json())
