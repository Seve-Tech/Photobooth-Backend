"""
Arduino Serial Bridge.

Reads pulse counts from the Arduino over USB serial, then forwards
them to the FastAPI backend as WebSocket messages.

How it works:
  1. Arduino counts pulses from the TB74 bill acceptor
  2. Arduino sends the count as plain text over USB: "3\n"
  3. This script reads that number from the USB port
  4. Converts it to a WebSocket message and sends to the backend

Usage:
    python arduino_bridge.py                        # auto-detect serial port
    python arduino_bridge.py --port COM3            # Windows
    python arduino_bridge.py --port /dev/ttyUSB0   # Linux/Mac

To find your Arduino's port:
    Windows:  Device Manager → Ports (COM & LPT)
    Linux:    ls /dev/ttyUSB* or ls /dev/ttyACM*
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

import serial
import serial.tools.list_ports
import websockets

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

WS_URL = f"ws://localhost:{settings.port}/ws?api_key={settings.api_key}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_arduino_port() -> str | None:
    """
    Auto-detect the Arduino's serial port.
    Looks for common Arduino USB descriptors.
    """
    for port in serial.tools.list_ports.comports():
        desc = (port.description or "").lower()
        if any(kw in desc for kw in ("arduino", "ch340", "cp210", "ftdi", "usb serial")):
            return port.device
    return None


def build_pulse_message(pulse_count: int, session_id: str | None = None) -> str:
    """Build the WebSocket JSON message the backend expects."""
    payload: dict = {
        "pulse_count": pulse_count,
        "received_at": datetime.utcnow().isoformat(),
        "source": "arduino",
    }
    if session_id:
        payload["session_id"] = session_id

    return json.dumps({
        "type": "pulse_received",
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── Main bridge loop ──────────────────────────────────────────────────────────

async def run_bridge(port: str, baud: int) -> None:
    """
    Open the serial port and WebSocket connection, then relay messages forever.
    Reconnects automatically if either connection drops.
    """
    logger.info("Opening serial port %s at %d baud...", port, baud)

    try:
        ser = serial.Serial(port, baud, timeout=1)
    except serial.SerialException as exc:
        logger.error("Could not open serial port %s: %s", port, exc)
        sys.exit(1)

    logger.info("Serial port open. Connecting to backend at %s ...", WS_URL)

    # Track the current session ID (updated when the front-end tells us)
    current_session_id: str | None = None

    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                logger.info("Connected to backend. Waiting for Arduino pulses...")

                # Background task: listen for session_updated events from the backend
                # so we always know the active session ID
                async def listen_for_session():
                    nonlocal current_session_id
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            if msg.get("type") == "session_updated":
                                sid = msg.get("payload", {}).get("id")
                                if sid:
                                    current_session_id = sid
                                    logger.info("Active session updated: %s", sid)
                        except Exception:
                            pass

                asyncio.create_task(listen_for_session())

                # Main loop: read from serial, send to backend
                while True:
                    # readline() blocks up to timeout=1s, returns b"" if nothing arrives
                    raw_line = await asyncio.get_event_loop().run_in_executor(
                        None, ser.readline
                    )

                    if not raw_line:
                        continue  # timeout — nothing received, try again

                    line = raw_line.decode("utf-8", errors="ignore").strip()

                    if not line:
                        continue

                    logger.debug("Arduino raw: %r", line)

                    if not line.isdigit():
                        logger.warning("Ignoring non-numeric data from Arduino: %r", line)
                        continue

                    pulse_count = int(line)
                    logger.info(
                        "Pulse received: %d pulse(s) — forwarding to backend (session: %s)",
                        pulse_count,
                        current_session_id or "none",
                    )

                    msg = build_pulse_message(pulse_count, current_session_id)
                    await ws.send(msg)

        except (websockets.ConnectionClosed, OSError) as exc:
            logger.warning("WebSocket disconnected: %s — retrying in 3s...", exc)
            await asyncio.sleep(3)
        except Exception as exc:
            logger.exception("Unexpected error: %s — retrying in 3s...", exc)
            await asyncio.sleep(3)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Arduino → Backend WebSocket bridge")
    parser.add_argument(
        "--port", type=str, default=None,
        help="Serial port (e.g. COM3 or /dev/ttyUSB0). Auto-detected if not specified.",
    )
    parser.add_argument(
        "--baud", type=int, default=9600,
        help="Baud rate (default: 9600 — must match your Arduino sketch).",
    )
    args = parser.parse_args()

    port = args.port
    if port is None:
        port = find_arduino_port()
        if port is None:
            logger.error(
                "Could not auto-detect Arduino port. "
                "Plug in the Arduino and try again, or specify --port manually."
            )
            sys.exit(1)
        logger.info("Auto-detected Arduino on port: %s", port)

    try:
        asyncio.run(run_bridge(port, args.baud))
    except KeyboardInterrupt:
        logger.info("Bridge stopped.")


if __name__ == "__main__":
    main()
