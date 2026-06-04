"""
Database helpers for admin_settings table.

Stores one row per photobooth unit containing the bcrypt-hashed admin PIN.
The PIN is never stored in plain text.
"""

from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def get_admin_pin_hash(unit_id: int) -> str | None:
    """
    Fetch the current hashed PIN for the given unit.
    Returns None if no PIN has been set yet (first boot before seeding).
    """
    pool = get_pool()

    query = """
        SELECT pin_hash
        FROM admin_settings
        WHERE unit_id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, unit_id)

    return row["pin_hash"] if row else None


async def upsert_admin_pin(unit_id: int, new_hash: str) -> None:
    """
    Insert or update the hashed PIN for the given unit.
    Uses ON CONFLICT so this is safe to call on first boot (insert)
    and on subsequent PIN changes (update).
    """
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO admin_settings (unit_id, pin_hash, updated_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (unit_id)
        DO UPDATE SET
            pin_hash   = EXCLUDED.pin_hash,
            updated_at = EXCLUDED.updated_at
    """

    async with pool.acquire() as conn:
        await conn.execute(query, unit_id, new_hash, now)


async def get_default_theme(unit_id: int) -> str:
    """
    Fetch the default theme configured for the given unit.
    Returns 'neon' if not configured yet.
    """
    pool = get_pool()

    query = """
        SELECT default_theme
        FROM admin_settings
        WHERE unit_id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, unit_id)

    return row["default_theme"] if row and row["default_theme"] else "neon"


async def update_default_theme(unit_id: int, theme: str) -> None:
    """
    Update the default theme for the given unit.
    """
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        UPDATE admin_settings
        SET default_theme = $1, updated_at = $2
        WHERE unit_id = $3
    """

    async with pool.acquire() as conn:
        await conn.execute(query, theme, now, unit_id)

