"""
Mock Arduino / bill-acceptor client.

Simulates the AGmarketing TB74 sending pulse signals over WebSocket.
Run this alongside the main server to test the full flow without hardware.

Usage:
    uv run python mock_arduino.py
    uv run python mock_arduino.py --session-id <id>   # attach to a session
    uv run python mock_arduino.py --auto               # send pulses automatically
"""

import asyncio
import json
import argparse
from datetime import datetime

import websockets


SERVER_URL = "ws://localhost:8000/ws"

# Human-readable denomination labels (matches settings.bill_pulse_map)
DENOMINATION_LABELS: dict[int, str] = {
    1: "PHP 20",
    2: "PHP 50",
    3: "PHP 100",
    4: "PHP 200",
    5: "PHP 500",
}


def build_pulse_message(pulse_count: int, session_id: str | None = None) -> str:
    """Build a WSMessage JSON string for a pulse signal."""
    payload: dict = {
        "pulse_count": pulse_count,
        "received_at": datetime.utcnow().isoformat(),
        "source": "mock_arduino",
    }
    if session_id:
        payload["session_id"] = session_id

    message = {
        "type": "pulse_received",
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
                status = payload.get("status")
                amount = payload.get("amount", 0)
                pulses = payload.get("pulse_count")
                print(f"\n  [SERVER] bill_accepted — pulses={pulses}, amount=PHP {amount:.2f}, status={status}")

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
    print(f"\nConnecting to {SERVER_URL} …")

    async with websockets.connect(SERVER_URL) as ws:
        print("Connected!\n")

        # Start listening for server events in background
        asyncio.create_task(listen_for_events(ws))

        print("Available denominations:")
        for pulse, label in DENOMINATION_LABELS.items():
            print(f"  {pulse} pulse(s) → {label}")
        print("\nType a pulse count (1-5) and press Enter. Ctrl+C to quit.\n")

        loop = asyncio.get_event_loop()

        while True:
            try:
                raw_input = await loop.run_in_executor(None, input, "pulse count > ")
                pulse_count = int(raw_input.strip())
                label = DENOMINATION_LABELS.get(pulse_count, "unknown denomination")
                print(f"  Sending {pulse_count} pulse(s) ({label}) …")
                await ws.send(build_pulse_message(pulse_count, session_id))
            except ValueError:
                print("  Please enter a number between 1 and 5.")
            except KeyboardInterrupt:
                print("\nDisconnecting…")
                break


async def auto_mode(session_id: str | None) -> None:
    """Automatically send one of each denomination with a 2-second gap."""
    print(f"\nConnecting to {SERVER_URL} in AUTO mode …")

    async with websockets.connect(SERVER_URL) as ws:
        print("Connected! Will send all denominations in sequence.\n")

        asyncio.create_task(listen_for_events(ws))

        for pulse_count, label in DENOMINATION_LABELS.items():
            print(f"Sending {pulse_count} pulse(s) → {label}")
            await ws.send(build_pulse_message(pulse_count, session_id))
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
