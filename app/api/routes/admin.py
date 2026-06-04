"""
Admin PIN + dashboard REST endpoints.

Endpoints:
  POST  /api/v1/admin/verify-pin       — verify a PIN attempt (used by the PIN modal)
  PATCH /api/v1/admin/pin              — change the stored PIN (Security Settings)
  GET   /api/v1/admin/sessions         — paginated sessions list (Transactions tab)
  GET   /api/v1/admin/logs             — paginated hardware/device events (Logs tab)
  GET   /api/v1/admin/package-price    — read Package 1 current price (Settings tab)
  PATCH /api/v1/admin/package-price    — update a package price (Settings tab)
  GET   /api/v1/admin/theme            — get the default theme for the kiosk
  PATCH /api/v1/admin/theme            — update the default theme for the kiosk

All endpoints require the X-API-Key header.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.security import verify_api_key, hash_pin, verify_pin
from app.db.admin_settings import (
    get_admin_pin_hash,
    upsert_admin_pin,
    get_default_theme,
    update_default_theme,
)
from app.db.sessions import list_sessions, count_sessions
from app.db.device_events import list_device_events, count_device_events
from app.db.packages import update_package_price, get_package_price
from app.models.schemas import (
    AdminPinVerifyRequest,
    AdminPinChangeRequest,
    PaginatedSessions,
    PackagePriceUpdate,
    ThemeUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_api_key)],
)

# The fallback hash is pre-computed once at module load to avoid hashing on
# every request when no PIN row exists in the DB yet.
_DEFAULT_PIN = "000000"


@router.post(
    "/verify-pin",
    status_code=status.HTTP_200_OK,
    summary="Verify the admin PIN",
)
async def verify_admin_pin(body: AdminPinVerifyRequest) -> dict:
    """
    Check whether the supplied PIN matches the one stored in the database.

    Returns 200 OK on success.
    Returns 401 Unauthorized if the PIN is wrong.

    If no PIN has been seeded yet (edge case on a brand-new unit before the
    startup seed runs), falls back to comparing against the default '000000'.
    """
    stored_hash = await get_admin_pin_hash(settings.unit_id)

    if stored_hash is None:
        # Startup seed hasn't run yet — accept the default PIN and seed it now.
        logger.warning(
            "No admin PIN found in DB for unit %d — seeding default PIN.",
            settings.unit_id,
        )
        default_hash = hash_pin(_DEFAULT_PIN)
        await upsert_admin_pin(settings.unit_id, default_hash)
        stored_hash = default_hash

    if not verify_pin(body.pin, stored_hash):
        logger.warning("Failed admin PIN attempt for unit %d.", settings.unit_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    logger.info("Admin PIN verified successfully for unit %d.", settings.unit_id)
    return {"detail": "PIN verified."}


@router.patch(
    "/pin",
    status_code=status.HTTP_200_OK,
    summary="Change the admin PIN",
)
async def change_admin_pin(body: AdminPinChangeRequest) -> dict:
    """
    Replace the stored admin PIN with a new one.

    The new PIN is bcrypt-hashed before storage — the plain-text value is
    never persisted.
    """
    new_hash = hash_pin(body.new_pin)
    await upsert_admin_pin(settings.unit_id, new_hash)

    logger.info("Admin PIN updated for unit %d.", settings.unit_id)
    return {"detail": "PIN updated successfully."}


@router.get(
    "/sessions",
    response_model=PaginatedSessions,
    summary="Paginated sessions list for the admin dashboard",
)
async def admin_list_sessions(
    limit: int = Query(default=100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip"),
) -> PaginatedSessions:
    """
    Return a paginated list of all photobooth sessions ordered by most-recent
    first. Used by the Logs & Transactions tab and the Overview stats.
    """
    items = await list_sessions(limit=limit, offset=offset)
    total = await count_sessions()
    return PaginatedSessions(items=items, total=total)


@router.get(
    "/logs",
    summary="Paginated hardware/device event logs for the admin dashboard",
)
async def admin_list_logs(
    limit: int = Query(default=100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip"),
    severity: str | None = Query(default=None, description="Filter by severity: info | error | warning"),
) -> dict:
    """
    Return a paginated list of device events (hardware logs) ordered by
    most-recent first. Used by the Hardware Logs table in the admin dashboard.
    """
    items = await list_device_events(
        unit_id=settings.unit_id,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    total = await count_device_events(unit_id=settings.unit_id, severity=severity)
    return {"items": items, "total": total}


@router.get(
    "/package-price",
    summary="Get the current price for a package",
)
async def get_admin_package_price(
    package_id: int = Query(default=1, ge=1, description="Package ID to query"),
) -> dict:
    """
    Return the current price of a package. The admin Settings tab calls this
    on load so the UI always reflects the DB-authoritative price.
    """
    row = await get_package_price(package_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package {package_id} not found.",
        )
    return {"id": row["id"], "package_name": row["package_name"], "price": float(row["price"])}


@router.patch(
    "/package-price",
    status_code=status.HTTP_200_OK,
    summary="Update the price of a photobooth package",
)
async def update_admin_package_price(body: PackagePriceUpdate) -> dict:
    """
    Update the price of a package in the database.
    Called by the Photobooth Pricing section of System Settings.
    """
    row = await update_package_price(body.package_id, Decimal(str(body.price)))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package {body.package_id} not found.",
        )
    logger.info(
        "Package %d price updated to %.2f by admin (unit %d).",
        body.package_id,
        body.price,
        settings.unit_id,
    )
    return {"id": row["id"], "package_name": row["package_name"], "price": float(row["price"])}


@router.get(
    "/theme",
    summary="Get the default theme for the kiosk",
)
async def get_kiosk_default_theme() -> dict:
    """
    Return the default theme configured for this unit.
    """
    theme = await get_default_theme(settings.unit_id)
    return {"default_theme": theme}


@router.patch(
    "/theme",
    status_code=status.HTTP_200_OK,
    summary="Update the default theme for the kiosk",
)
async def update_kiosk_default_theme(body: ThemeUpdate) -> dict:
    """
    Update the default theme configured for this unit.
    """
    valid_themes = {"neon", "chibi", "luxury", "retro", "flowery"}
    if body.theme not in valid_themes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid theme. Must be one of {valid_themes}",
        )
    await update_default_theme(settings.unit_id, body.theme)
    logger.info("Default theme updated to '%s' for unit %d.", body.theme, settings.unit_id)
    return {"default_theme": body.theme}
