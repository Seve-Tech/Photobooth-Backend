import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.dslrbooth_service import DSLRBoothService, DSLRBoothResult
from app.core.config import settings

@pytest.mark.asyncio
async def test_dslrbooth_service_mock_mode() -> None:
    service = DSLRBoothService()
    service.mock = True

    # start session in mock
    res = await service.start_session(mode="print")
    assert res.IsSuccessful is True
    assert res.Command == "start?mode=print"

    # print copies in mock
    res = await service.print_copies(count=2)
    assert res.IsSuccessful is True
    assert res.Command == "print?count=2"

    # share email in mock
    res = await service.share_email("test@example.com")
    assert res.IsSuccessful is True
    assert res.Command == "share/email?email=test@example.com"

    # share sms in mock
    res = await service.share_sms("12345678")
    assert res.IsSuccessful is True
    assert res.Command == "share/sms?phone=12345678"


@pytest.mark.asyncio
async def test_dslrbooth_service_real_mode_success() -> None:
    service = DSLRBoothService()
    service.mock = False
    service.host = "http://localhost:1500"
    service.password = "secret"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ApiVersion": 1,
        "Command": "start?mode=print",
        "IsSuccessful": True,
        "ErrorMessage": ""
    }

    # Use patch context manager to mock HTTP client
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        res = await service.start_session(mode="print")
        assert res.IsSuccessful is True
        assert res.Command == "start?mode=print"
        mock_get.assert_called_once_with(
            "http://localhost:1500/api/start",
            params={"mode": "print", "password": "secret"}
        )


@pytest.mark.asyncio
async def test_dslrbooth_service_real_mode_failure() -> None:
    service = DSLRBoothService()
    service.mock = False
    service.host = "http://localhost:1500"
    service.password = "secret"

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        res = await service.start_session(mode="print")
        assert res.IsSuccessful is False
        assert "HTTP status code 400" in res.ErrorMessage
