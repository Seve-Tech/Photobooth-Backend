from datetime import datetime, date
from decimal import Decimal
from typing import Any

from app.db.connection import get_pool, row_to_dict


async def create_expense(
    branch_id: int,
    expense_type: str,
    amount: Decimal,
    expense_date: date,
    description: str | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    now = datetime.utcnow()

    query = """
        INSERT INTO expenses (
            branch_id,
            expense_type,
            description,
            amount,
            expense_date,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, branch_id, expense_type, description, amount, expense_date, now)

    return row_to_dict(row)


async def list_expenses(
    branch_id: int | None = None,
    expense_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict[str, Any]]:
    pool = get_pool()

    conditions: list[str] = []
    values: list[Any] = []

    if branch_id is not None:
        values.append(branch_id)
        conditions.append(f"branch_id = ${len(values)}")

    if expense_type is not None:
        values.append(expense_type)
        conditions.append(f"expense_type = ${len(values)}")

    if from_date is not None:
        values.append(from_date)
        conditions.append(f"expense_date >= ${len(values)}")

    if to_date is not None:
        values.append(to_date)
        conditions.append(f"expense_date <= ${len(values)}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT * FROM expenses
        {where}
        ORDER BY expense_date DESC, created_at DESC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *values)

    return [row_to_dict(r) for r in rows]


async def get_branch_expense_summary(
    branch_id: int,
    from_date: date,
    to_date: date,
) -> dict[str, Any]:
    pool = get_pool()

    query = """
        SELECT
            expense_type,
            COUNT(*)    AS entry_count,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE
            branch_id        = $1
            AND expense_date >= $2
            AND expense_date <= $3
        GROUP BY expense_type
        ORDER BY total_amount DESC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, branch_id, from_date, to_date)

    return {
        "branch_id": branch_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "breakdown": [row_to_dict(r) for r in rows],
        "grand_total": sum(Decimal(str(r["total_amount"])) for r in rows),
    }