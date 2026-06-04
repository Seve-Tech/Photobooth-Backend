"""
Admin PIN REST endpoints.

Two endpoints protect the kiosk admin dashboard:
  POST /api/v1/admin/verify-pin  — verify a PIN attempt (used by the PIN modal)
  PATCH /api/v1/admin/pin        — change the stored PIN (used by Security Settings)

Both endpoints require the X-API-Key header (same as all other REST routes).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.security import verify_api_key, hash_pin, verify_pin
from app.db.admin_settings import get_admin_pin_hash, upsert_admin_pin
from app.models.schemas import AdminPinVerifyRequest, AdminPinChangeRequest

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
