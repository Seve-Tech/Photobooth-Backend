# Photobooth Backend

FastAPI backend for the photobooth system. Handles bill-acceptor pulse signals, manages sessions, and broadcasts real-time events over WebSocket.

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
    (PostgreSQL)
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
    │   └── security.py             # API key guard + WebSocket rate limiter
    ├── db/                         # PostgreSQL queries & connection pool
    │   ├── connection.py           # asyncpg pool lifecycle
    │   ├── payments.py             # Payment queries
    │   └── sessions.py             # Session queries
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

Then open `.env` and configure your setup:
```ini
API_KEY=replace-with-a-long-random-string

# Frontend origin allowed by CORS
FRONTEND_ORIGIN=https://photobooth.yourdomain.com

# PostgreSQL database connection
DATABASE_URL=postgresql://your_db_username:your_db_password@localhost:5432/photobooth_db

# Machine Identity (Set per physical deployment)
BRANCH_ID=1
UNIT_ID=1
```

To generate a random API key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Setup Database

Run the migration script to automatically create the database and all tables:
```bash
python migrate.py
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
    "acceptor_status": "validated",
    "payment_status": "completed",
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

## Running Unit Tests

The project includes a suite of unit tests for the core logic and REST endpoints using a mocked database connection.

To run the tests:
```bash
uv run pytest -v
```

---

## TODOs
- [ ] Confirm exact pulse-count map with hardware team (TB74 config)
