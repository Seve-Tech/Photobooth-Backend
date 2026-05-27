from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def create_unit(
    branch_id: int,
    unit_code: str,
    machine_name: str,
    serial_number: str,
    device_uuid: str,
    location_description: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO photobooth_units (
            branch_id,
            unit_code,
            machine_name,
            serial_number,
            device_uuid,
            location_description,
            status,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, branch_id, unit_code, machine_name, serial_number, device_uuid, location_description, status, now)

    return row_to_dict(row)


async def get_unit(unit_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        SELECT
            u.*,
            b.branch_name,
            b.branch_code
        FROM photobooth_units u
        JOIN branches b ON b.id = u.branch_id
        WHERE u.id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, unit_id)

    return row_to_dict(row) if row else None


async def get_unit_by_device_uuid(device_uuid: str) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        SELECT * FROM photobooth_units
        WHERE device_uuid = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, device_uuid)

    return row_to_dict(row) if row else None


async def list_units(branch_id: int | None = None) -> list[dict[str, Any]]:
    pool = get_pool()

    if branch_id:
        query = """
            SELECT
                u.*,
                b.branch_name,
                b.branch_code
            FROM photobooth_units u
            JOIN branches b ON b.id = u.branch_id
            WHERE u.branch_id = $1
            ORDER BY u.unit_code ASC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, branch_id)
    else:
        query = """
            SELECT
                u.*,
                b.branch_name,
                b.branch_code
            FROM photobooth_units u
            JOIN branches b ON b.id = u.branch_id
            ORDER BY b.branch_name ASC, u.unit_code ASC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

    return [row_to_dict(r) for r in rows]


async def update_unit_last_seen(unit_id: int) -> None:
    pool = get_pool()

    query = """
        UPDATE photobooth_units
        SET last_seen_at = $1
        WHERE id = $2
    """

    async with pool.acquire() as conn:
        await conn.execute(query, datetime.utcnow(), unit_id)


async def update_unit_status(unit_id: int, status: str) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        UPDATE photobooth_units
        SET status = $1, last_seen_at = $2
        WHERE id = $3
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, status, datetime.utcnow(), unit_id)

    return row_to_dict(row) if row else None