from fastapi import APIRouter

from app.core.config import settings
from app.core.database import ping_db
from app.models.schemas import HealthResponse
from app.websocket.manager import manager

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Quick liveness + readiness check."""
    db_ok = await ping_db()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        db_connected=db_ok,
    )


@router.get("/health/ws")
async def ws_health() -> dict:
    """Show how many WebSocket clients are currently connected."""
    return {"connected_clients": manager.client_count}
