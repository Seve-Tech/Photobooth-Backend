from datetime import datetime
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def create_branch(
    branch_code: str,
    branch_name: str,
    owner_name: str,
    contact_number: str,
    address: str,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO branches (
            branch_code,
            branch_name,
            owner_name,
            contact_number,
            address,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, branch_code, branch_name, owner_name, contact_number, address, now)

    return row_to_dict(row)


async def get_branch(branch_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        SELECT * FROM branches
        WHERE id = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, branch_id)

    return row_to_dict(row) if row else None


async def get_branch_by_code(branch_code: str) -> dict[str, Any] | None:
    pool = get_pool()

    query = """
        SELECT * FROM branches
        WHERE branch_code = $1
        LIMIT 1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, branch_code)

    return row_to_dict(row) if row else None


async def list_branches() -> list[dict[str, Any]]:
    pool = get_pool()

    query = """
        SELECT * FROM branches
        ORDER BY branch_name ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    return [row_to_dict(r) for r in rows]


async def update_branch(branch_id: int, **kwargs: Any) -> dict[str, Any] | None:
    pool = get_pool()

    allowed = {"branch_name", "owner_name", "contact_number", "address"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

    if not updates:
        return await get_branch(branch_id)

    set_clauses = [f"{col} = ${i}" for i, col in enumerate(updates.keys(), start=1)]
    values = list(updates.values())
    values.append(branch_id)

    query = f"""
        UPDATE branches
        SET {', '.join(set_clauses)}
        WHERE id = ${len(values)}
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)

    return row_to_dict(row) if row else None


async def delete_branch(branch_id: int) -> bool:
    pool = get_pool()

    query = """
        DELETE FROM branches
        WHERE id = $1
    """

    async with pool.acquire() as conn:
        result = await conn.execute(query, branch_id)

    return result == "DELETE 1"