# Agribot Flask Backend

REST API server for the Agribot agricultural robot — manages device fleet, field scanning, weed detection, and analytics.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Flask 3.1 |
| Database | PostgreSQL + SQLAlchemy |
| Auth | JWT (flask-jwt-extended) |
| Device | Jetson (HTTP + multipart image upload) |

---

## Features

- **JWT Authentication** — token-based login for frontend and device clients
- **Device Fleet Management** — register devices, configure serial/camera settings, ping connectivity
- **Field Definition** — create fields with grid dimensions for structured scanning
- **Weed Detection** — run scans in grid mode (cell-by-cell) or route mode (instruction sequence)
- **Real-time Status Polling** — live progress tracking (cells scanned, weeds found, grid state)
- **Analytics** — density maps, species breakdowns, historical run filtering
- **Command Queue** — send movement commands (forward / backward / left / right / stop) to devices
- **Jetson Integration** — devices POST detection images; server queues movement commands for polling

---

## API Overview

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Get JWT token |
| POST | `/api/auth/logout` | Invalidate token |
| GET | `/api/auth/me` | Current user info |

### Devices
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all devices |
| POST | `/api/devices` | Register new device |
| GET | `/api/devices/{id}/ping` | Check device connectivity |
| GET/PUT | `/api/devices/{id}/settings` | Fetch / update device config |
| POST | `/api/devices/{id}/move` | Send movement command |

### Fields
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/fields` | List / create fields |
| PUT/DELETE | `/api/fields/{id}` | Update / delete field |

### Detection
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/devices/{id}/detection/start` | Start detection run |
| POST | `/api/devices/{id}/detection/stop` | Stop active run |
| GET | `/api/devices/{id}/detection/status` | Poll run progress |
| GET | `/api/devices/{id}/detection/grid` | Live weed density grid |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/metrics` | Totals: weeds, runs, active devices |
| GET | `/api/dashboard/density-map` | 2D weed count grid |
| GET | `/api/dashboard/species-breakdown` | Weed species distribution |
| GET | `/api/runs` | Paginated run history (filterable) |
| GET | `/api/runs/{runId}/detection-logs` | Per-detection log entries |

### Routes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/routes` | List / create movement routes |
| PUT/DELETE | `/api/routes/{id}` | Update / delete route |

### Jetson Device
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/predictions` | Upload detection image + result |
| GET | `/api/get-commands/{device_id}` | Poll pending movement commands |

---

## Getting Started

**Prerequisites**
- Python 3.10+
- PostgreSQL running with database `agribot`

**Setup**
```bash
# Install dependencies
pip install flask flask-cors flask-sqlalchemy flask-jwt-extended psycopg2-binary

# Configure database (app.py)
# SQLALCHEMY_DATABASE_URI = "postgresql://agribot-admin:1234@localhost:5432/agribot"

# Run
python app.py
# Server starts at http://0.0.0.0:5000
```

Default test credentials (auto-seeded): `guest` / `guest1234`

---

## Architecture

```
React Frontend
    │
    ├─ POST /api/auth/login ──────────────────► JWT token
    │
    └─ All other requests (Bearer token) ────► Flask API ──► PostgreSQL


Jetson Device (Robot)
    │
    ├─ POST /api/predictions ────────────────► Store image + update active Run
    │
    └─ GET  /api/get-commands/{device_id} ───► Fetch next movement command
```

---

## Project Structure

```
Agribot-FlaskBackend/
├── app.py          # App init, config, entry point
├── api.py          # All models and API endpoints
├── uploads/        # Detection images
└── docs/
    ├── API_REFERENCE.md
    └── DEVELOPER_REFERENCE.md
```
