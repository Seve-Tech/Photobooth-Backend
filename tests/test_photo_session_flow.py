import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.schemas import SessionResponse, SessionStatus


def test_start_photo_session_success(client: TestClient, valid_api_key_headers: dict) -> None:
    mock_session = {
        "id": "77fb7920-a68e-4e1c-8e64-c425af7f55dd",
        "status": SessionStatus.PAID,
        "total_paid": 199.0,
        "currency": "PHP",
        "customer_ref": "Test User",
        "package_id": 1,
        "created_at": "2026-05-27T12:00:00Z",
        "updated_at": "2026-05-27T12:00:00Z",
    }
    
    mock_session_active = mock_session.copy()
    mock_session_active["status"] = SessionStatus.PHOTO_ACTIVE

    with patch("app.api.routes.photo_session.get_session", new_callable=AsyncMock) as mock_get_session, \
         patch("app.api.routes.photo_session.update_session", new_callable=AsyncMock) as mock_update_session, \
         patch("app.api.routes.photo_session.dslrbooth_service.is_reachable", new_callable=AsyncMock) as mock_reachable, \
         patch("app.api.routes.photo_session.dslrbooth_service.start_session", new_callable=AsyncMock) as mock_start, \
         patch("app.api.routes.photo_session._schedule_session_timeout", new_callable=AsyncMock) as mock_timeout, \
         patch("app.api.routes.photo_session.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        
        mock_get_session.return_value = SessionResponse(**mock_session)
        mock_update_session.return_value = SessionResponse(**mock_session_active)
        mock_reachable.return_value = True
        
        from app.services.dslrbooth_service import DSLRBoothResult
        mock_start.return_value = DSLRBoothResult(Command="start", IsSuccessful=True)

        payload = {"session_id": "77fb7920-a68e-4e1c-8e64-c425af7f55dd"}
        response = client.post(
            "/api/v1/photo-session/start",
            json=payload,
            headers=valid_api_key_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "launched"
        assert data["session_id"] == "77fb7920-a68e-4e1c-8e64-c425af7f55dd"
        
        assert mock_get_session.called
        assert mock_update_session.called
        assert mock_start.called
        assert mock_broadcast.called


def test_start_photo_session_not_found(client: TestClient, valid_api_key_headers: dict) -> None:
    with patch("app.api.routes.photo_session.get_session", new_callable=AsyncMock) as mock_get_session:
        mock_get_session.return_value = None

        payload = {"session_id": "nonexistent-id"}
        response = client.post(
            "/api/v1/photo-session/start",
            json=payload,
            headers=valid_api_key_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


def test_dslrbooth_webhook_session_end(client: TestClient) -> None:
    mock_active_session = {
        "id": "77fb7920-a68e-4e1c-8e64-c425af7f55dd",
        "status": SessionStatus.PHOTO_ACTIVE,
        "total_paid": 199.0,
        "currency": "PHP",
        "customer_ref": "Test User",
        "package_id": 1,
        "created_at": "2026-05-27T12:00:00Z",
        "updated_at": "2026-05-27T12:00:00Z",
    }
    
    mock_session_complete = mock_active_session.copy()
    mock_session_complete["status"] = SessionStatus.PHOTO_COMPLETE

    with patch("app.api.routes.photo_session.get_active_photo_session", new_callable=AsyncMock) as mock_get_active, \
         patch("app.api.routes.photo_session.update_session", new_callable=AsyncMock) as mock_update, \
         patch("app.api.routes.photo_session.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        
        mock_get_active.return_value = SessionResponse(**mock_active_session)
        mock_update.return_value = SessionResponse(**mock_session_complete)

        response = client.get(
            "/api/v1/photo-session/webhook",
            params={"event_type": "session_end"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        assert mock_get_active.called
        assert mock_update.called
        # Verify it broadcast status update + session completion
        assert mock_broadcast.call_count >= 2


def test_complete_photo_session(client: TestClient, valid_api_key_headers: dict) -> None:
    mock_completed_session = {
        "id": "77fb7920-a68e-4e1c-8e64-c425af7f55dd",
        "status": SessionStatus.COMPLETED,
        "total_paid": 199.0,
        "currency": "PHP",
        "customer_ref": "Test User",
        "package_id": 1,
        "created_at": "2026-05-27T12:00:00Z",
        "updated_at": "2026-05-27T12:00:00Z",
    }

    with patch("app.api.routes.photo_session.complete_session", new_callable=AsyncMock) as mock_complete, \
         patch("app.api.routes.photo_session.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        
        mock_complete.return_value = SessionResponse(**mock_completed_session)

        response = client.post(
            "/api/v1/photo-session/complete/77fb7920-a68e-4e1c-8e64-c425af7f55dd",
            headers=valid_api_key_headers
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert mock_complete.called
        assert mock_broadcast.called
