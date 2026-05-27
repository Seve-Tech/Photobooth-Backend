from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.models.schemas import SessionStatus


def test_health_endpoint(client: TestClient):
    """Test the /health endpoint without needing a real DB."""
    # We mock ping_db so it doesn't try to query the database
    with patch("app.api.routes.health.ping_db", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = True
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db_connected"] is True


def test_create_session(client: TestClient, valid_api_key_headers: dict):
    """Test creating a new session via the REST API."""
    mock_session_response = {
        "id": "1",
        "status": SessionStatus.PENDING,
        "total_paid": 0.0,
        "currency": "PHP",
        "customer_ref": "Test User",
        "package_id": 1,
        "created_at": "2026-05-27T12:00:00Z",
        "updated_at": "2026-05-27T12:00:00Z",
    }
    
    # Mock create_session and manager.broadcast
    with patch("app.api.routes.sessions.create_session", new_callable=AsyncMock) as mock_create, \
         patch("app.api.routes.sessions.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        
        # We need to return a SessionResponse object, but since the endpoint returns
        # the model directly, we can just let it return the dict if we mock it carefully,
        # or better yet, return the actual Pydantic model.
        from app.models.schemas import SessionResponse
        mock_create.return_value = SessionResponse(**mock_session_response)
        
        payload = {
            "customer_ref": "Test User",
            "package_id": 1
        }
        
        response = client.post(
            "/api/v1/sessions", 
            json=payload, 
            headers=valid_api_key_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["customer_ref"] == "Test User"
        assert data["status"] == "pending"
        
        # Verify broadcast was called
        assert mock_broadcast.called
