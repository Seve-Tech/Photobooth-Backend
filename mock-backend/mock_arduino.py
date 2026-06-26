"""
Mock Arduino / bill-acceptor client.

Simulates the bill acceptor sending pulse signals over WebSocket.
Run this alongside the main server to test the full flow without hardware.

Usage:
    python mock_arduino.py
    python mock_arduino.py --session-id <id>   # attach to a session
    python mock_arduino.py --auto               # send pulses automatically
"""

import sys
from pathlib import Path

# Add project root to sys.path to allow running from subdirectories
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import asyncio
import json
import argparse
from datetime import datetime

import websockets

from app.core.config import settings

# Reads API key from .env automatically — no need to hardcode it
SERVER_URL = f"ws://localhost:{settings.port}/ws?api_key={settings.api_key}&client_type=arduino"

# Human-readable denomination labels — built from settings so it always matches config.py
DENOMINATION_LABELS: dict[float, str] = {
    amount: f"PHP {int(amount)}"
    for amount in sorted(settings.valid_denominations)
}


def build_amount_message(amount: float) -> str:
    """Build a WSMessage JSON string for an amount signal."""
    payload: dict = {
        "amount": amount,
    }
    message = {
        "type": "amount_received",
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return json.dumps(message)


async def listen_for_events(websocket) -> None:
    """Background task: print every broadcast received from the server."""
    async for raw in websocket:
        try:
            msg = json.loads(raw)
            msg_type = msg.get("type", "unknown")
            payload  = msg.get("payload", {})

            if msg_type == "bill_accepted":
                status = payload.get("acceptor_status") or payload.get("status")
                amount = payload.get("amount", 0)
                pulse_count = payload.get("pulse_count")
                pulse_str = f", pulses={pulse_count}" if pulse_count is not None else ""
                print(f"\n  [SERVER] bill_accepted — amount=PHP {amount:.2f}, status={status}{pulse_str}")

            elif msg_type == "session_updated":
                sid    = payload.get("id", "?")
                status = payload.get("status")
                total  = payload.get("total_paid", 0)
                print(f"\n  [SERVER] session_updated — id={sid}, status={status}, total=PHP {total:.2f}")

            elif msg_type == "pong":
                print("  [SERVER] pong ✓")

            elif msg_type == "error":
                print(f"\n  [SERVER] ERROR — {payload.get('detail')}")

        except Exception as exc:
            print(f"  [CLIENT] Failed to parse server message: {exc}")


async def interactive_mode(session_id: str | None) -> None:
    """Let the user manually type pulse counts."""
    safe_url = f"ws://localhost:{settings.port}/ws?api_key=***"
    print(f"\nConnecting to {safe_url} …")

    async with websockets.connect(SERVER_URL) as ws:
        print("Connected!\n")

        # Start listening for server events in background
        asyncio.create_task(listen_for_events(ws))

        print("Available denominations:")
        for amt, label in DENOMINATION_LABELS.items():
            print(f"  PHP {amt} -> {label}")
        valid = list(DENOMINATION_LABELS.keys())
        print(f"\nType a denomination amount {valid} and press Enter. Ctrl+C to quit.\n")

        loop = asyncio.get_event_loop()

        while True:
            try:
                raw_input = await loop.run_in_executor(None, input, "amount > ")
                amount = float(raw_input.strip())
                label = DENOMINATION_LABELS.get(amount, "unknown denomination")
                print(f"  Sending PHP {amount:.2f} ({label}) …")
                await ws.send(build_amount_message(amount))
            except ValueError:
                print(f"  Please enter a valid amount: {list(DENOMINATION_LABELS.keys())}")
            except KeyboardInterrupt:
                print("\nDisconnecting…")
                break


async def auto_mode(session_id: str | None) -> None:
    """Automatically send one of each denomination with a 2-second gap."""
    safe_url = f"ws://localhost:{settings.port}/ws?api_key=***"
    print(f"\nConnecting to {safe_url} in AUTO mode …")

    async with websockets.connect(SERVER_URL) as ws:
        print("Connected! Will send all denominations in sequence.\n")

        asyncio.create_task(listen_for_events(ws))

        for amount, label in DENOMINATION_LABELS.items():
            print(f"Sending PHP {amount:.2f} -> {label}")
            await ws.send(build_amount_message(amount))
            await asyncio.sleep(2)

        # Give the listener time to receive the last broadcast
        await asyncio.sleep(1)
        print("\nAuto mode done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock Arduino bill-acceptor client")
    parser.add_argument("--session-id", type=str, default=None, help="Photobooth session ID")
    parser.add_argument("--auto", action="store_true", help="Auto-send all denominations")
    args = parser.parse_args()

    try:
        if args.auto:
            asyncio.run(auto_mode(args.session_id))
        else:
            asyncio.run(interactive_mode(args.session_id))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
