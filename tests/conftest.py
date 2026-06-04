from typing import Generator
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient for testing the FastAPI app."""
    # Note: Since the app has a lifespan that tries to connect to the DB, 
    # we need to mock init_db and close_db, plus get_admin_pin_hash and upsert_admin_pin.
    with patch("app.app_factory.init_db", new_callable=AsyncMock), \
         patch("app.app_factory.close_db", new_callable=AsyncMock), \
         patch("app.app_factory.get_pool") as mock_get_pool, \
         patch("app.app_factory.get_admin_pin_hash", new_callable=AsyncMock) as mock_get_pin, \
         patch("app.app_factory.upsert_admin_pin", new_callable=AsyncMock):
        
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        
        # mock pool.acquire() context manager
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool.acquire.return_value = mock_ctx
        mock_get_pool.return_value = mock_pool
        mock_get_pin.return_value = "fake_pin_hash"
        
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def valid_api_key_headers() -> dict[str, str]:
    """Return headers with the valid API key for auth."""
    return {"X-API-Key": settings.api_key}
