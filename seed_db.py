"""
One-time seed script — inserts the minimum required rows so the app can
create sessions without hitting foreign key violations.

Tables seeded (in dependency order):
    1. branches          → required by sessions (branch_id)
    2. photobooth_units  → required by sessions (unit_id), depends on branches
    3. packages          → required by sessions (package_id)

Run with:
    python seed_db.py

Safe to re-run — each section checks before inserting.
"""

import asyncio
from decimal import Decimal

import asyncpg
from app.core.config import settings


async def seed() -> None:
    conn = await asyncpg.connect(settings.DATABASE_URL)
    print(f"Connected to: {settings.DATABASE_URL}\n")

    # ── 1. Branch ─────────────────────────────────────────────────────────────
    existing = await conn.fetchrow("SELECT id FROM branches WHERE id = 1")
    if existing:
        print("[OK] Branch id=1 already exists — skipping.")
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO branches (branch_code, branch_name, owner_name, contact_number, address, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id, branch_name
            """,
            "BR001", "Main Branch", "Owner", "09000000000", "Main Location",
        )
        print(f"[OK] Created branch: id={row['id']}, name={row['branch_name']}")

    # ── 2. Photobooth unit ────────────────────────────────────────────────────
    existing = await conn.fetchrow("SELECT id FROM photobooth_units WHERE id = 1")
    if existing:
        print("[OK] Unit id=1 already exists — skipping.")
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO photobooth_units
                (branch_id, unit_code, machine_name, serial_number, device_uuid,
                 location_description, status, created_at)
            VALUES ($1, $2, $3, $4, gen_random_uuid(), $5, $6, NOW())
            RETURNING id, machine_name
            """,
            1, "PB001", "Photobooth Unit 1", "SN-001", "Main Floor", "active",
        )
        print(f"[OK] Created unit: id={row['id']}, name={row['machine_name']}")

    # ── 3. Package ────────────────────────────────────────────────────────────
    existing = await conn.fetchrow("SELECT id FROM packages WHERE id = 1")
    if existing:
        print("[OK] Package id=1 already exists — skipping.")
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO packages
                (package_code, package_name, description, price,
                 number_of_shots, print_count, duration_seconds, is_active, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING id, package_name, price
            """,
            "PKG-STANDARD",
            "Standard Package",
            "4 shots, 1 print strip",
            Decimal("150.00"),
            4,    # number_of_shots
            1,    # print_count
            120,  # duration_seconds (2 minutes)
            1,    # is_active
        )
        print(f"[OK] Created package: id={row['id']}, name={row['package_name']}, price=PHP {row['price']}")

    await conn.close()
    print("\nSeeding complete. You can now create sessions.")


if __name__ == "__main__":
    asyncio.run(seed())
