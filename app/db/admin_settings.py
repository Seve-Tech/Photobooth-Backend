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


async def get_default_theme(unit_id: int) -> dict:
    """
    Fetch the default theme configuration for the given unit.
    """
    pool = get_pool()

    query = """
        SELECT default_theme, plain_theme_name, plain_theme_bg_color, plain_theme_text_color,
               plain_theme_font_family, plain_theme_font_family_subtitle,
               plain_theme_font_family_body, active_plain_theme_id
        FROM admin_settings
        WHERE unit_id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, unit_id)

    if row:
        res = dict(row)
        if not res.get("default_theme"):
            res["default_theme"] = "neon"
        return res
    return {"default_theme": "neon"}


async def update_default_theme(
    unit_id: int,
    theme: str,
    plain_theme_name: str | None = None,
    plain_theme_bg_color: str | None = None,
    plain_theme_text_color: str | None = None,
    plain_theme_font_family: str | None = None,
    plain_theme_font_family_subtitle: str | None = None,
    plain_theme_font_family_body: str | None = None,
    active_plain_theme_id: str | None = None,
) -> None:
    """
    Update the default theme for the given unit.
    """
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        UPDATE admin_settings
        SET default_theme = $1,
            plain_theme_name = COALESCE($2, plain_theme_name),
            plain_theme_bg_color = COALESCE($3, plain_theme_bg_color),
            plain_theme_text_color = COALESCE($4, plain_theme_text_color),
            plain_theme_font_family = COALESCE($5, plain_theme_font_family),
            plain_theme_font_family_subtitle = COALESCE($6, plain_theme_font_family_subtitle),
            plain_theme_font_family_body = COALESCE($7, plain_theme_font_family_body),
            active_plain_theme_id = COALESCE($8, active_plain_theme_id),
            updated_at = $9
        WHERE unit_id = $10
    """

    async with pool.acquire() as conn:
        await conn.execute(
            query,
            theme,
            plain_theme_name,
            plain_theme_bg_color,
            plain_theme_text_color,
            plain_theme_font_family,
            plain_theme_font_family_subtitle,
            plain_theme_font_family_body,
            active_plain_theme_id,
            now,
            unit_id,
        )

