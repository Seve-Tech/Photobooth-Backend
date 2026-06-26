import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.bill_acceptor import validate_amount, handle_amount
from app.models.schemas import AmountSignal, PaymentStatus, BillAcceptedEvent


def test_validate_amount():
    """Test PHP amount validation."""
    assert validate_amount(50.0) is True
    assert validate_amount(100.0) is True
    assert validate_amount(150.0) is True
    assert validate_amount(200.0) is True
    assert validate_amount(250.0) is True
    assert validate_amount(20.0) is False  # Removed denomination
    assert validate_amount(99.0) is False  # Invalid amount


@pytest.mark.asyncio
@patch("app.services.bill_acceptor.manager.broadcast", new_callable=AsyncMock)
async def test_handle_amount_invalid(mock_broadcast):
    """Test handling an invalid amount (e.g. noise/unsupported coin)."""
    signal = AmountSignal(amount=99.0, received_at=datetime.utcnow(), source="arduino")
    
    event = await handle_amount(signal)
    
    # Verify the event is marked as rejected
    assert event.amount == 99.0
    assert event.acceptor_status == PaymentStatus.REJECTED
    assert event.pulse_count is None
    
    # Verify broadcast was called with the rejected event
    assert mock_broadcast.called


@pytest.mark.asyncio
@patch("app.services.bill_acceptor._persist_payment", new_callable=AsyncMock)
@patch("app.services.bill_acceptor.manager.broadcast", new_callable=AsyncMock)
async def test_handle_amount_valid_with_session(mock_broadcast, mock_persist):
    """Test handling a valid amount when an active session exists."""
    signal = AmountSignal(amount=100.0, received_at=datetime.utcnow(), source="arduino")
    session_id = "test-session-uuid"
    
    event = await handle_amount(signal, session_id=session_id)
    
    # Verify the event was validated and amount resolved correctly
    assert event.amount == 100.0
    assert event.acceptor_status == PaymentStatus.VALIDATED
    assert event.session_id == session_id
    
    # Verify we tried to persist it to the DB
    mock_persist.assert_called_once_with(event, session_id, signal)
    
    # Verify we broadcasted the event
    assert mock_broadcast.called
