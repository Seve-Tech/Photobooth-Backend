import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import bills, health, sessions
from app.api.routes import admin as admin_routes
from app.core.config import settings
from app.db import init_db, close_db
from app.websocket.endpoints import router as ws_router

from app.db.admin_settings import get_admin_pin_hash, upsert_admin_pin
from app.core.security import hash_pin

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

    # Seed the default admin PIN (000000) if this unit has no PIN stored yet.
    # This runs harmlessly on every restart after the first seed.
    existing_hash = await get_admin_pin_hash(settings.unit_id)
    if existing_hash is None:
        await upsert_admin_pin(settings.unit_id, hash_pin("000000"))
        logger.info("Seeded default admin PIN (000000) for unit %d.", settings.unit_id)

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
    app.include_router(bills.router,         prefix="/api/v1")
    app.include_router(sessions.router,      prefix="/api/v1")
    app.include_router(admin_routes.router,  prefix="/api/v1")

    # ── WebSocket ─────────────────────────────────────────────────────────────
    app.include_router(ws_router)

    return app
