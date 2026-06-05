"""
DSLRBooth photo session endpoints.
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import verify_api_key
from app.db import (
    get_session,
    update_session,
    complete_session,
    get_active_photo_session,
)
from app.models.schemas import (
    SessionResponse,
    SessionStatus,
    SessionUpdate,
    WSMessage,
    WSMessageType,
)
from app.services.dslrbooth_service import dslrbooth_service
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/photo-session",
    tags=["photo-session"],
)


class StartSessionRequest(BaseModel):
    session_id: str


async def _schedule_session_timeout(session_id: str, timeout_seconds: int) -> None:
    """Background safety net to recover the session status if the trigger never fires."""
    await asyncio.sleep(timeout_seconds)
    try:
        session = await get_session(session_id)
        if session and session.status == SessionStatus.PHOTO_ACTIVE:
            logger.warning(
                "Session %s timed out waiting for DSLRBooth session_end webhook trigger",
                session_id,
            )
            # Force transition to COMPLETED (or we could go to cancel/error, but COMPLETED allows recovery)
            updated = await update_session(
                session_id, SessionUpdate(status=SessionStatus.COMPLETED)
            )
            if updated:
                # Broadcast error and status change
                err_msg = WSMessage(
                    type=WSMessageType.PHOTO_SESSION_ERROR,
                    payload={
                        "session_id": session_id,
                        "detail": "Photo capture timed out. Restoring kiosk interface.",
                    },
                )
                await manager.broadcast(err_msg.model_dump_json())

                sess_msg = WSMessage(
                    type=WSMessageType.SESSION_UPDATED,
                    payload=updated.model_dump(mode="json"),
                )
                await manager.broadcast(sess_msg.model_dump_json())
    except Exception as exc:
        logger.error(
            "Error handling session timeout for session %s: %s", session_id, exc
        )


@router.post("/start", response_model=dict)
async def start_photo_session(
    body: StartSessionRequest,
    background_tasks: BackgroundTasks,
    _ = Depends(verify_api_key),
) -> dict:
    """
    Trigger DSLRBooth to start a photo session for the given session_id.
    """
    session = await get_session(body.session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{body.session_id}' not found"
        )

    # 1. Check if DSLRBooth is reachable
    if not await dslrbooth_service.is_reachable():
        raise HTTPException(
            status_code=503,
            detail="DSLRBooth API is unreachable. Please make sure the app is running.",
        )

    # 2. Update DB status to PHOTO_ACTIVE
    updated = await update_session(
        body.session_id, SessionUpdate(status=SessionStatus.PHOTO_ACTIVE)
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update session status")

    # 3. Call DSLRBooth API
    result = await dslrbooth_service.start_session(settings.dslrbooth_booth_mode)
    if not result.IsSuccessful:
        # Revert status back to PAID if we failed to launch
        await update_session(
            body.session_id, SessionUpdate(status=SessionStatus.PAID)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to start DSLRBooth: {result.ErrorMessage}",
        )

    # 4. Broadcast to WebSockets
    msg = WSMessage(
        type=WSMessageType.PHOTO_SESSION_STARTED,
        payload=updated.model_dump(mode="json"),
    )
    await manager.broadcast(msg.model_dump_json())

    # 5. Schedule timeout safety net
    background_tasks.add_task(
        _schedule_session_timeout, body.session_id, settings.dslrbooth_session_timeout_s
    )

    return {
        "status": "launched",
        "session_id": body.session_id,
        "booth_mode": settings.dslrbooth_booth_mode,
    }


@router.get("/webhook")
async def dslrbooth_webhook(
    event_type: str = Query(..., alias="event_type"),
    param1: str | None = Query(None, alias="param1"),
    param2: str | None = Query(None, alias="param2"),
    param3: str | None = Query(None, alias="param3"),
    param4: str | None = Query(None, alias="param4"),
) -> dict:
    """
    Webhook endpoint called by DSLRBooth triggers (HTTP GET).
    Configured in DSLRBooth settings.
    """
    logger.info(
        "DSLRBooth webhook received: event_type=%s, param1=%s, param2=%s, param3=%s, param4=%s",
        event_type,
        param1,
        param2,
        param3,
        param4,
    )

    # 1. Broadcast event for frontend UI visibility
    status_msg = WSMessage(
        type=WSMessageType.DSLRBOOTH_STATUS,
        payload={
            "event_type": event_type,
            "param1": param1,
            "param2": param2,
            "param3": param3,
            "param4": param4,
        },
    )
    await manager.broadcast(status_msg.model_dump_json())

    # 2. Look up the current active photo session
    active_session = await get_active_photo_session()

    if active_session:
        session_id = active_session.id
        if event_type == "session_end":
            logger.info(
                "DSLRBooth session ended. Completing session %s in DB.", session_id
            )
            # Update status to PHOTO_COMPLETE in DB
            updated = await update_session(
                session_id, SessionUpdate(status=SessionStatus.PHOTO_COMPLETE)
            )
            if updated:
                # Notify frontend of completion
                comp_msg = WSMessage(
                    type=WSMessageType.PHOTO_SESSION_COMPLETE,
                    payload=updated.model_dump(mode="json"),
                )
                await manager.broadcast(comp_msg.model_dump_json())
    else:
        logger.warning(
            "Received DSLRBooth webhook '%s' but no active photo session was found in DB.",
            event_type,
        )

    return {"status": "success", "event_type": event_type}


@router.post("/complete/{session_id}", response_model=SessionResponse)
async def complete_photo_session(
    session_id: str,
    _ = Depends(verify_api_key),
) -> SessionResponse:
    """
    Explicitly complete a photo session, transitioning its status to COMPLETED.
    Called by the frontend when transitioning from the thank-you screen to IDLE.
    """
    logger.info("Marking photo session %s as COMPLETED", session_id)
    updated = await complete_session(session_id)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found"
        )

    # Broadcast updated session details
    msg = WSMessage(
        type=WSMessageType.SESSION_UPDATED,
        payload=updated.model_dump(mode="json"),
    )
    await manager.broadcast(msg.model_dump_json())

    return updated
