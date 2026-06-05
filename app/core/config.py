from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # App
    app_name: str = "Photobooth Backend"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, alias="DEBUG")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Security
    # api_key MUST be set in .env — no default so the app fails fast if omitted.
    api_key: str = Field(alias="API_KEY")
    # The front-end origin allowed by CORS. Update to your production URL.
    frontend_origin: str = Field(
        default="http://localhost:3000", alias="FRONTEND_ORIGIN"
    )
    # Max WebSocket messages per client per 60-second window.
    ws_rate_limit: int = Field(default=40, alias="WS_RATE_LIMIT")

    # Database
    # Each photobooth unit sets DATABASE_URL, BRANCH_ID, and UNIT_ID in its own .env.
    # DATABASE_URL must be a raw asyncpg DSN — no driver prefix:
    #   postgresql://user:password@host:5432/dbname
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/photobooth_db",
        alias="DATABASE_URL",
    )

    # Machine identity — set once per physical deployment.
    # These are auto-injected into every session so callers never need to pass them.
    branch_id: int = Field(default=1, alias="BRANCH_ID")
    unit_id: int = Field(default=1, alias="UNIT_ID")

    # Bill acceptor pulse config
    # AGmarketing TB74 sends N pulses per denomination.
    # Map: pulse_count -> amount in PHP (update as needed)
    bill_pulse_map: dict[int, float] = Field(
        default={
            1: 10.0,
            2: 20.0,
            5: 50.0,
            10: 100.0,
            20: 200.0,
        }
    )

    # DSLRBooth Integration
    dslrbooth_host: str = Field(default="http://localhost:1500", alias="DSLRBOOTH_HOST")
    dslrbooth_password: str = Field(default="", alias="DSLRBOOTH_PASSWORD")
    dslrbooth_mock: bool = Field(default=True, alias="DSLRBOOTH_MOCK")
    dslrbooth_session_timeout_s: int = Field(default=300, alias="DSLRBOOTH_SESSION_TIMEOUT_S")
    dslrbooth_booth_mode: str = Field(default="print", alias="DSLRBOOTH_BOOTH_MODE")
    dslrbooth_mock_session_duration_s: int = Field(default=10, alias="DSLRBOOTH_MOCK_SESSION_DURATION_S")

    model_config = {"env_file": ".env", "populate_by_name": True}


# Singleton — import this everywhere you need settings
settings = Settings()
