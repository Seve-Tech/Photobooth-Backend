"""
Arduino Serial Bridge.

Reads pulse counts from the Arduino over USB serial, then forwards
them to the FastAPI backend as WebSocket messages.

How it works:
  1. Arduino counts pulses from the TB74 bill acceptor
  2. Arduino sends incremental amounts over USB (e.g. "10\n" per pulse)
  3. This script ACCUMULATES those amounts into a running total
  4. After a short idle window (PULSE_DEBOUNCE_S) with no new pulses,
     the total is sent as a single consolidated WebSocket message.
     This prevents the frontend from seeing partial/incremental updates
     mid-insertion and ensures one clean broadcast per bill.

Usage:
    python arduino_bridge.py                        # auto-detect serial port
    python arduino_bridge.py --port COM3            # Windows
    python arduino_bridge.py --port /dev/ttyUSB0   # Linux/Mac

To find your Arduino's port:
    Windows:  Device Manager → Ports (COM & LPT)
    Linux:    ls /dev/ttyUSB* or ls /dev/ttyACM*
"""

import sys
from pathlib import Path

# Add project root to sys.path to allow running from subdirectories
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import argparse
import asyncio
import json
import logging
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

# ── Pulse accumulator config ──────────────────────────────────────────────────
# How long (seconds) to wait after the last pulse before flushing the
# accumulated total to the backend.  400 ms works well for most bill
# acceptors; raise it if you still see split broadcasts.
PULSE_DEBOUNCE_S: float = 0.4


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


def build_amount_message(amount: float) -> str:
    """Build the WebSocket JSON message the backend expects."""
    payload: dict = {
        "amount": amount,
    }

    return json.dumps({
        "type": "amount_received",
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── Main bridge loop ──────────────────────────────────────────────────────────

async def run_bridge(port: str, baud: int) -> None:
    """
    Open the serial port and WebSocket connection, then relay messages forever.
    Reconnects automatically if either connection drops.

    Pulse accumulation strategy
    ---------------------------
    The Arduino may send multiple incremental amounts for a single bill
    (e.g. five "10" lines for a ₱50 note).  Rather than forwarding each
    pulse immediately — which would cause the frontend to display partial
    amounts — we accumulate all pulses into a running total and only
    broadcast once the serial line has been idle for PULSE_DEBOUNCE_S seconds.
    """
    logger.info("Opening serial port %s at %d baud...", port, baud)

    try:
        ser = serial.Serial(port, baud, timeout=1)
    except serial.SerialException as exc:
        logger.error("Could not open serial port %s: %s", port, exc)
        sys.exit(1)

    logger.info("Serial port open. Connecting to backend at %s ...", WS_URL)

    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                logger.info("Connected to backend. Waiting for Arduino messages...")

                # Accumulator state
                accumulated: float = 0.0      # running total for current bill
                flush_task: asyncio.Task | None = None  # debounce timer task

                async def flush_accumulated() -> None:
                    """Wait for the debounce window, then send the accumulated total."""
                    nonlocal accumulated
                    await asyncio.sleep(PULSE_DEBOUNCE_S)
                    total = accumulated
                    accumulated = 0.0
                    logger.info(
                        "Pulse window closed — flushing accumulated total: PHP %.2f",
                        total,
                    )
                    msg = build_amount_message(total)
                    await ws.send(msg)

                # Main loop: read from serial, accumulate, debounce-flush
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

                    amount = None
                    # Try parsing as JSON first
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            data = json.loads(line)
                            amount = float(data.get("amount"))
                        except (ValueError, KeyError, TypeError) as exc:
                            logger.warning("Failed to parse JSON from Arduino: %r — %s", line, exc)
                            continue
                    else:
                        # Otherwise, try parsing as float
                        try:
                            amount = float(line)
                        except ValueError:
                            logger.warning("Ignoring non-numeric/invalid data from Arduino: %r", line)
                            continue

                    # ── Accumulate and (re)start the debounce timer ──────────
                    accumulated += amount
                    logger.info(
                        "Pulse received: +PHP %.2f | Running total: PHP %.2f (debouncing %.0fms...)",
                        amount,
                        accumulated,
                        PULSE_DEBOUNCE_S * 1000,
                    )

                    # Cancel any pending flush and restart the window
                    if flush_task and not flush_task.done():
                        flush_task.cancel()

                    flush_task = asyncio.create_task(flush_accumulated())

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
