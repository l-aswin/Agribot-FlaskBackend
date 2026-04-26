# AgriBot REST API Contract

**Version:** 1.0  
**Base URL:** `http://<host>:5000`  
**Dev Proxy:** Vite proxies `/api` → `http://localhost:5000` during development

---

## General Conventions

### Authentication
All endpoints (except `/api/auth/login`) require a Bearer token in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

Token is obtained from `POST /api/auth/login` and stored client-side. On `401` responses, the client clears the token and redirects to login.

### Request Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Error Response Format
```json
{
  "message": "Human-readable error description"
}
```

### HTTP Status Codes
| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (invalid/expired token) |
| 404 | Resource not found |
| 409 | Conflict (e.g. duplicate name) |
| 500 | Internal Server Error |

---

## Authentication

### POST /api/auth/login
Log in and receive an access token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "access_token": "string"
}
```

---

### POST /api/auth/logout
Invalidate the current session token.

**Request Body:** None

**Response `200`:**
```json
{
  "message": "Logged out successfully"
}
```

---

### GET /api/auth/me
Get the currently authenticated user's profile.

**Response `200`:**
```json
{
  "id": "string",
  "username": "string",
  "email": "string"
}
```

---

## Fields

A field represents a physical agricultural plot. It can be divided into partitions.

### Field Object
```json
{
  "id": "string",
  "name": "string",
  "width": "number (meters)",
  "length": "number (meters)",
  "partition_type": "string",
  "partition_count": "number",
  "created_date": "ISO 8601 datetime string"
}
```

---

### GET /api/fields
List all fields.

**Response `200`:** Array of Field objects
```json
[
  {
    "id": "string",
    "name": "string",
    "width": 10,
    "length": 20,
    "partition_type": "grid",
    "partition_count": 4,
    "created_date": "2025-01-01T00:00:00Z"
  }
]
```

---

### POST /api/fields
Create a new field.

**Request Body:**
```json
{
  "name": "string",
  "width": "number",
  "length": "number",
  "partition_type": "string",
  "partition_count": "number"
}
```

**Response `201`:** Created Field object

---

### PUT /api/fields/{id}
Update an existing field.

**Path Params:** `id` — field ID

**Request Body:** Same shape as POST (all fields optional)

**Response `200`:** Updated Field object

---

### DELETE /api/fields/{id}
Delete a field.

**Path Params:** `id` — field ID

**Response `200`:**
```json
{
  "message": "Field deleted successfully"
}
```

---

## Devices

A device is a physical AgriBot robot unit.

### Device Object
```json
{
  "id": "string",
  "name": "string",
  "online": "boolean",
  "status": "string",
  "created_date": "ISO 8601 datetime string",
  "device_id": "string",
  "device_secret": "string",
  "server_url": "string",
  "serial_port": "string",
  "serial_baud_rate": "string",
  "camera_index": "string",
  "confidence_threshold": "string (float as string, e.g. '0.5')",
  "camera_vision_width_cm": "string (number as string)"
}
```

---

### GET /api/devices
List all devices.

**Response `200`:** Array of Device objects

---

### GET /api/devices/{id}
Get a single device by ID.

**Path Params:** `id` — device ID

**Response `200`:** Device object

---

### POST /api/devices
Register a new device.

**Request Body:**
```json
{
  "name": "string",
  "device_id": "string",
  "device_secret": "string",
  "server_url": "string",
  "serial_port": "string",
  "serial_baud_rate": "string",
  "camera_index": "string",
  "confidence_threshold": "string",
  "camera_vision_width_cm": "string"
}
```

**Response `201`:** Created Device object

---

### DELETE /api/devices/{id}
Remove a device.

**Path Params:** `id` — device ID

**Response `200`:**
```json
{
  "message": "Device deleted successfully"
}
```

---

### GET /api/devices/check-name
Check if a device name is available (for duplicate prevention).

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Device name to check |

**Response `200`:**
```json
{
  "available": true
}
```

---

### GET /api/devices/{id}/ping
Ping a device to check connectivity.

**Path Params:** `id` — device ID

**Response `200`:**
```json
{
  "online": true,
  "latency_ms": 42
}
```

---

### GET /api/devices/{id}/settings
Get a device's configuration settings.

**Path Params:** `id` — device ID

**Response `200`:** Device settings object (same fields as Device object configuration properties)

---

### PUT /api/devices/{id}/settings
Update a device's configuration settings.

**Path Params:** `id` — device ID

**Request Body:** Device settings fields to update

**Response `200`:** Updated settings object

---

## Device Control

### POST /api/devices/{id}/move
Send a manual movement command to a device.

**Path Params:** `id` — device ID

**Request Body:**
```json
{
  "command": "forward | backward | left | right | weed",
  "value": "number"
}
```

| Command | Description |
|---------|-------------|
| `forward` | Move forward by `value` units |
| `backward` | Move backward by `value` units |
| `left` | Turn left by `value` degrees |
| `right` | Turn right by `value` degrees |
| `weed` | Trigger weed detection at current position |

**Response `200`:**
```json
{
  "message": "Command sent"
}
```

---

### POST /api/devices/{id}/detection/start
Start a weed detection run on a device.

**Path Params:** `id` — device ID

**Request Body (Grid Mode):**
```json
{
  "field_id": "string",
  "partition_type": "string",
  "mode": "grid",
  "grid_x": "number (columns)",
  "grid_y": "number (rows)",
  "distance": "number (cm per cell)",
  "start_col": "number (0-indexed)",
  "start_row": "number (0-indexed)"
}
```

**Request Body (Route Mode):**
```json
{
  "field_id": "string",
  "partition_type": "string",
  "mode": "route",
  "route_id": "string"
}
```

**Response `200`:**
```json
{
  "message": "Detection started"
}
```

---

### POST /api/devices/{id}/detection/stop
Stop an in-progress detection run.

**Path Params:** `id` — device ID

**Request Body:** None

**Response `200`:**
```json
{
  "message": "Detection stopped"
}
```

---

### GET /api/devices/{id}/detection/status
Get the current detection run status. Polled by client every **2 seconds** while a run is active.

**Path Params:** `id` — device ID

**Response `200`:**
```json
{
  "status": "running | finished | stopped",
  "current_steps": "number",
  "total_steps": "number",
  "total_distance_cm": "number",
  "cells_scanned": "number",
  "weeds_found": "number",
  "finished_at": "ISO 8601 datetime string | null",
  "stopped_at": "ISO 8601 datetime string | null"
}
```

---

### GET /api/devices/{id}/detection/grid
Get the live weed detection grid data. Polled by client every **3.5 seconds** while a run is active.

**Path Params:** `id` — device ID

**Response `200`:** Array of bucket objects representing scanned grid cells
```json
[
  {
    "cell": "number (cell index, 0-indexed)",
    "weed_count": "number",
    "step_count": "number"
  }
]
```

---

## Runs

A run represents a single completed or in-progress weed detection sweep.

### Run Object
```json
{
  "id": "string",
  "run_number": "number",
  "device_id": "string",
  "field": {
    "id": "string",
    "name": "string"
  },
  "datetime": "ISO 8601 datetime string",
  "duration": "number (seconds)",
  "weeds": "number (total weeds detected)"
}
```

---

### GET /api/runs
List runs with optional filters, paginated.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| device_id | string | No | Filter by device |
| field_id | string | No | Filter by field |
| month | string | No | Filter by month (e.g. `2025-01`) |
| page | number | No | Page number (default: 1) |
| limit | number | No | Items per page (default: 20) |

**Response `200`:**
```json
{
  "runs": [ /* array of Run objects */ ],
  "total": "number"
}
```

---

### GET /api/runs/{runId}
Get details for a single run.

**Path Params:** `runId` — run ID

**Response `200`:** Run object

---

### GET /api/runs/{runId}/density-map
Get the weed density grid for a run.

**Path Params:** `runId` — run ID

**Response `200`:** 2D array (rows × columns) of weed counts
```json
[
  [0, 2, 1],
  [3, 0, 4],
  [1, 1, 0]
]
```

---

### GET /api/runs/{runId}/species
Get species breakdown for a run.

**Path Params:** `runId` — run ID

**Response `200`:**
```json
[
  {
    "species": "Crabgrass | Nutsedge | Purslane | Other",
    "count": "number"
  }
]
```

---

### GET /api/runs/{runId}/device-summary
Get device information at the time of the run.

**Path Params:** `runId` — run ID

**Response `200`:**
```json
{
  "device_id": "string",
  "device_name": "string",
  "serial_port": "string",
  "camera_index": "string",
  "confidence_threshold": "string"
}
```

---

### GET /api/runs/{runId}/detection-logs
Get paginated detection log entries for a run.

**Path Params:** `runId` — run ID

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| page | number | No | Page number (default: 1) |
| limit | number | No | Items per page (default: 20) |

**Response `200`:**
```json
{
  "total": "number",
  "logs": [
    {
      "id": "string",
      "timestamp": "ISO 8601 datetime string",
      "species": "string",
      "confidence": "number (0.0–1.0)",
      "cell": "number",
      "image_url": "string | null"
    }
  ]
}
```

---

## Dashboard

### GET /api/dashboard/metrics
Get high-level summary metrics.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| field_id | string | No | Filter by field (empty = all fields) |

**Response `200`:**
```json
{
  "total_weeds": "number | null",
  "total_runs": "number | null",
  "active_devices": "number | null",
  "total_devices": "number | null"
}
```

---

### GET /api/dashboard/species-breakdown
Get species detection breakdown, filtered to the latest run of a field.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| field_id | string | No | Filter by field |
| run_id | string | No | Use `latest` for most recent run |

**Response `200`:**
```json
[
  {
    "species": "string",
    "count": "number"
  }
]
```

---

### GET /api/dashboard/density-map
Get the weed density grid for the latest run of a field.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| field_id | string | No | Filter by field |
| run_id | string | No | Use `latest` for most recent run |

**Response `200`:** 2D array of weed counts (same format as `/api/runs/{runId}/density-map`)

---

### GET /api/dashboard/partition-density
Get per-partition density grids for a field.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| field_id | string | No | Filter by field |

**Response `200`:** Array of 2D grids, one per partition. Partitions with no data return `null`.
```json
[
  [[0, 1], [2, 0]],
  null,
  [[1, 3], [0, 2]]
]
```

---

### GET /api/dashboard/runs-chart
Get time-series data for runs and weed counts chart.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| field_id | string | No | Filter by field |
| period | string | No | Time period (default: `30d`). Examples: `7d`, `30d`, `90d` |

**Response `200`:**
```json
[
  {
    "date": "ISO 8601 date string",
    "weeds": "number",
    "runs": "number"
  }
]
```

---

## Routes

A route is a saved sequence of movement instructions that a device can replay.

### Route Object
```json
{
  "id": "string",
  "name": "string",
  "device_id": "string",
  "instructions": [
    {
      "command": "forward | backward | left | right | weed",
      "value": "number"
    }
  ]
}
```

---

### GET /api/routes
List routes.

**Query Params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| device_id | string | No | Filter by device (empty = all devices) |

**Response `200`:** Array of Route objects

---

### GET /api/routes/{id}
Get a single route.

**Path Params:** `id` — route ID

**Response `200`:** Route object

---

### POST /api/routes
Create a new route.

**Request Body:**
```json
{
  "name": "string",
  "device_id": "string",
  "instructions": [
    {
      "command": "forward | backward | left | right | weed",
      "value": "number"
    }
  ]
}
```

**Response `201`:** Created Route object

---

### PUT /api/routes/{id}
Update a route.

**Path Params:** `id` — route ID

**Request Body:** Route fields to update (same shape as POST)

**Response `200`:** Updated Route object

---

### DELETE /api/routes/{id}
Delete a route.

**Path Params:** `id` — route ID

**Response `200`:**
```json
{
  "message": "Route deleted successfully"
}
```

---

## Polling Summary

These endpoints are called on a polling interval by the frontend during an active detection run:

| Endpoint | Interval | Purpose |
|----------|----------|---------|
| `GET /api/devices/{id}/detection/status` | 2000 ms | Track run progress percentage and status |
| `GET /api/devices/{id}/detection/grid` | 3500 ms | Update live weed density grid |
