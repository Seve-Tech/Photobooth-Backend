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

# How long to wait before retrying a dropped serial or WebSocket connection.
RECONNECT_S: float = 3.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def close_serial(ser: serial.Serial | None) -> None:
    """Close a serial port, ignoring errors from already-dead handles."""
    if ser is None:
        return
    try:
        if ser.is_open:
            ser.close()
    except Exception:
        pass


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

async def _ensure_serial(
    ser: serial.Serial | None,
    port: str | None,
    baud: int,
    *,
    auto_detect: bool,
) -> tuple[serial.Serial | None, str | None]:
    """
    Open the serial port when needed. Re-detects the port after unplug/replug
    when auto_detect is True.
    """
    if ser is not None and ser.is_open:
        return ser, port

    close_serial(ser)

    current_port = port
    if auto_detect:
        current_port = find_arduino_port()
        if current_port is None:
            logger.warning(
                "Arduino not detected — plug it in and retrying in %.0fs...",
                RECONNECT_S,
            )
            return None, port

    assert current_port is not None

    try:
        logger.info("Opening serial port %s at %d baud...", current_port, baud)
        opened = serial.Serial(current_port, baud, timeout=1)
    except serial.SerialException as exc:
        logger.warning(
            "Could not open serial port %s: %s — retrying in %.0fs...",
            current_port,
            exc,
            RECONNECT_S,
        )
        return None, port

    if auto_detect:
        logger.info("Auto-detected Arduino on port: %s", current_port)

    logger.info("Serial port open.")
    return opened, current_port


async def run_bridge(port: str | None, baud: int, *, auto_detect: bool) -> None:
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
    logger.info("Connecting to backend at %s ...", WS_URL)

    accumulated: float = 0.0  # survives reconnects so failed flushes are retried
    ser: serial.Serial | None = None
    current_port = port

    while True:
        ser, current_port = await _ensure_serial(
            ser, current_port, baud, auto_detect=auto_detect,
        )
        if ser is None:
            await asyncio.sleep(RECONNECT_S)
            continue

        serial_lost = False

        try:
            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=60,
            ) as ws:
                logger.info("Connected to backend. Waiting for Arduino messages...")

                flush_task: asyncio.Task | None = None  # debounce timer task
                disconnect_event = asyncio.Event()

                async def drain_ws() -> None:
                    """Keep the connection alive by processing incoming frames (pings, etc.)."""
                    try:
                        async for _ in ws:
                            pass
                    except websockets.ConnectionClosed:
                        disconnect_event.set()

                async def send_total(total: float, *, retry: bool = False) -> None:
                    nonlocal accumulated
                    if total <= 0:
                        return
                    if retry:
                        logger.info(
                            "Retrying previously unsent total after reconnect: PHP %.2f",
                            total,
                        )
                    else:
                        logger.info(
                            "Pulse window closed — flushing accumulated total: PHP %.2f",
                            total,
                        )
                    msg = build_amount_message(total)
                    try:
                        await ws.send(msg)
                    except websockets.ConnectionClosed:
                        accumulated += total
                        disconnect_event.set()
                        raise

                async def flush_accumulated() -> None:
                    """Wait for the debounce window, then send the accumulated total."""
                    nonlocal accumulated
                    await asyncio.sleep(PULSE_DEBOUNCE_S)
                    total = accumulated
                    accumulated = 0.0
                    await send_total(total)

                async def retry_unsent() -> None:
                    nonlocal accumulated
                    total = accumulated
                    accumulated = 0.0
                    await send_total(total, retry=True)

                def on_flush_done(task: asyncio.Task) -> None:
                    if task.cancelled():
                        return
                    if task.exception() is not None:
                        disconnect_event.set()

                drain_task = asyncio.create_task(drain_ws())

                if accumulated > 0:
                    flush_task = asyncio.create_task(retry_unsent())
                    flush_task.add_done_callback(on_flush_done)

                try:
                    # Main loop: read from serial, accumulate, debounce-flush
                    while not disconnect_event.is_set() and not serial_lost:
                        try:
                            # readline() blocks up to timeout=1s, returns b"" if nothing arrives
                            raw_line = await asyncio.get_event_loop().run_in_executor(
                                None, ser.readline
                            )
                        except (serial.SerialException, OSError) as exc:
                            logger.warning(
                                "Serial connection lost: %s — reconnecting...",
                                exc,
                            )
                            serial_lost = True
                            break

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
                        flush_task.add_done_callback(on_flush_done)
                finally:
                    drain_task.cancel()
                    try:
                        await drain_task
                    except asyncio.CancelledError:
                        pass
                    if flush_task and not flush_task.done():
                        flush_task.cancel()
                        try:
                            await flush_task
                        except (asyncio.CancelledError, websockets.ConnectionClosed):
                            pass

        except (websockets.ConnectionClosed, OSError) as exc:
            if not serial_lost:
                logger.warning(
                    "WebSocket disconnected: %s — retrying in %.0fs...",
                    exc,
                    RECONNECT_S,
                )
        except Exception as exc:
            if not serial_lost:
                logger.exception(
                    "Unexpected error: %s — retrying in %.0fs...",
                    exc,
                    RECONNECT_S,
                )

        if serial_lost:
            close_serial(ser)
            ser = None

        await asyncio.sleep(RECONNECT_S)


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

    auto_detect = args.port is None
    if auto_detect:
        logger.info("Auto-detect enabled; will wait for Arduino if unplugged.")
    else:
        logger.info("Using serial port: %s", args.port)

    try:
        asyncio.run(run_bridge(args.port, args.baud, auto_detect=auto_detect))
    except KeyboardInterrupt:
        logger.info("Bridge stopped.")


if __name__ == "__main__":
    main()
