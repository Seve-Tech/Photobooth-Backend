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

    # Database — fill these in once the DB is ready
    # The db_url is set to a placeholder so the app boots without a real DB.
    # When the DB is ready, just set DATABASE_URL in your .env file.
    db_url: str = Field(
        default="sqlite:///./photobooth_dev.db",
        alias="DATABASE_URL",
    )

    # Bill acceptor pulse config
    # AGmarketing TB74 sends N pulses per denomination.
    # Map: pulse_count -> amount in PHP (update as needed)
    bill_pulse_map: dict[int, float] = Field(
        default={
            1: 20.0,
            2: 50.0,
            3: 100.0,
            4: 200.0,
            5: 500.0,
        }
    )

    model_config = {"env_file": ".env", "populate_by_name": True}


# Singleton — import this everywhere you need settings
settings = Settings()
