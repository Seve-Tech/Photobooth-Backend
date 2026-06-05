"""
Mock DSLRBooth HTTP API Server.

This mimics the actual DSLRBooth API on port 1500.
When start is triggered, it runs a background task to fire the webhook events back
to our main backend at http://localhost:8000.
"""

import asyncio
import logging
import httpx
from fastapi import FastAPI, Query, BackgroundTasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | mock_dslrbooth | %(message)s",
)
logger = logging.getLogger("mock_dslrbooth")

app = FastAPI(title="Mock DSLRBooth API", version="1.0.0")

# Local backend webhook URL
WEBHOOK_URL = "http://localhost:8000/api/v1/photo-session/webhook"
# Delay between mock events (in seconds)
EVENT_DELAY = 1.0


async def fire_webhook_event(event_type: str, params: dict) -> None:
    query_params = {"event_type": event_type, **params}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            logger.info("Firing trigger webhook: %s with params %s", event_type, params)
            resp = await client.get(WEBHOOK_URL, params=query_params)
            logger.info("Webhook response: %d", resp.status_code)
    except Exception as exc:
        logger.error("Failed to fire webhook event %s: %s", event_type, exc)


async def simulate_dslrbooth_session(mode: str) -> None:
    """Simulates the lifecycle of a DSLRBooth session over webhooks."""
    # Wait for the start API response to complete
    await asyncio.sleep(1.0)

    events = [
        ("session_start", {"param1": mode}),
        ("countdown_start", {"param1": "5"}),
        ("countdown", {"param1": "50"}),
        ("capture_start", {}),
        ("file_download", {"param1": "mock_captured_photo.jpg"}),
        ("processing_start", {}),
        ("sharing_screen", {}),
        ("printing", {"param1": "mock_captured_photo.jpg", "param2": "1", "param3": "MockPrinter"}),
        ("file_upload", {"param1": "mock_captured_photo.jpg", "param2": "http://mock-dslrbooth.cloud/upload/123"}),
        ("session_end", {}),
    ]

    for event_type, params in events:
        await fire_webhook_event(event_type, params)
        await asyncio.sleep(EVENT_DELAY)

    logger.info("Session simulation complete.")


@app.get("/")
async def root() -> dict:
    logger.info("Received health check reachability request at /")
    return {"status": "alive", "message": "Mock DSLRBooth API Server is running"}



@app.get("/api/start")
async def start_session(
    background_tasks: BackgroundTasks,
    mode: str = Query("print"),
    password: str | None = Query(None),
) -> dict:
    logger.info("Received start command (mode: %s, password: %s)", mode, password)
    
    # In real DSLRBooth, if the password doesn't match, it returns IsSuccessful=False
    # For local testing, we print a warning but allow it
    if password is None or password == "":
        logger.warning("No password provided in start command!")

    # Start trigger lifecycle in background
    background_tasks.add_task(simulate_dslrbooth_session, mode)

    return {
        "ApiVersion": 1,
        "Command": f"start?mode={mode}",
        "IsSuccessful": True,
        "ErrorMessage": "",
    }


@app.get("/api/print")
async def print_copies(
    count: int = Query(1),
    password: str | None = Query(None),
) -> dict:
    logger.info("Received print command (count: %d, password: %s)", count, password)
    return {
        "ApiVersion": 1,
        "Command": f"print?count={count}",
        "IsSuccessful": True,
        "ErrorMessage": "",
    }


@app.get("/api/share/email")
async def share_email(
    email: str = Query(...),
    password: str | None = Query(None),
) -> dict:
    logger.info("Received share/email command (email: %s, password: %s)", email, password)
    return {
        "ApiVersion": 1,
        "Command": f"share/email?email={email}",
        "IsSuccessful": True,
        "ErrorMessage": "",
    }


@app.get("/api/share/sms")
async def share_sms(
    phone: str = Query(...),
    password: str | None = Query(None),
) -> dict:
    logger.info("Received share/sms command (phone: %s, password: %s)", phone, password)
    return {
        "ApiVersion": 1,
        "Command": f"share/sms?phone={phone}",
        "IsSuccessful": True,
        "ErrorMessage": "",
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Mock DSLRBooth Server on port 1500...")
    uvicorn.run(app, host="0.0.0.0", port=1500)
