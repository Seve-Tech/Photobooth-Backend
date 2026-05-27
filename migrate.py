import asyncio
import asyncpg
from app.core.config import settings


async def create_database() -> None:
    db_url = settings.DATABASE_URL
    db_name = db_url.rsplit("/", 1)[-1]
    root_url = db_url.rsplit("/", 1)[0] + "/postgres"

    conn = await asyncpg.connect(root_url)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"[+] Database '{db_name}' created.")
        else:
            print(f"[~] Database '{db_name}' already exists, skipping.")
    finally:
        await conn.close()


async def create_tables() -> None:
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id              SERIAL PRIMARY KEY,
                branch_code     VARCHAR(50)  NOT NULL UNIQUE,
                branch_name     VARCHAR(255) NOT NULL,
                owner_name      VARCHAR(255) NOT NULL,
                contact_number  VARCHAR(50)  NOT NULL,
                address         TEXT         NOT NULL,
                created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'branches' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS photobooth_units (
                id                   SERIAL PRIMARY KEY,
                branch_id            INT          NOT NULL REFERENCES branches(id),
                unit_code            VARCHAR(50)  NOT NULL UNIQUE,
                machine_name         VARCHAR(255) NOT NULL,
                serial_number        VARCHAR(255) NOT NULL,
                device_uuid          VARCHAR(255) NOT NULL UNIQUE,
                location_description TEXT,
                status               VARCHAR(50)  NOT NULL DEFAULT 'active',
                last_seen_at         TIMESTAMP,
                created_at           TIMESTAMP    NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'photobooth_units' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS packages (
                id               SERIAL PRIMARY KEY,
                package_code     VARCHAR(50)    NOT NULL UNIQUE,
                package_name     VARCHAR(255)   NOT NULL,
                description      TEXT,
                price            DECIMAL(10, 2) NOT NULL,
                number_of_shots  INT            NOT NULL,
                print_count      INT            NOT NULL,
                duration_seconds INT            NOT NULL,
                is_active        INT            NOT NULL DEFAULT 1,
                created_at       TIMESTAMP      NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'packages' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id                 SERIAL PRIMARY KEY,
                session_uuid       UUID           NOT NULL UNIQUE,
                branch_id          INT            NOT NULL REFERENCES branches(id),
                unit_id            INT            NOT NULL REFERENCES photobooth_units(id),
                package_id         INT            NOT NULL REFERENCES packages(id),
                customer_ref       VARCHAR(255),
                session_status     VARCHAR(50)    NOT NULL DEFAULT 'pending',
                started_at         TIMESTAMP      NOT NULL DEFAULT NOW(),
                completed_at       TIMESTAMP,
                expected_amount    DECIMAL(10, 2),
                paid_amount        DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                payment_status     VARCHAR(50)    NOT NULL DEFAULT 'unpaid',
                total_photos_taken INT            NOT NULL DEFAULT 0,
                total_prints       INT            NOT NULL DEFAULT 0,
                sync_status        VARCHAR(50)    NOT NULL DEFAULT 'pending',
                created_at         TIMESTAMP      NOT NULL DEFAULT NOW(),
                updated_at         TIMESTAMP      NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'sessions' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id               SERIAL PRIMARY KEY,
                payment_uuid     UUID           NOT NULL UNIQUE,
                session_id       INT            NOT NULL REFERENCES sessions(id),
                payment_method   VARCHAR(100)   NOT NULL,
                payment_status   VARCHAR(50)    NOT NULL,
                amount           DECIMAL(10, 2) NOT NULL,
                reference_number VARCHAR(255),
                received_at      TIMESTAMP      NOT NULL DEFAULT NOW(),
                sync_status      VARCHAR(50)    NOT NULL DEFAULT 'pending',
                created_at       TIMESTAMP      NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'payments' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bill_acceptor_logs (
                id              SERIAL PRIMARY KEY,
                session_id      INT            NOT NULL REFERENCES sessions(id),
                denomination    DECIMAL(10, 2) NOT NULL,
                bill_count      INT            NOT NULL DEFAULT 1,
                raw_signal      TEXT,
                hardware_status VARCHAR(100),
                inserted_at     TIMESTAMP      NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'bill_acceptor_logs' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id                  SERIAL PRIMARY KEY,
                session_id          INT       NOT NULL REFERENCES sessions(id),
                shot_number         INT       NOT NULL,
                original_file_path  TEXT      NOT NULL,
                processed_file_path TEXT,
                thumbnail_path      TEXT,
                captured_at         TIMESTAMP NOT NULL DEFAULT NOW(),
                is_printed          INT       NOT NULL DEFAULT 0,
                created_at          TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'photos' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS print_jobs (
                id            SERIAL PRIMARY KEY,
                session_id    INT          NOT NULL REFERENCES sessions(id),
                printer_name  VARCHAR(255) NOT NULL,
                copies        INT          NOT NULL DEFAULT 1,
                print_status  VARCHAR(50)  NOT NULL DEFAULT 'queued',
                printed_at    TIMESTAMP,
                error_message TEXT,
                created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'print_jobs' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS device_events (
                id         SERIAL PRIMARY KEY,
                unit_id    INT          NOT NULL REFERENCES photobooth_units(id),
                event_type VARCHAR(100) NOT NULL,
                severity   VARCHAR(50)  NOT NULL DEFAULT 'info',
                message    TEXT         NOT NULL,
                created_at TIMESTAMP    NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'device_events' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id           SERIAL PRIMARY KEY,
                branch_id    INT            NOT NULL REFERENCES branches(id),
                expense_type VARCHAR(100)   NOT NULL,
                description  TEXT,
                amount       DECIMAL(10, 2) NOT NULL,
                expense_date DATE           NOT NULL,
                created_at   TIMESTAMP      NOT NULL DEFAULT NOW()
            );
        """)
        print("[+] Table 'expenses' ready.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id             SERIAL PRIMARY KEY,
                table_name     VARCHAR(100) NOT NULL,
                record_id      INT          NOT NULL,
                operation_type VARCHAR(20)  NOT NULL,
                sync_status    VARCHAR(50)  NOT NULL DEFAULT 'pending',
                retry_count    INT          NOT NULL DEFAULT 0,
                created_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
                synced_at      TIMESTAMP
            );
        """)
        print("[+] Table 'sync_queue' ready.")

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_session_uuid
                ON sessions (session_uuid);

            CREATE INDEX IF NOT EXISTS idx_sessions_branch_id
                ON sessions (branch_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_unit_id
                ON sessions (unit_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_created_at
                ON sessions (created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_payments_session_id
                ON payments (session_id);

            CREATE INDEX IF NOT EXISTS idx_photos_session_id
                ON photos (session_id);

            CREATE INDEX IF NOT EXISTS idx_bill_acceptor_logs_session_id
                ON bill_acceptor_logs (session_id);

            CREATE INDEX IF NOT EXISTS idx_device_events_unit_id_created_at
                ON device_events (unit_id, created_at DESC);
        """)
        print("[+] Indexes ready.")

    finally:
        await conn.close()


async def main() -> None:
    print("Starting migration...")
    await create_database()
    await create_tables()
    print("\nMigration complete. All tables and indexes are ready.")


if __name__ == "__main__":
    asyncio.run(main())