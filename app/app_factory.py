import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import bills, health, sessions
from app.core.config import settings
from app.db import init_db, close_db
from app.websocket.endpoints import router as ws_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the asyncpg connection pool for the lifetime of the application."""
    logger.info("Starting up — initialising database connection pool...")
    await init_db()
    logger.info("Database pool ready.")
    yield
    logger.info("Shutting down — closing database connection pool...")
    await close_db()
    logger.info("Database pool closed.")


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST routes ───────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(bills.router,    prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")

    # ── WebSocket ─────────────────────────────────────────────────────────────
    app.include_router(ws_router)

    return app
