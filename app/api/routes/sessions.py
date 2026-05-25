"""
Session REST endpoints.

Sessions represent a single customer's photobooth interaction.
The front-end uses these to create / track / complete sessions.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import (
    create_session,
    get_session,
    list_sessions,
    update_session,
)
from app.core.security import verify_api_key
from app.models.schemas import (
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    WSMessage,
    WSMessageType,
)
from app.websocket.manager import manager

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(verify_api_key)],  # All session endpoints require X-API-Key
)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_new_session(body: SessionCreate) -> SessionResponse:
    """Start a new photobooth session (status starts as PENDING)."""
    session = await create_session(body)

    # Notify WebSocket subscribers that a session was created
    msg = WSMessage(
        type=WSMessageType.SESSION_UPDATED,
        payload=session.model_dump(mode="json"),
    )
    await manager.broadcast(msg.model_dump_json())

    return session


@router.get("", response_model=list[SessionResponse])
async def get_all_sessions() -> list[SessionResponse]:
    """Return all sessions (useful for admin / dashboard)."""
    return await list_sessions()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_one_session(session_id: str) -> SessionResponse:
    """Get a single session by its ID."""
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def patch_session(session_id: str, body: SessionUpdate) -> SessionResponse:
    """
    Partially update a session (e.g. mark as COMPLETED after photos are taken).
    """
    session = await update_session(session_id, body)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Broadcast the change
    msg = WSMessage(
        type=WSMessageType.SESSION_UPDATED,
        payload=session.model_dump(mode="json"),
    )
    await manager.broadcast(msg.model_dump_json())

    return session
