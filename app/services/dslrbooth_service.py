"""
DSLRBooth service.

Responsible for communicating with the local DSLRBooth HTTP API on port 1500
and simulating it in mock mode.
"""

import asyncio
import logging
import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class DSLRBoothResult(BaseModel):
    ApiVersion: int = 1
    Command: str
    IsSuccessful: bool
    ErrorMessage: str = ""


class DSLRBoothService:
    def __init__(self) -> None:
        self.host = settings.dslrbooth_host.rstrip("/")
        self.password = settings.dslrbooth_password
        self.mock = settings.dslrbooth_mock
        self.timeout = 5.0  # seconds

    async def start_session(self, mode: str = "print") -> DSLRBoothResult:
        if self.mock:
            logger.info("[Mock DSLRBooth] Starting session mock (mode: %s)...", mode)
            # Spawn background task to simulate the webhook trigger sequence
            asyncio.create_task(self._simulate_webhook_lifecycle(mode))
            return DSLRBoothResult(Command=f"start?mode={mode}", IsSuccessful=True)

        url = f"{self.host}/api/start"
        params = {"mode": mode, "password": self.password}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    return DSLRBoothResult(
                        Command=f"start?mode={mode}",
                        IsSuccessful=False,
                        ErrorMessage=f"HTTP status code {response.status_code}",
                    )
                data = response.json()
                return DSLRBoothResult(**data)
        except Exception as exc:
            logger.exception("Error starting DSLRBooth session: %s", exc)
            return DSLRBoothResult(
                Command=f"start?mode={mode}",
                IsSuccessful=False,
                ErrorMessage=str(exc),
            )

    async def print_copies(self, count: int = 1) -> DSLRBoothResult:
        if self.mock:
            logger.info("[Mock DSLRBooth] Printing %d copies...", count)
            return DSLRBoothResult(Command=f"print?count={count}", IsSuccessful=True)

        url = f"{self.host}/api/print"
        params = {"count": count, "password": self.password}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    return DSLRBoothResult(
                        Command=f"print?count={count}",
                        IsSuccessful=False,
                        ErrorMessage=f"HTTP status code {response.status_code}",
                    )
                data = response.json()
                return DSLRBoothResult(**data)
        except Exception as exc:
            logger.exception("Error triggering DSLRBooth print: %s", exc)
            return DSLRBoothResult(
                Command=f"print?count={count}",
                IsSuccessful=False,
                ErrorMessage=str(exc),
            )

    async def share_email(self, email: str) -> DSLRBoothResult:
        if self.mock:
            logger.info("[Mock DSLRBooth] Sharing via email to %s...", email)
            return DSLRBoothResult(Command=f"share/email?email={email}", IsSuccessful=True)

        url = f"{self.host}/api/share/email"
        params = {"email": email, "password": self.password}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    return DSLRBoothResult(
                        Command=f"share/email?email={email}",
                        IsSuccessful=False,
                        ErrorMessage=f"HTTP status code {response.status_code}",
                    )
                data = response.json()
                return DSLRBoothResult(**data)
        except Exception as exc:
            logger.exception("Error sharing DSLRBooth via email: %s", exc)
            return DSLRBoothResult(
                Command=f"share/email?email={email}",
                IsSuccessful=False,
                ErrorMessage=str(exc),
            )

    async def share_sms(self, phone: str) -> DSLRBoothResult:
        if self.mock:
            logger.info("[Mock DSLRBooth] Sharing via SMS to %s...", phone)
            return DSLRBoothResult(Command=f"share/sms?phone={phone}", IsSuccessful=True)

        url = f"{self.host}/api/share/sms"
        params = {"phone": phone, "password": self.password}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    return DSLRBoothResult(
                        Command=f"share/sms?phone={phone}",
                        IsSuccessful=False,
                        ErrorMessage=f"HTTP status code {response.status_code}",
                    )
                data = response.json()
                return DSLRBoothResult(**data)
        except Exception as exc:
            logger.exception("Error sharing DSLRBooth via SMS: %s", exc)
            return DSLRBoothResult(
                Command=f"share/sms?phone={phone}",
                IsSuccessful=False,
                ErrorMessage=str(exc),
            )

    async def is_reachable(self) -> bool:
        if self.mock:
            return True
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.get(self.host)
                return True
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return False
        except Exception:
            return True

    async def _simulate_webhook_lifecycle(self, mode: str) -> None:
        """
        Spawns background calls to our local webhook to simulate DSLRBooth triggers.
        """
        total_duration = settings.dslrbooth_mock_session_duration_s
        step_delay = max(0.5, total_duration / 10.0)

        events = [
            ("session_start", {"param1": mode}),
            ("countdown_start", {"param1": "5"}),
            ("countdown", {"param1": "50"}),
            ("capture_start", {}),
            ("file_download", {"param1": "mock_photo_1.jpg"}),
            ("processing_start", {}),
            ("sharing_screen", {}),
            ("printing", {"param1": "mock_photo_1.jpg", "param2": "1", "param3": "MockPrinter"}),
            ("file_upload", {"param1": "mock_photo_1.jpg", "param2": "http://mock-upload-url"}),
            ("session_end", {}),
        ]

        logger.info("[Mock DSLRBooth] Starting trigger simulation...")
        local_webhook_url = f"http://localhost:{settings.port}/api/v1/photo-session/webhook"

        # Give the start response a tiny moment to send back to the frontend first
        await asyncio.sleep(0.5)

        for event_type, params in events:
            query_params = {"event_type": event_type, **params}
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    logger.debug("[Mock DSLRBooth] Simulating webhook trigger: %s %s", event_type, params)
                    await client.get(local_webhook_url, params=query_params)
            except Exception as exc:
                logger.error("[Mock DSLRBooth] Webhook simulation failed for event %s: %s", event_type, exc)

            await asyncio.sleep(step_delay)

        logger.info("[Mock DSLRBooth] Webhook simulation complete.")


dslrbooth_service = DSLRBoothService()
