import uuid
from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def save_photo(
    session_id: str,
    shot_number: int,
    original_file_path: str,
    processed_file_path: str | None = None,
    thumbnail_path: str | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    async with pool.acquire() as conn:
        async with conn.transaction():

            insert_photo = """
                INSERT INTO photos (
                    session_id,
                    shot_number,
                    original_file_path,
                    processed_file_path,
                    thumbnail_path,
                    captured_at,
                    is_printed,
                    created_at
                )
                SELECT
                    s.id,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    0,
                    $6
                FROM sessions s
                WHERE s.session_uuid = $1
                RETURNING *
            """

            row = await conn.fetchrow(insert_photo, uuid.UUID(session_id), shot_number, original_file_path, processed_file_path, thumbnail_path, now)

            if row is None:
                raise ValueError(f"Session '{session_id}' not found.")

            await conn.execute(
                """
                UPDATE sessions
                SET
                    total_photos_taken = total_photos_taken + 1,
                    updated_at = $1
                WHERE session_uuid = $2
                """,
                now,
                uuid.UUID(session_id),
            )

    return row_to_dict(row)


async def get_photo(photo_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        SELECT * FROM photos
        WHERE id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, photo_id)

    return row_to_dict(row) if row else None


async def list_photos(session_id: str) -> list[dict[str, Any]]:
    pool = get_pool()

    query = """
        SELECT p.*
        FROM photos p
        JOIN sessions s ON s.id = p.session_id
        WHERE s.session_uuid = $1
        ORDER BY p.shot_number ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, uuid.UUID(session_id))

    return [row_to_dict(r) for r in rows]


async def mark_photo_printed(photo_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        UPDATE photos
        SET is_printed = 1
        WHERE id = $1
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, photo_id)

    return row_to_dict(row) if row else None