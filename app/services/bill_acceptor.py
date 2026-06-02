"""
Bill acceptor service.

Responsible for:
1. Translating pulse counts to PHP denominations.
2. Persisting the payment event and bill log to the database.
3. Broadcasting the event to all WebSocket subscribers.
"""

import logging
from decimal import Decimal

from app.core.config import settings
from app.db import save_payment, log_bill_accepted, get_session, create_session, get_active_pending_session
from app.models.schemas import (
    BillAcceptedEvent,
    PaymentStatus,
    PulseSignal,
    SessionCreate,
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
            acceptor_status=PaymentStatus.REJECTED,
            received_at=signal.received_at,
            session_id=session_id,
        )
    else:
        # If no session_id is provided, resolve or create one
        if not session_id:
            active_session = await get_active_pending_session()
            if active_session:
                session_id = active_session.id
                logger.info("Associated incoming bill with active pending session: %s", session_id)
            else:
                logger.info("No active pending session found. Automatically creating a new session on bill insertion.")
                new_session = await create_session(
                    SessionCreate(package_id=1, customer_ref="Guest"),
                    branch_id=settings.branch_id,
                    unit_id=settings.unit_id,
                )
                session_id = new_session.id

        logger.info(
            "Bill accepted — pulses: %d, amount: PHP %.2f, session: %s",
            signal.pulse_count,
            amount,
            session_id,
        )
        event = BillAcceptedEvent(
            pulse_count=signal.pulse_count,
            amount=amount,
            acceptor_status=PaymentStatus.VALIDATED,
            received_at=signal.received_at,
            session_id=session_id,
            payment_method="cash",
        )

        if session_id:
            await _persist_payment(event, session_id, signal)

    # Broadcast the bill event to all WebSocket clients (frontend, dashboard, etc.)
    ws_message = WSMessage(
        type=WSMessageType.BILL_ACCEPTED,
        payload=event.model_dump(mode="json"),
    )
    await manager.broadcast(ws_message.model_dump_json())

    return event


async def _persist_payment(event: BillAcceptedEvent, session_id: str, signal: PulseSignal) -> None:
    """
    Persist a validated bill payment to the database.

    save_payment() atomically in one DB transaction:
      1. Inserts a row into `payments`
      2. Updates sessions.paid_amount and payment_status

    log_bill_accepted() writes hardware-level traceability to bill_acceptor_logs.
    After persisting, the updated session is broadcast to all WebSocket clients.
    """
    try:
        await save_payment(event)
        logger.info("Payment persisted for session %s, amount: PHP %.2f", session_id, event.amount)

        await log_bill_accepted(
            session_id=session_id,
            denomination=Decimal(str(event.amount)),
            raw_signal=str(signal.pulse_count),
            hardware_status="accepted",
        )

        # Broadcast the updated session so the frontend reflects the new paid_amount
        updated = await get_session(session_id)
        if updated:
            ws_message = WSMessage(
                type=WSMessageType.SESSION_UPDATED,
                payload=updated.model_dump(mode="json"),
            )
            await manager.broadcast(ws_message.model_dump_json())

    except Exception as exc:
        logger.error(
            "Failed to persist payment for session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
