from typing import Generator
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient for testing the FastAPI app."""
    # We use TestClient which synchronously runs the ASGI app for HTTP routes.
    # Note: Since the app has a lifespan that tries to connect to the DB, 
    # we need to mock init_db and close_db before creating the client.
    with patch("app.app_factory.init_db", new_callable=AsyncMock), \
         patch("app.app_factory.close_db", new_callable=AsyncMock):
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def valid_api_key_headers() -> dict[str, str]:
    """Return headers with the valid API key for auth."""
    return {"X-API-Key": settings.api_key}
