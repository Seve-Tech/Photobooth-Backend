"""
Security utilities for the Photobooth backend.

Two protection mechanisms are provided:

  1. API Key guard    — every REST request must include an X-API-Key header.
                        Works exactly like a webhook secret you're already familiar with.

  2. WS Rate Limiter — limits how many messages a single WebSocket client
                        can send per 60-second window.
"""

import logging
import time

from fastapi import Header, HTTPException, WebSocket, status

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── REST: API-Key dependency ──────────────────────────────────────────────────


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency — attach this to any route that should be protected.

    The caller must include the header:
        X-API-Key: <your secret key>

    Returns 403 Forbidden for both a missing header and a wrong value.
    We use 403 (not 401) because 401 implies there is a login flow — this
    is a shared-secret scheme, so "Forbidden" is more accurate.

    Usage on a route:
        @router.get("/example", dependencies=[Depends(verify_api_key)])

    Or on a whole router:
        router = APIRouter(dependencies=[Depends(verify_api_key)])
    """
    if x_api_key != settings.api_key:
        logger.warning("Rejected request: invalid or missing API key.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )


# ── WebSocket: API-Key check (query param) ────────────────────────────────────


async def verify_ws_api_key(websocket: WebSocket, api_key: str | None) -> bool:
    """
    Validate the API key sent as a WebSocket URL query parameter.

    The client connects like:
        ws://localhost:8000/ws?api_key=<your secret key>

    Returns True if the key is valid.
    Closes the socket with code 4001 and returns False if the key is wrong.
    """
    # Fallback to query_params if parameter extraction failed
    if api_key is None:
        api_key = websocket.query_params.get("api_key")

    # logger.debug("verify_ws_api_key: received api_key=%r, expected=%r", api_key, settings.api_key)

    if api_key != settings.api_key:
        logger.warning(
            "Rejected WebSocket connection: invalid or missing API key. Received: %r, Expected: %r",
            api_key,
            settings.api_key
        )
        await websocket.close(code=4001, reason="Invalid or missing API key.")
        return False
    return True


# ── WebSocket: Rate Limiter ───────────────────────────────────────────────────


class WSRateLimiter:
    """
    Simple in-memory sliding-window rate limiter for WebSocket connections.

    Each connected WebSocket gets its own counter that resets every 60 seconds.
    If a client sends more messages than the allowed maximum within the window,
    is_allowed() returns False — the endpoint can then send them an error.

    Example with default settings (30 msgs / 60 s):
        A bill acceptor sending 5 pulses takes ~5 messages → well within limit.
        A misbehaving client spamming 100 msgs/s will be blocked after 30 msgs.
    """

    def __init__(self, max_messages: int, window_seconds: int = 60) -> None:
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        # Maps id(websocket) → (message_count, window_start_time)
        self._counts: dict[int, tuple[int, float]] = {}

    def is_allowed(self, websocket: WebSocket) -> bool:
        """
        Record one incoming message for this WebSocket client and check
        whether they are still within the allowed rate.

        Returns True  → message is allowed, process normally.
        Returns False → client has exceeded the rate limit.
        """
        ws_id = id(websocket)
        now = time.monotonic()
        count, window_start = self._counts.get(ws_id, (0, now))

        # If the current window has expired, start a fresh one
        if now - window_start >= self.window_seconds:
            count = 0
            window_start = now

        count += 1
        self._counts[ws_id] = (count, window_start)

        if count > self.max_messages:
            logger.warning(
                "WS rate limit exceeded: client %d sent %d msgs in %.1fs window.",
                ws_id,
                count,
                self.window_seconds,
            )
            return False
        return True

    def remove(self, websocket: WebSocket) -> None:
        """Clean up tracking state when a client disconnects."""
        self._counts.pop(id(websocket), None)


# Singleton shared across all WebSocket connections
# max_messages is read from settings so you can tune it via .env
ws_rate_limiter = WSRateLimiter(
    max_messages=settings.ws_rate_limit,
    window_seconds=60,
)
