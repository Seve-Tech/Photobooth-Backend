# Photobooth Backend

FastAPI backend for the photobooth system. It handles bill-acceptor pulse signals, manages customer sessions, integrates with DSLRBooth API/webhooks, and broadcasts real-time events over WebSockets.

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
| [📸 Development without DSLRBooth](#-development-without-dslrbooth-mock-server) | Simulating DSLRBooth HTTP API & Webhooks locally |
| [🌐 API Reference](#api-reference) | WebSocket protocol specification and REST endpoints |
| [🪙 Pulse-to-Cash Mapping](#pulse--denomination-map) | Configuration detail for TB74 bill acceptor signals |
| [🧪 Running Unit Tests](#running-unit-tests) | Verifying changes with the `pytest` suite |
| [📝 Roadmap & TODOs](#roadmap--todos) | Upcoming tasks and completed items |

---

## Architecture

```
TB74 Bill Acceptor
      │
      │  electrical pulses (wire)
      ▼
   Arduino
      │
      │  USB serial  (e.g. COM3)  — sends amount as plain text: "50\n" or JSON: '{"amount":50}'
      ▼
   Mini-PC  ──────────────────────────────────────────────────────────┐
      │                                                               │
      │  arduino_bridge.py           FastAPI Server (:8000)           │
      │  reads USB → forwards ──────►  /ws  WebSocket  ◄─────────────┘
      │  as WebSocket message           /api/v1/bills       Front-end
      │                                 /api/v1/sessions    (touchscreen)
      │                                 /api/v1/photo-session
      │                                 /api/v1/admin
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
├── seed_db.py                      # One-time DB seed (branch, unit, package)
├── migrate.py                      # Database migrations
├── .env.example                    # Config template — copy to .env
└── app/
    ├── app_factory.py              # Wires up FastAPI, CORS, routes, DB pool lifecycle
    ├── core/
    │   ├── config.py               # All settings (reads from .env)
    │   └── security.py             # API key guard + WebSocket rate limiter
    ├── db/                         # PostgreSQL layer (asyncpg)
    │   ├── connection.py           # Connection pool init / teardown
    │   ├── admin_settings.py       # Admin settings queries (PIN, theme)
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
    │   └── schemas.py              # Pydantic models / validation types
    ├── services/
    │   ├── bill_acceptor.py        # Pulse → amount → DB → WS broadcast
    │   └── dslrbooth_service.py    # DSLRBooth controller & API calls
    ├── api/routes/
    │   ├── health.py               # GET /health, GET /health/ws
    │   ├── bills.py                # POST /api/v1/bills/pulse, GET /api/v1/bills/payments
    │   ├── sessions.py             # CRUD /api/v1/sessions
    │   ├── photo_session.py        # DSLRBooth start/webhook/complete routes
    │   └── admin.py                # Admin dashboard verify-pin, themes & queries
    └── websocket/
        ├── manager.py              # Tracks connected clients, handles broadcast
        └── endpoints.py            # /ws — auth check, rate limit, message dispatch
mock-backend/
├── mock_arduino.py                 # Development only: simulates Arduino via keyboard input
└── mock_dslrbooth.py               # Development only: simulates DSLRBooth API + triggers
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

# ── DSLRBooth Integration ─────────────────────────
# Set DSLRBOOTH_MOCK=true during local development (no DSLRBooth installed)
# Set DSLRBOOTH_MOCK=false on the client's Mini PC for production
DSLRBOOTH_MOCK=true
DSLRBOOTH_HOST=http://localhost:1500
DSLRBOOTH_PASSWORD=                    # Get this from DSLRBooth Settings → General → API tab
DSLRBOOTH_BOOTH_MODE=print             # Options: print, gif, boomerang, video
DSLRBOOTH_SESSION_TIMEOUT_S=300        # Max seconds to wait before timing out
DSLRBOOTH_MOCK_SESSION_DURATION_S=10   # Mock session duration in seconds
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
- `admin_settings` row — seeds the default Admin PIN (`000000`) for the unit

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

The bridge reads the amount from the Arduino over USB and forwards it to the backend as a WebSocket message. It reconnects automatically if either side drops.

> **Arduino firmware requirement:** The Arduino sketch must print the amount as plain text followed by a newline: `Serial.println(amount);` or as a JSON string: `Serial.println("{\"amount\": 50}");`

---

## Development without Hardware (Mock Arduino)

Open **two terminals**:

**Terminal 1 — start the backend:**
```bash
python main.py
```

**Terminal 2 — run the mock client:**
```bash
# Interactive: type amounts manually
python mock-backend/mock_arduino.py

# Auto mode: sends all denominations in sequence
python mock-backend/mock_arduino.py --auto

# Attach to a specific session:
python mock-backend/mock_arduino.py --session-id <uuid>
```

---

## 📸 Development without DSLRBooth (Mock Server)

To test the photo session flow without having DSLRBooth installed:

**Terminal 1 — run the mock DSLRBooth API server:**
```bash
python mock-backend/mock_dslrbooth.py
```
This runs a mock server on port 1500. When `/api/start` is triggered, it runs a background task simulating the 10 standard DSLRBooth trigger webhook callbacks back to the backend.

**Terminal 2 — configure env and run backend:**
Ensure `.env` contains:
```ini
DSLRBOOTH_MOCK=false
DSLRBOOTH_HOST=http://localhost:1500
```
Then run the backend:
```bash
python main.py
```
The backend will now make real HTTP calls to the mock server, which will fire webhooks back to the backend.

*Note: Alternatively, you can set `DSLRBOOTH_MOCK=true` in `.env` to simulate the webhook callbacks internally inside the backend process without needing to run `mock_dslrbooth.py`.*

---

## API Reference

### WebSocket `/ws`

All clients (front-end and Arduino bridge) connect here. **API key required as a query param.**

```
ws://localhost:8000/ws?api_key=<your-API_KEY>
```

Rate limit: **40 messages per minute** per connection (set via `WS_RATE_LIMIT` in `.env`). Exceeding it returns an `error` message; the connection stays open.

**Send — Arduino bridge → server:**
```json
{
  "type": "amount_received",
  "payload": {
    "amount": 50.0
  }
}
```

**Receive — server → all connected clients:**
```json
{
  "type": "bill_accepted",
  "payload": {
    "amount": 50.0,
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
    "status": "pending",
    "total_paid": 100.0
  }
}
```

Message types: `pulse_received`, `bill_accepted`, `session_updated`, `error`, `ping`, `pong`, `photo_session_started`, `photo_session_complete`, `photo_session_error`, `dslrbooth_status`

---

### REST Endpoints

All endpoints prefixed with `/api/v1/` require the header:
```http
X-API-Key: <your-API_KEY>
```
`/health` and `/api/v1/photo-session/webhook` do not require an API key.

#### 🩺 Health & Monitoring
| Method | Path | Auth | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/health` | Open | Liveness + database connectivity status |
| `GET` | `/health/ws` | Open | Total number of currently connected WS clients |

#### 🪙 Bills & Payments
| Method | Path | Auth | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/bills/amount` | Key | Send amount via HTTP (fallback/test query param: `amount`, optional `session_id`) |
| `GET` | `/api/v1/bills/payments` | Key | List payments, optionally filtered by `session_id` |

#### 📂 Sessions
| Method | Path | Auth | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/sessions` | Key | Create a new photobooth session (returns session UUID) |
| `GET` | `/api/v1/sessions` | Key | List all session records |
| `GET` | `/api/v1/sessions/{session_id}` | Key | Retrieve details of a single session |
| `PATCH` | `/api/v1/sessions/{session_id}` | Key | Partially update session details (status, total_paid, customer_ref) |

#### 📸 DSLRBooth Photo Session Integration
| Method | Path | Auth | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/photo-session/start` | Key | Starts a DSLRBooth photo capture session (expects JSON body: `{"session_id": "<uuid>"}`) |
| `GET` | `/api/v1/photo-session/webhook` | Open | Webhook trigger receiver called by DSLRBooth (sends query param `event_type`) |
| `POST` | `/api/v1/photo-session/complete/{session_id}` | Key | Explicitly completes the photo session, marking it `COMPLETED` |

#### ⚙️ Admin Dashboard
| Method | Path | Auth | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/admin/verify-pin` | Key | Verify the 6-digit admin PIN (expects JSON: `{"pin": "000000"}`) |
| `PATCH` | `/api/v1/admin/pin` | Key | Update the 6-digit admin PIN (expects JSON: `{"new_pin": "123456"}`) |
| `GET` | `/api/v1/admin/sessions` | Key | Paginated list of sessions for transactions overview (query params: `limit`, `offset`) |
| `GET` | `/api/v1/admin/logs` | Key | Paginated hardware logs / device events (query params: `limit`, `offset`, `severity`) |
| `GET` | `/api/v1/admin/package-price` | Key | Fetch current price of package (query param: `package_id`) |
| `PATCH` | `/api/v1/admin/package-price` | Key | Update package price (expects JSON: `{"package_id": 1, "price": 250.0}`) |
| `GET` | `/api/v1/admin/theme` | Key | Get the default kiosk UI theme |
| `PATCH` | `/api/v1/admin/theme` | Key | Update the default kiosk UI theme (expects JSON: `{"theme": "neon"}`) |

---

## Accepted Denominations

Configured in `config.py`. Current valid denominations (update to match your physical bill acceptor settings):

| Accepted Denomination |
| :---: |
| PHP 20.00 |
| PHP 50.00 |
| PHP 100.00 |
| PHP 200.00 |

To change the accepted values, update `valid_denominations` in `app/core/config.py`.

---

## Running Unit Tests

```bash
uv run pytest -v
```

---

## TODOs

- [ ] Setup real DSLRBooth software application to test the photobooth functionality
