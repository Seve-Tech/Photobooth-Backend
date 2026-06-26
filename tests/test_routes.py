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


def test_admin_branches_flow(client: TestClient, valid_api_key_headers: dict):
    """Test branches list, create, update, and delete admin endpoints."""
    import datetime

    # 1. Test GET /api/v1/admin/branches
    mock_branches = [
        {
            "id": 1,
            "branch_code": "BR-01",
            "branch_name": "Manila Branch",
            "owner_name": "John Doe",
            "contact_number": "09123456789",
            "address": "Manila City",
            "created_at": datetime.datetime(2026, 6, 26, 12, 0, 0, tzinfo=datetime.timezone.utc),
        }
    ]
    with patch("app.api.routes.admin.list_branches", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_branches
        response = client.get("/api/v1/admin/branches", headers=valid_api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["branch_name"] == "Manila Branch"

    # 2. Test POST /api/v1/admin/branches
    new_branch_payload = {
        "branch_code": "BR-02",
        "branch_name": "Quezon Branch",
        "owner_name": "Jane Doe",
        "contact_number": "09876543210",
        "address": "Quezon City",
    }
    mock_created_branch = {
        "id": 2,
        "branch_code": "BR-02",
        "branch_name": "Quezon Branch",
        "owner_name": "Jane Doe",
        "contact_number": "09876543210",
        "address": "Quezon City",
        "created_at": datetime.datetime(2026, 6, 26, 12, 0, 0, tzinfo=datetime.timezone.utc),
    }
    with patch("app.api.routes.admin.get_branch_by_code", new_callable=AsyncMock) as mock_get_code, \
         patch("app.api.routes.admin.create_branch", new_callable=AsyncMock) as mock_create:
        mock_get_code.return_value = None
        mock_create.return_value = mock_created_branch

        response = client.post(
            "/api/v1/admin/branches",
            json=new_branch_payload,
            headers=valid_api_key_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 2
        assert data["branch_name"] == "Quezon Branch"

    # 3. Test PATCH /api/v1/admin/branches/{branch_id}
    update_payload = {"branch_name": "Quezon City Branch"}
    mock_updated_branch = {
        "id": 2,
        "branch_code": "BR-02",
        "branch_name": "Quezon City Branch",
        "owner_name": "Jane Doe",
        "contact_number": "09876543210",
        "address": "Quezon City",
        "created_at": datetime.datetime(2026, 6, 26, 12, 0, 0, tzinfo=datetime.timezone.utc),
    }
    with patch("app.api.routes.admin.get_branch", new_callable=AsyncMock) as mock_get, \
         patch("app.api.routes.admin.update_branch", new_callable=AsyncMock) as mock_update:
        mock_get.return_value = mock_created_branch
        mock_update.return_value = mock_updated_branch

        response = client.patch(
            "/api/v1/admin/branches/2",
            json=update_payload,
            headers=valid_api_key_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["branch_name"] == "Quezon City Branch"

    # 4. Test DELETE /api/v1/admin/branches/{branch_id}
    with patch("app.api.routes.admin.get_branch", new_callable=AsyncMock) as mock_get, \
         patch("app.api.routes.admin.delete_branch", new_callable=AsyncMock) as mock_delete:
        mock_get.return_value = mock_updated_branch
        mock_delete.return_value = True

        response = client.delete(
            "/api/v1/admin/branches/2",
            headers=valid_api_key_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Branch deleted successfully."

