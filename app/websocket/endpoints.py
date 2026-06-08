"""
WebSocket endpoint.

Two types of clients connect here:
  1. The Arduino bridge (or mock) — sends pulse signals.
  2. The front-end — subscribes to real-time events.

Both use the same endpoint; message `type` tells them apart.

Security:
  - Clients must provide the API key as a query param:
      ws://localhost:8000/ws?api_key=<your_key>
  - Messages are rate-limited to WS_RATE_LIMIT per minute (default: 30).
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import verify_ws_api_key, ws_rate_limiter
from app.db import log_device_event
from app.models.schemas import AmountSignal, WSMessage, WSMessageType
from app.services.bill_acceptor import handle_amount
from app.websocket.manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


async def _log(event_type: str, message: str, severity: str = "info") -> None:
    try:
        await log_device_event(settings.unit_id, event_type, message, severity)
    except Exception:
        pass


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str | None = None,
) -> None:
    """
    Main WebSocket gate.

    Connect with:
        ws://localhost:8000/ws?api_key=<your_key>

    Expected incoming message shape:
        {
            "type": "pulse_received",
            "payload": { "pulse_count": 3, "source": "arduino" }
        }

    All other connected clients will receive broadcast events
    (bill_accepted, session_updated, etc.) automatically.
    """
    
    # verify_ws_api_key closes the socket with code 4001 if the key is wrong.
    if not await verify_ws_api_key(websocket, api_key):
        return  # Socket is already closed; nothing more to do.

    await manager.connect(websocket)
    await _log("ws_client_connected", "WebSocket client connected", "info")

    try:
        while True:
            raw = await websocket.receive_text()

            if not ws_rate_limiter.is_allowed(websocket):
                error = WSMessage(
                    type=WSMessageType.ERROR,
                    payload={"detail": "Rate limit exceeded. Slow down your messages."},
                )
                await manager.send_to(websocket, error.model_dump_json())
                await _log("ws_rate_limit", "WebSocket message rate limit exceeded", "warning")
                continue  # Drop the message but keep the connection open.

            await _handle_message(websocket, raw)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        ws_rate_limiter.remove(websocket)
        await _log("ws_client_disconnected", "WebSocket client disconnected", "info")
    except Exception as exc:
        logger.exception("Unexpected WebSocket error: %s", exc)
        manager.disconnect(websocket)
        ws_rate_limiter.remove(websocket)


async def _handle_message(websocket: WebSocket, raw: str) -> None:
    """Parse and dispatch an incoming WebSocket message."""
    try:
        data = json.loads(raw)
        msg = WSMessage(**data)
    except Exception:
        error = WSMessage(
            type=WSMessageType.ERROR,
            payload={"detail": "Invalid message format. Expected WSMessage JSON."},
        )
        await manager.send_to(websocket, error.model_dump_json())
        return

    match msg.type:
        case WSMessageType.PING:
            pong = WSMessage(type=WSMessageType.PONG)
            await manager.send_to(websocket, pong.model_dump_json())

        case WSMessageType.AMOUNT_RECEIVED:
            try:
                signal = AmountSignal(**msg.payload)
                session_id: str | None = msg.payload.get("session_id")
                await handle_amount(signal, session_id=session_id)
            except Exception as exc:
                logger.exception("Failed to handle amount: %s", exc)
                error = WSMessage(
                    type=WSMessageType.ERROR,
                    payload={"detail": f"Failed to process amount: {exc}"},
                )
                await manager.send_to(websocket, error.model_dump_json())

        case _:
            logger.debug("Unhandled WS message type: %s", msg.type)
            await _log("ws_unknown_message", f"Unhandled WS message type: {msg.type}", "warning")
