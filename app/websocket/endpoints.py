"""
WebSocket endpoint.

Two types of clients connect here:
  1. The Arduino bridge (or mock) — sends pulse signals.
  2. The front-end — subscribes to real-time events.

Both use the same endpoint; message `type` tells them apart.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.schemas import PulseSignal, WSMessage, WSMessageType
from app.services.bill_acceptor import handle_pulse
from app.websocket.manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Main WebSocket gate.

    Expected incoming message shape:
        {
            "type": "pulse_received",
            "payload": { "pulse_count": 3, "source": "arduino" }
        }

    All other connected clients will receive broadcast events
    (bill_accepted, session_updated, etc.) automatically.
    """
    await manager.connect(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            await _handle_message(websocket, raw)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.exception("Unexpected WebSocket error: %s", exc)
        manager.disconnect(websocket)


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

        case WSMessageType.PULSE_RECEIVED:
            try:
                signal = PulseSignal(**msg.payload)
                session_id: str | None = msg.payload.get("session_id")
                await handle_pulse(signal, session_id=session_id)
            except Exception as exc:
                logger.exception("Failed to handle pulse: %s", exc)
                error = WSMessage(
                    type=WSMessageType.ERROR,
                    payload={"detail": f"Failed to process pulse: {exc}"},
                )
                await manager.send_to(websocket, error.model_dump_json())

        case _:
            logger.debug("Unhandled WS message type: %s", msg.type)
