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
    PHOTO_ACTIVE = "photo_active"    # DSLRBooth session is currently active
    PHOTO_COMPLETE = "photo_complete" # DSLRBooth session has completed
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


class AmountSignal(BaseModel):
    """
    Raw amount signal coming from the Arduino / bill acceptor.
    The Arduino itself now translates pulse counts to the actual PHP amount.
    """

    amount: float = Field(..., ge=0.0, description="Amount received in PHP")
    received_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="arduino", description="Who sent this signal")


class BillAcceptedEvent(BaseModel):
    """
    Processed payment event derived from an AmountSignal.

    Field guide:
      acceptor_status — hardware result: did the bill acceptor physically accept the bill?
                        (VALIDATED / REJECTED)
      payment_status  — financial record: state of the payment row in the DB
                        ("completed" / "partial" / "pending")
    """

    pulse_count: int | None = None
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
    AMOUNT_RECEIVED = "amount_received"     # Raw amount from Arduino
    BILL_ACCEPTED = "bill_accepted"         # Processed & validated bill
    SESSION_UPDATED = "session_updated"     # Session state changed
    ERROR = "error"                         # Something went wrong
    PING = "ping"
    PONG = "pong"
    PHOTO_SESSION_STARTED = "photo_session_started"   # DSLRBooth session started
    PHOTO_SESSION_COMPLETE = "photo_session_complete" # DSLRBooth session finished
    PHOTO_SESSION_ERROR = "photo_session_error"       # DSLRBooth session failed
    DSLRBOOTH_STATUS = "dslrbooth_status"             # DSLRBooth event webhook updates
    HARDWARE_STATUS = "hardware_status"               # Arduino hardware connection updates


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


# ---------------------------------------------------------------------------
# Admin PIN models
# ---------------------------------------------------------------------------


class AdminPinVerifyRequest(BaseModel):
    """Payload to verify the admin PIN at the login modal."""

    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class AdminPinChangeRequest(BaseModel):
    """Payload to set a new 6-digit admin PIN."""

    new_pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


# ---------------------------------------------------------------------------
# Admin data / dashboard models
# ---------------------------------------------------------------------------


class PaginatedSessions(BaseModel):
    """Paginated response for the admin sessions list endpoint."""

    items: list[SessionResponse]
    total: int


class PackagePriceUpdate(BaseModel):
    """Payload to update a package price from the admin dashboard."""

    package_id: int = Field(..., gt=0, description="ID of the package to update")
    price: float = Field(..., ge=0, description="New price in PHP (0 = free mode)")


class ThemeUpdate(BaseModel):
    """Payload to update the default kiosk theme from the admin dashboard."""

    theme: str = Field(..., description="Theme name (e.g. 'neon', 'chibi', 'luxury', 'retro', 'flowery', 'plain')")
    plain_theme_name: str | None = None
    plain_theme_bg_color: str | None = None
    plain_theme_text_color: str | None = None
    plain_theme_font_family: str | None = None
    plain_theme_font_family_subtitle: str | None = None
    plain_theme_font_family_body: str | None = None
    plain_theme_text_title: str | None = None
    plain_theme_text_subtitle: str | None = None
    plain_theme_text_header: str | None = None
    plain_theme_text_payment: str | None = None
    plain_theme_text_instruction: str | None = None
    active_plain_theme_id: str | None = None


# ---------------------------------------------------------------------------
# Branch models
# ---------------------------------------------------------------------------


class BranchCreate(BaseModel):
    """Payload to create a new branch."""

    branch_code: str = Field(..., max_length=50)
    branch_name: str = Field(..., max_length=255)
    owner_name: str = Field(..., max_length=255)
    contact_number: str = Field(..., max_length=50)
    address: str


class BranchUpdate(BaseModel):
    """Payload to update an existing branch."""

    branch_code: str | None = Field(None, max_length=50)
    branch_name: str | None = Field(None, max_length=255)
    owner_name: str | None = Field(None, max_length=255)
    contact_number: str | None = Field(None, max_length=50)
    address: str | None = None


class BranchResponse(BaseModel):
    """What the API returns when querying a branch."""

    id: int
    branch_code: str
    branch_name: str
    owner_name: str
    contact_number: str
    address: str
    created_at: datetime



