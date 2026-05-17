"""
WebSocket connection manager.

Keeps track of all active WebSocket clients and lets any part of
the app broadcast messages to everyone connected.
"""

import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # List of currently connected WebSocket clients
        self._active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.append(websocket)
        logger.info("WS client connected. Total: %d", len(self._active))

    def disconnect(self, websocket: WebSocket) -> None:
        self._active.remove(websocket)
        logger.info("WS client disconnected. Total: %d", len(self._active))

    async def send_to(self, websocket: WebSocket, message: str) -> None:
        """Send a JSON string to a single client."""
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        """Broadcast a JSON string to every connected client."""
        dead: list[WebSocket] = []
        for ws in self._active:
            try:
                await ws.send_text(message)
            except Exception:
                # Client disconnected mid-send; clean up after the loop
                dead.append(ws)

        for ws in dead:
            self._active.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._active)


# Singleton shared across the app
manager = ConnectionManager()
