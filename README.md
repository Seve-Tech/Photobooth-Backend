# Photobooth Backend

FastAPI backend for the photobooth system. Handles bill-acceptor (AGmarketing TB74) pulse signals, manages sessions, and broadcasts real-time events over WebSocket.

---

## Architecture

```
Arduino / Bill Acceptor
        │
        │ pulse signal (WebSocket or HTTP POST)
        ▼
┌───────────────────┐
│   FastAPI Server  │
│                   │
│  /ws  WebSocket   │◄──── Front-end (subscribes for real-time events)
│  /api/v1/bills    │
│  /api/v1/sessions │
└────────┬──────────┘
         │
         ▼
      Database
  (in-memory now → swap to real DB later)
```

### Key files

```
photobooth-backend/
├── main.py                         # Entry point
├── mock_arduino.py                 # Simulates Arduino for local testing
├── .env.example                    # Config template
└── app/
    ├── app_factory.py              # Creates the FastAPI app
    ├── core/
    │   ├── config.py               # Settings (reads .env)
    │   ├── database.py             # DB layer (in-memory stub → replace later)
    │   └── security.py             # API key guard + WebSocket rate limiter
    ├── models/
    │   └── schemas.py              # Pydantic models / types
    ├── services/
    │   └── bill_acceptor.py        # Pulse → amount logic + DB + WS broadcast
    ├── api/routes/
    │   ├── bills.py                # POST /api/v1/bills/pulse
    │   ├── sessions.py             # CRUD /api/v1/sessions
    │   └── health.py               # GET /health
    └── websocket/
        ├── manager.py              # Connection manager (broadcast helper)
        └── endpoints.py            # /ws WebSocket endpoint
```

---

## Setup

### Requirements
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

### Install dependencies

```bash
uv sync
```

### Configure environment

```bash
cp .env.example .env
```

Then open `.env` and set a real secret key:
```
API_KEY=replace-with-a-long-random-string
```

Generate one with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Also set your front-end origin before going to production:
```
FRONTEND_ORIGIN=https://photobooth.yourdomain.com
```

### Run the server

```bash
uv run python main.py
# or with auto-reload during development:
DEBUG=true uv run uvicorn main:app --reload
```

Server starts at **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

---

## Testing with the mock Arduino client

Open **two terminals**:

**Terminal 1 — start the server:**
```bash
uv run python main.py
```

**Terminal 2 — run the mock client:**
```bash
# Interactive: type pulse counts manually
uv run python mock_arduino.py

# Auto mode: sends all denominations in sequence
uv run python mock_arduino.py --auto

# With a session ID (create one via the API first):
uv run python mock_arduino.py --session-id <uuid>
```

---

## API Reference

### WebSocket  `/ws`

Connect from the front-end or Arduino bridge. **An API key is required as a query param.**

```
ws://localhost:8000/ws?api_key=<your-API_KEY>
```

**Send (client → server):**
```json
{
  "type": "pulse_received",
  "payload": {
    "pulse_count": 3,
    "source": "arduino",
    "session_id": "optional-uuid"
  }
}
```

Rate limit: **30 messages per minute** per connection (configurable via `WS_RATE_LIMIT` in `.env`). Exceeding it returns an `error` message; the connection stays open.

**Receive (server → all clients):**
```json
{
  "type": "bill_accepted",
  "payload": {
    "pulse_count": 3,
    "amount": 100.0,
    "currency": "PHP",
    "status": "validated",
    "session_id": "optional-uuid"
  }
}
```

Message types: `bill_accepted`, `session_updated`, `error`, `ping`, `pong`

---

### REST Endpoints

All routes under `/api/v1/` require the header:
```
X-API-Key: <your-API_KEY>
```
The `/health` routes are open — no key needed.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ws` | WebSocket client count |
| `POST` | `/api/v1/bills/pulse?pulse_count=3` | Send pulse via HTTP |
| `GET` | `/api/v1/bills/payments` | List all payments |
| `POST` | `/api/v1/sessions` | Create a new session |
| `GET` | `/api/v1/sessions` | List all sessions |
| `GET` | `/api/v1/sessions/{id}` | Get one session |
| `PATCH` | `/api/v1/sessions/{id}` | Update session status |

---

## Pulse → Denomination map

| Pulses | Amount |
|--------|--------|
| 1 | PHP 20 |
| 2 | PHP 50 |
| 3 | PHP 100 |
| 4 | PHP 200 |
| 5 | PHP 500 |

To change the mapping, edit `BILL_PULSE_MAP` in `app/core/config.py` or override via `.env`.

---

## Plugging in the real database

When the DB is ready:

1. Set `DATABASE_URL` in `.env`.
2. Open `app/core/database.py`.
3. Replace the in-memory dicts (`_sessions`, `_payments`) with real ORM queries.
4. All function signatures stay the same — no other file needs to change.

---

## TODOs

- [ ] Wire up real database (waiting on DB team)
- [ ] Write unit tests for `bill_acceptor.py`
- [ ] **Add a `GET /api/v1/bills/payments/{session_id}` convenience route** (Don't know if this is still needed)
- [ ] Confirm exact pulse-count map with hardware team (TB74 config)
