import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.bill_acceptor import resolve_amount, handle_pulse
from app.models.schemas import PulseSignal, PaymentStatus, BillAcceptedEvent


def test_resolve_amount():
    """Test pulse to PHP amount mapping."""
    assert resolve_amount(1) == 20.0
    assert resolve_amount(3) == 100.0
    assert resolve_amount(99) is None  # Unknown pulse


@pytest.mark.asyncio
@patch("app.services.bill_acceptor.manager.broadcast", new_callable=AsyncMock)
async def test_handle_pulse_invalid(mock_broadcast):
    """Test handling an unknown pulse count (e.g. noise from hardware)."""
    signal = PulseSignal(pulse_count=99, received_at=datetime.utcnow(), source="arduino")
    
    event = await handle_pulse(signal)
    
    # Verify the event is marked as rejected
    assert event.amount == 0.0
    assert event.acceptor_status == PaymentStatus.REJECTED
    assert event.pulse_count == 99
    
    # Verify broadcast was called with the rejected event
    assert mock_broadcast.called


@pytest.mark.asyncio
@patch("app.services.bill_acceptor._persist_payment", new_callable=AsyncMock)
@patch("app.services.bill_acceptor.manager.broadcast", new_callable=AsyncMock)
async def test_handle_pulse_valid_with_session(mock_broadcast, mock_persist):
    """Test handling a valid pulse when an active session exists."""
    signal = PulseSignal(pulse_count=3, received_at=datetime.utcnow(), source="arduino")
    session_id = "test-session-uuid"
    
    event = await handle_pulse(signal, session_id=session_id)
    
    # Verify the event was validated and amount resolved correctly
    assert event.amount == 100.0
    assert event.acceptor_status == PaymentStatus.VALIDATED
    assert event.session_id == session_id
    
    # Verify we tried to persist it to the DB
    mock_persist.assert_called_once_with(event, session_id, signal)
    
    # Verify we broadcasted the event
    assert mock_broadcast.called
