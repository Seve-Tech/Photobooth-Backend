"""
Pydantic models used across the app.

These are intentionally kept separate from any ORM models so that
when the DB layer is wired up, the DB person can map these freely.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionStatus(str, Enum):
    PENDING = "pending"       # Waiting for payment
    PAID = "paid"             # Payment received, booth unlocked
    COMPLETED = "completed"   # Photo session done
    CANCELLED = "cancelled"   # Session was cancelled


class PaymentStatus(str, Enum):
    """Hardware result from the bill acceptor machine."""
    RECEIVED = "received"     # Bill inserted by customer
    VALIDATED = "validated"   # Pulse count matched a known denomination
    REJECTED = "rejected"     # Unknown pulse count / bad signal — bill not credited


# ---------------------------------------------------------------------------
# Bill Acceptor / Pulse models
# ---------------------------------------------------------------------------


class PulseSignal(BaseModel):
    """
    Raw pulse signal coming from the Arduino / bill acceptor.
    The TB74 sends N pulses per accepted bill; the pulse count
    tells us which denomination was inserted.
    """

    pulse_count: int = Field(..., ge=1, description="Number of pulses received")
    received_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="arduino", description="Who sent this signal")


class BillAcceptedEvent(BaseModel):
    """
    Processed payment event derived from a PulseSignal.
    amount is resolved using the pulse->denomination map in settings.

    Field guide:
      acceptor_status — hardware result: did the bill acceptor physically accept the bill?
                        (VALIDATED / REJECTED)
      payment_status  — financial record: state of the payment row in the DB
                        ("completed" / "partial" / "pending")
    """

    pulse_count: int
    amount: float = Field(..., ge=0)
    currency: str = Field(default="PHP")
    acceptor_status: PaymentStatus          # hardware bill acceptor result
    received_at: datetime
    session_id: str | None = None
    payment_method: str = Field(default="cash")
    payment_status: str | None = None       # financial outcome stored in DB payments table
    reference_number: str | None = None     # reserved for future online payment integration


# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    """Payload to create a new photobooth session."""

    customer_ref: str | None = Field(
        default=None, description="Optional name or reference for the customer"
    )
    package_id: int | None = Field(
        default=None, description="Photobooth package ID (integer PK from packages table)"
    )
    paid_amount: float | None = Field(
        default=0.0, description="Optionally pass final total paid amount to create as paid session"
    )
    payment_method: str | None = Field(
        default="cash", description="Payment method used (e.g. cash, or online methods in future)"
    )


class SessionUpdate(BaseModel):
    """Partial update for an existing session."""

    status: SessionStatus | None = None
    total_paid: float | None = None
    customer_ref: str | None = None


class SessionResponse(BaseModel):
    """What the API returns when querying a session."""

    id: str
    status: SessionStatus
    total_paid: float
    currency: str
    customer_ref: str | None
    package_id: int | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# WebSocket message envelope
# ---------------------------------------------------------------------------


class WSMessageType(str, Enum):
    PULSE_RECEIVED = "pulse_received"       # Raw pulse from Arduino
    BILL_ACCEPTED = "bill_accepted"         # Processed & validated bill
    SESSION_UPDATED = "session_updated"     # Session state changed
    ERROR = "error"                         # Something went wrong
    PING = "ping"
    PONG = "pong"


class WSMessage(BaseModel):
    """
    Envelope for every WebSocket message so clients
    can discriminate on `type` without guessing the shape.
    """

    type: WSMessageType
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# API response helpers
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    db_connected: bool


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
