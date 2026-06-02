# Photobooth Backend

FastAPI backend for the photobooth system. Handles bill-acceptor pulse signals, manages sessions, and broadcasts real-time events over WebSocket.

---

## 🗺️ Quick Navigation

Click any of the sections below to jump directly to it:

| Section | Description |
| :--- | :--- |
| [🏗️ System Architecture](#architecture) | Hardware connectivity, components, and data flow |
| [📁 Project Structure](#key-files) | Map of key codebase files and directories |
| [⚙️ Setup & Installation](#setup) | Steps to configure environment, database, and run |
| [🔌 Running with Hardware](#running-with-hardware-arduino--bill-acceptor) | Launching with the physical Arduino & Bill Acceptor |
| [💻 Development without Hardware](#development-without-hardware-mock-arduino) | Simulating hardware pulses locally |
| [🌐 API Reference](#api-reference) | WebSocket protocol specification and REST endpoints |
| [🪙 Pulse-to-Cash Mapping](#pulse--denomination-map) | Configuration detail for TB74 bill acceptor signals |
| [🧪 Running Unit Tests](#running-unit-tests) | Verifying changes with the `pytest` suite |

---

## Architecture

```
TB74 Bill Acceptor
      │
      │  electrical pulses (wire)
      ▼
   Arduino
      │
      │  USB serial  (e.g. COM3)  — sends pulse count as plain text: "10\n"
      ▼
   Mini-PC  ──────────────────────────────────────────────────────────┐
      │                                                               │
      │  arduino_bridge.py           FastAPI Server (:8000)           │
      │  reads USB → forwards ──────►  /ws  WebSocket  ◄─────────────┘
      │  as WebSocket message           /api/v1/bills       Front-end
      │                                 /api/v1/sessions    (touchscreen)
      │                                      │
      │                                      ▼
      │                                 PostgreSQL DB
      └───────────────────────────────────────────────
```

### Key files

```
photobooth-backend/
├── main.py                         # Entry point — starts the server
├── arduino_bridge.py               # Real hardware: reads Arduino USB → forwards to backend
├── mock_arduino.py                 # Development only: simulates Arduino via keyboard input
├── seed_db.py                      # One-time DB seed (branch, unit, package)
├── .env.example                    # Config template — copy to .env
└── app/
    ├── app_factory.py              # Wires up FastAPI, CORS, routes, DB pool lifecycle
    ├── core/
    │   ├── config.py               # All settings (reads from .env)
    │   └── security.py             # API key guard + WebSocket rate limiter
    ├── db/                         # PostgreSQL layer (asyncpg)
    │   ├── connection.py           # Connection pool init / teardown
    │   ├── branches.py             # Branch queries
    │   ├── units.py                # Photobooth unit queries
    │   ├── packages.py             # Package queries
    │   ├── sessions.py             # Session queries
    │   ├── payments.py             # Payment queries
    │   ├── bill_logs.py            # Bill acceptor hardware log queries
    │   ├── photos.py               # Photo record queries
    │   ├── print_jobs.py           # Print job queries
    │   ├── device_events.py        # Device event log queries
    │   ├── expenses.py             # Expense queries
    │   └── sync.py                 # Sync queue queries
    ├── models/
    │   └── schemas.py              # Pydantic models / types
    ├── services/
    │   └── bill_acceptor.py        # Pulse → amount → DB → WS broadcast
    ├── api/routes/
    │   ├── health.py               # GET /health
    │   ├── bills.py                # POST /api/v1/bills/pulse, GET /api/v1/bills/payments
    │   └── sessions.py             # CRUD /api/v1/sessions
    └── websocket/
        ├── manager.py              # Tracks connected clients, handles broadcast
        └── endpoints.py            # /ws — auth check, rate limit, message dispatch
```

---

## Setup

### Requirements
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- PostgreSQL running locally (or on the same machine)

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```ini
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
API_KEY=replace-with-a-long-random-string

# The front-end origin allowed by CORS (use localhost:3000 for local dev)
FRONTEND_ORIGIN=http://localhost:3000

# Max WebSocket messages per client per minute
WS_RATE_LIMIT=40

# PostgreSQL connection (no driver prefix — raw asyncpg DSN)
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/photobooth_db

# Identity of this physical machine — set once per deployment
BRANCH_ID=1
UNIT_ID=1
```

### 3. Create the database tables

```bash
python migrate.py
```

### 4. Seed initial data (run once)

Before the app can create sessions, the database needs at least one branch, one photobooth unit, and one package. Run this once after migrating:

```bash
python seed_db.py
```

This creates:
- `branches` row — your photobooth location
- `photobooth_units` row — this physical machine
- `packages` row — the Standard Package (PHP 200.00)

#### Developer Options
If you want to clear all data and reset the database schema from scratch before seeding, run with the `--reset` flag:
```bash
python seed_db.py --reset
```
*Note: This drops all existing tables and re-executes migrations.*

Safe to re-run without flags — it will skip rows that already exist.

### 5. Run the server

```bash
python main.py
# or with auto-reload during development:
uvicorn main:app --reload
```

Server starts at **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

---

## Running with Hardware (Arduino + Bill Acceptor)

Open **two terminals**:

**Terminal 1 — start the backend:**
```bash
python main.py
```

**Terminal 2 — start the Arduino bridge:**
```bash
# Auto-detect the Arduino's USB port:
python arduino_bridge.py

# Or specify the port manually:
python arduino_bridge.py --port COM3        # Windows
python arduino_bridge.py --port /dev/ttyUSB0  # Linux
```

The bridge reads the pulse count from the Arduino over USB and forwards it to the backend as a WebSocket message. It reconnects automatically if either side drops.

> **Arduino firmware requirement:** The Arduino sketch must print the pulse count as plain text followed by a newline: `Serial.println(pulseCount);`

---

## Development without Hardware (Mock Arduino)

Open **two terminals**:

**Terminal 1 — start the backend:**
```bash
python main.py
```

**Terminal 2 — run the mock client:**
```bash
# Interactive: type pulse counts manually
python mock_arduino.py

# Auto mode: sends all denominations in sequence
python mock_arduino.py --auto

# Attach to a specific session:
python mock_arduino.py --session-id <uuid>
```

---

## API Reference

### WebSocket  `/ws`

All clients (front-end and Arduino bridge) connect here. **API key required as a query param.**

```
ws://localhost:8000/ws?api_key=<your-API_KEY>
```

Rate limit: **40 messages per minute** per connection (set via `WS_RATE_LIMIT` in `.env`). Exceeding it returns an `error` message; the connection stays open.

**Send — Arduino bridge → server:**
```json
{
  "type": "pulse_received",
  "payload": {
    "pulse_count": 10,
    "source": "arduino",
    "session_id": "uuid-of-active-session"
  }
}
```

**Receive — server → all connected clients:**
```json
{
  "type": "bill_accepted",
  "payload": {
    "pulse_count": 10,
    "amount": 100.0,
    "currency": "PHP",
    "acceptor_status": "validated",
    "session_id": "uuid-of-active-session"
  }
}
```

```json
{
  "type": "session_updated",
  "payload": {
    "id": "uuid",
    "status": "PENDING",
    "total_paid": 100.0
  }
}
```

Message types: `bill_accepted`, `session_updated`, `error`, `ping`, `pong`

---

### REST Endpoints

All `/api/v1/` routes require the header:
```
X-API-Key: <your-API_KEY>
```
`/health` is open — no key needed.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ws` | WebSocket client count |
| `POST` | `/api/v1/bills/pulse?pulse_count=10` | Send pulse via HTTP (fallback / testing) |
| `GET` | `/api/v1/bills/payments` | List all payment records |
| `POST` | `/api/v1/sessions` | Create a new session |
| `GET` | `/api/v1/sessions` | List all sessions |
| `GET` | `/api/v1/sessions/{id}` | Get one session |
| `PATCH` | `/api/v1/sessions/{id}` | Update session status |

---

## Pulse → Denomination Map

Configured in `config.py`. Current mapping (update to match your TB74 settings):

| Pulses | Amount |
|--------|--------|
| 1 | PHP 10 |
| 2 | PHP 20 |
| 5 | PHP 50 |
| 10 | PHP 100 |
| 20 | PHP 200 |

To change the mapping, update `bill_pulse_map` in `app/core/config.py`.

---

## Running Unit Tests

```bash
uv run pytest -v
```

---

## TODOs

- [ ] Pass the real money value from arduino to back-end
