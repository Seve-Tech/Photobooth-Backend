from datetime import datetime
from decimal import Decimal
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def create_package(
    package_code: str,
    package_name: str,
    price: Decimal,
    number_of_shots: int,
    print_count: int,
    duration_seconds: int,
    description: str | None = None,
    is_active: int = 1,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO packages (
            package_code,
            package_name,
            description,
            price,
            number_of_shots,
            print_count,
            duration_seconds,
            is_active,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, package_code, package_name, description, price, number_of_shots, print_count, duration_seconds, is_active, now)

    return row_to_dict(row)


async def get_package(package_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        SELECT * FROM packages
        WHERE id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, package_id)

    return row_to_dict(row) if row else None


async def list_packages(active_only: bool = True) -> list[dict[str, Any]]:
    pool = get_pool()

    if active_only:
        query = """
            SELECT * FROM packages
            WHERE is_active = 1
            ORDER BY price ASC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
    else:
        query = """
            SELECT * FROM packages
            ORDER BY is_active DESC, price ASC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)

    return [row_to_dict(r) for r in rows]


async def deactivate_package(package_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        UPDATE packages
        SET is_active = 0
        WHERE id = $1
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, package_id)

    return row_to_dict(row) if row else None