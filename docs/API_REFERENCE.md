# AgriBot Backend — API Reference

> **Base URL:** `http://localhost:5000` (configurable via `VITE_API_BASE_URL` on the frontend)
>
> **Authentication:** All endpoints except login require a Bearer token in the `Authorization` header.
> ```
> Authorization: Bearer <access_token>
> ```
> Obtain a token from `POST /api/auth/login`.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Fields](#2-fields)
3. [Devices](#3-devices)
4. [Device Settings](#4-device-settings)
5. [Dashboard](#5-dashboard)
6. [Runs / Analytics](#6-runs--analytics)
7. [Device Control — Detection](#7-device-control--detection)
8. [Device Control — Manual Movement](#8-device-control--manual-movement)
9. [Routes](#9-routes)
10. [Jetson Device Endpoints](#10-jetson-device-endpoints)
11. [Error Responses](#11-error-responses)
12. [Data Models](#12-data-models)

---

## 1. Authentication

### POST `/api/auth/login`

Authenticate a user and receive a JWT access token.

**Auth required:** No

**Request body:**
```json
{
  "username": "guest",
  "password": "guest1234"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGci..."
}
```

**Response `401`:**
```json
{ "message": "Bad username or password" }
```

---

### POST `/api/auth/logout`

Invalidate the current session. The client must discard the stored token.

**Auth required:** Yes

**Response `200`:**
```json
{ "message": "Logged out successfully" }
```

---

### GET `/api/auth/me`

Return the profile of the currently authenticated user.

**Auth required:** Yes

**Response `200`:**
```json
{
  "id": 1,
  "username": "guest"
}
```

---

## 2. Fields

### GET `/api/fields`

List all fields.

**Auth required:** Yes

**Response `200`:**
```json
[
  {
    "id": 1,
    "name": "North Paddock",
    "width": 10,
    "height": 8,
    "partition_type": "grid",
    "partition_count": 80,
    "created_at": "2024-01-01T00:00:00+00:00"
  }
]
```

---

### POST `/api/fields`

Create a new field.

**Auth required:** Yes

**Request body:**
```json
{
  "name": "North Paddock",
  "width": 10,
  "height": 8,
  "partition_type": "grid",
  "partition_count": 80
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Field name |
| `width` | integer | Yes | Grid width (columns) |
| `height` | integer | Yes | Grid height (rows) |
| `partition_type` | string | No | Default: `"grid"` |
| `partition_count` | integer | No | Default: `width × height` |

**Response `201`:** Field object (same shape as GET list item)

**Response `400`:**
```json
{ "message": "name, width, and height are required" }
```

---

### PUT `/api/fields/{id}`

Update an existing field.

**Auth required:** Yes

**Request body:** Any subset of the field properties (`name`, `width`, `height`, `partition_type`, `partition_count`).

**Response `200`:** Updated field object

**Response `404`:**
```json
{ "message": "Field not found" }
```

---

### DELETE `/api/fields/{id}`

Delete a field.

**Auth required:** Yes

**Response `200`:**
```json
{ "message": "Field deleted" }
```

**Response `404`:**
```json
{ "message": "Field not found" }
```

---

## 3. Devices

### GET `/api/devices`

List all registered devices.

**Auth required:** Yes

**Response `200`:**
```json
[
  {
    "id": 1,
    "name": "AgriBot-01",
    "device_id": "AB01",
    "server_url": "http://192.168.1.10",
    "status": "online",
    "working": false,
    "created_at": "2024-01-01T00:00:00+00:00"
  }
]
```

---

### GET `/api/devices/{id}`

Get a single device including its configuration settings.

**Auth required:** Yes

**Response `200`:**
```json
{
  "id": 1,
  "name": "AgriBot-01",
  "device_id": "AB01",
  "server_url": "http://192.168.1.10",
  "status": "online",
  "working": false,
  "created_at": "2024-01-01T00:00:00+00:00",
  "serial_port": "/dev/ttyUSB0",
  "serial_baud_rate": 115200,
  "camera_index": 0,
  "confidence_threshold": 0.75
}
```

**Response `404`:**
```json
{ "message": "Device not found" }
```

---

### GET `/api/devices/check-name`

Check whether a device name is available before registering.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Device name to check |

**Response `200`:**
```json
{ "available": true }
```

---

### POST `/api/devices`

Register a new device.

**Auth required:** Yes

**Request body:**
```json
{
  "name": "AgriBot-02",
  "device_id": "AB02",
  "server_url": "http://192.168.1.11",
  "serial_port": "/dev/ttyUSB0",
  "serial_baud_rate": 115200,
  "camera_index": 0,
  "confidence_threshold": 0.75
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique human-readable name |
| `device_id` | string | Yes | Unique device identifier (e.g. `"AB02"`) |
| `server_url` | string | No | Device HTTP address |
| `serial_port` | string | No | Serial port path |
| `serial_baud_rate` | integer | No | Default: `115200` |
| `camera_index` | integer | No | Default: `0` |
| `confidence_threshold` | float | No | Default: `0.75` |

**Response `201`:** Full device object (same as GET single device)

**Response `409`:**
```json
{ "message": "Device name already exists" }
```

---

### DELETE `/api/devices/{id}`

Delete a device.

**Auth required:** Yes

**Response `200`:**
```json
{ "message": "Device deleted" }
```

---

### GET `/api/devices/{id}/ping`

Check connectivity to the device by attempting an HTTP request to its `server_url`. Updates `status` to `"online"` or `"offline"` in the database.

**Auth required:** Yes

**Response `200`:**
```json
{
  "status": "online",
  "reachable": true
}
```

---

## 4. Device Settings

### GET `/api/devices/{id}/settings`

Fetch the current configuration for a device.

**Auth required:** Yes

**Response `200`:**
```json
{
  "server_url": "http://192.168.1.10",
  "serial_port": "/dev/ttyUSB0",
  "serial_baud_rate": 115200,
  "camera_index": 0,
  "confidence_threshold": 0.75
}
```

---

### PUT `/api/devices/{id}/settings`

Push updated configuration to a device.

**Auth required:** Yes

**Request body:** Any subset of the settings fields (`server_url`, `serial_port`, `serial_baud_rate`, `camera_index`, `confidence_threshold`).

**Response `200`:** Updated settings object (same shape as GET)

---

## 5. Dashboard

All dashboard endpoints accept an optional `field_id` query parameter to scope results to a single field.

---

### GET `/api/dashboard/metrics`

Aggregate statistics for the top metrics bar.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `field_id` | integer | No | Scope metrics to a specific field |

**Response `200`:**
```json
{
  "total_weeds": 245,
  "total_runs": 18,
  "active_devices": 1,
  "total_devices": 2
}
```

---

### GET `/api/dashboard/runs-chart`

Time-series run data for the weed trend line chart.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `field_id` | integer | No | Scope to a specific field |
| `period` | string | No | Time window, e.g. `"30d"`. Default: `"30d"` |

**Response `200`:**
```json
[
  { "date": "2024-01-01", "runs": 2 },
  { "date": "2024-01-02", "runs": 1 }
]
```

---

### GET `/api/dashboard/species-breakdown`

Species weed count breakdown for a run.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `field_id` | integer | No | Scope to a specific field |
| `run_id` | integer \| `"latest"` | No | Specific run or `"latest"` (default) |

**Response `200`:**
```json
[
  { "species": "Dandelion", "count": 120 },
  { "species": "Thistle",   "count": 80  }
]
```

---

### GET `/api/dashboard/density-map`

2-D weed density grid for a run.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `field_id` | integer | No | Scope to a specific field |
| `run_id` | integer \| `"latest"` | No | Specific run or `"latest"` (default) |

**Response `200`:** 2-D array where each value is the weed count for that grid cell.
```json
[[0, 1, 2], [1, 0, 3], [2, 1, 0]]
```

---

## 6. Runs / Analytics

### GET `/api/runs`

Paginated list of all detection runs with optional filters.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | No | Filter by device string ID (e.g. `"AB01"`) |
| `field_id` | integer | No | Filter by field |
| `month` | string | No | Filter by month in `YYYY-MM` format |
| `page` | integer | No | Page number. Default: `1` |
| `limit` | integer | No | Items per page. Default: `8` |

**Response `200`:**
```json
{
  "total": 42,
  "runs": [
    {
      "id": 1,
      "device_id": "AB01",
      "field_id": 1,
      "mode": "grid",
      "started_at": "2024-01-01T09:00:00+00:00",
      "finished_at": "2024-01-01T09:45:00+00:00",
      "total_weeds": 50
    }
  ]
}
```

---

### GET `/api/runs/{runId}`

Fetch metadata for a single run.

**Auth required:** Yes

**Response `200`:** Single run object (same shape as list item)

**Response `404`:**
```json
{ "message": "Run not found" }
```

---

### GET `/api/runs/{runId}/density-map`

2-D weed density grid for a specific run.

**Auth required:** Yes

**Response `200`:**
```json
[[0, 1, 2], [1, 0, 3]]
```

---

### GET `/api/runs/{runId}/species`

Species breakdown for a specific run.

**Auth required:** Yes

**Response `200`:**
```json
[
  { "species": "Dandelion", "count": 30 },
  { "species": "Thistle",   "count": 20 }
]
```

---

### GET `/api/runs/{runId}/device-summary`

Device performance stats for a specific run.

**Auth required:** Yes

**Response `200`:**
```json
{
  "device_id": "AB01",
  "connectivity": "good",
  "total_weeds": 50,
  "total_photos": 120,
  "run_time": "00:45:00"
}
```

---

### GET `/api/runs/{runId}/detection-logs`

Paginated list of individual weed detection events for a run.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `page` | integer | No | Default: `1` |
| `limit` | integer | No | Default: `10` |

**Response `200`:**
```json
{
  "total": 120,
  "logs": [
    {
      "id": 1,
      "timestamp": "2024-01-01T09:05:00+00:00",
      "species": "Dandelion",
      "confidence": 0.95,
      "cell": "1,2",
      "photo_url": "/uploads/AB01_weed_001.jpg"
    }
  ]
}
```

---

## 7. Device Control — Detection

### POST `/api/devices/{id}/detection/start`

Start a detection run on a device.

**Auth required:** Yes

**Request body — Grid mode:**
```json
{
  "mode": "grid",
  "field_id": 1,
  "grid_x": 5,
  "grid_y": 4,
  "distance": 100
}
```

**Request body — Route mode:**
```json
{
  "mode": "route",
  "field_id": 1,
  "route_id": 3
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `"grid"` \| `"route"` | Yes | Detection mode |
| `field_id` | integer | No | Associated field |
| `grid_x` | integer | Grid mode | Number of columns |
| `grid_y` | integer | Grid mode | Number of rows |
| `distance` | integer | Grid mode | Cell distance in cm |
| `route_id` | integer | Route mode | ID of a saved route |

**Response `201`:**
```json
{ "message": "Detection started", "run_id": 7 }
```

**Response `409`:**
```json
{ "message": "Device is already running a detection" }
```

---

### POST `/api/devices/{id}/detection/stop`

Stop the active detection run on a device.

**Auth required:** Yes

**Response `200`:**
```json
{ "message": "Detection stopped", "run_id": 7 }
```

**Response `404`:**
```json
{ "message": "No active run found for this device" }
```

---

### GET `/api/devices/{id}/detection/status`

Poll the current run progress. Polled every **2 s** by the frontend during an active run.

**Auth required:** Yes

**Response `200`:**
```json
{
  "cells_total": 20,
  "cells_scanned": 7,
  "weeds_found": 12,
  "device_position": null,
  "status": "running",
  "finished_at": null,
  "stopped_at": null
}
```

`status` values: `"running"` | `"finished"` | `"stopped"`

---

### GET `/api/devices/{id}/detection/grid`

Live detection grid state. Polled every **3.5 s** by the frontend during an active run.

**Auth required:** Yes

**Response `200`:** 2-D array of weed counts per cell. Unscanned cells have value `0`.
```json
[[0, 1, 0], [2, 0, 1], [0, 0, 3]]
```

---

## 8. Device Control — Manual Movement

### POST `/api/devices/{id}/move`

Send a single move command to a device. The command is queued and picked up by the Jetson device via `GET /api/get-commands/{device_id}`.

**Auth required:** Yes

**Request body:**
```json
{
  "command": "forward",
  "value": 50
}
```

| `command` | `value` unit |
|-----------|-------------|
| `forward` | centimetres |
| `backward` | centimetres |
| `left` | degrees |
| `right` | degrees |
| `stop` | — (value ignored) |

**Response `201`:**
```json
{ "message": "Move command queued", "command_id": 12 }
```

**Response `400`:**
```json
{ "message": "Invalid command. Valid values: ['forward', 'backward', 'left', 'right', 'stop']" }
```

---

## 9. Routes

### GET `/api/routes`

List all saved routes, optionally filtered by device.

**Auth required:** Yes

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | integer | No | Filter by device DB id |

**Response `200`:**
```json
[
  {
    "id": 1,
    "name": "Perimeter Sweep",
    "device_id": 1,
    "instructions": [
      { "command": "forward", "value": 200 },
      { "command": "left",    "value": 90  },
      { "command": "forward", "value": 200 }
    ],
    "created_at": "2024-01-01T00:00:00+00:00"
  }
]
```

---

### GET `/api/routes/{id}`

Get a single route.

**Auth required:** Yes

**Response `200`:** Single route object (same shape as list item)

**Response `404`:**
```json
{ "message": "Route not found" }
```

---

### POST `/api/routes`

Create a new route.

**Auth required:** Yes

**Request body:**
```json
{
  "name": "Perimeter Sweep",
  "device_id": 1,
  "instructions": [
    { "command": "forward", "value": 200 },
    { "command": "left",    "value": 90  },
    { "command": "forward", "value": 200 }
  ]
}
```

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `device_id` | integer | Yes |
| `instructions` | array | No |

**Response `201`:** Created route object

---

### PUT `/api/routes/{id}`

Update a route's name or instructions.

**Auth required:** Yes

**Request body:** Any subset of `name`, `instructions`.

**Response `200`:** Updated route object

---

### DELETE `/api/routes/{id}`

Delete a route.

**Auth required:** Yes

**Response `200`:**
```json
{ "message": "Route deleted" }
```

---

## 10. Jetson Device Endpoints

These endpoints are used by the Jetson Nano device, not the React frontend.

---

### POST `/api/login` *(legacy)*

Identical to `POST /api/auth/login`. Kept for backward compatibility with existing Jetson firmware.

---

### POST `/api/predictions`

Submit a weed detection result including images. Automatically updates the active run's weed count, photos count, grid state, and creates a detection log entry.

**Auth required:** Yes (JWT)

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deviceID` | string | Yes | Device string ID (e.g. `"AB01"`) |
| `timestamp` | string | Yes | ISO 8601 datetime |
| `position_in_field` | string | Yes | Cell position in `"row,col"` format (e.g. `"2,3"`) |
| `prediction_text` | string | Yes | Detected species name |
| `original_image` | file | Yes | Original photo |
| `annotated_image` | file | Yes | Annotated photo with detection overlay |

**Response `201`:**
```json
{ "message": "Prediction record stored successfully", "id": 42 }
```

---

### GET `/api/get-commands/{device_id}`

Poll for the next pending move command. Returns and marks the oldest pending command as executed.

**Auth required:** Yes

**Path params:**

| Param | Description |
|-------|-------------|
| `device_id` | Device string ID (e.g. `"AB01"`) |

**Response `200` — command available:**
```json
{
  "message": "Command retrieved",
  "command": {
    "id": 5,
    "command_value": 0,
    "timestamp": "2024-01-01T09:00:00+00:00"
  }
}
```

**Command value mapping:**

| Value | Action |
|-------|--------|
| `0` | Forward |
| `1` | Backward |
| `2` | Right |
| `3` | Left |
| `4` | Stop |

**Response `200` — no pending commands:**
```json
{ "message": "No pending commands", "command": null }
```

---

### POST `/api/send-command` *(legacy)*

Queue a command using the legacy integer-based format. Prefer `POST /api/devices/{id}/move` for new integrations.

**Auth required:** Yes

**Request body:**
```json
{ "deviceID": "AB01", "command_value": 0 }
```

**Response `201`:**
```json
{ "message": "Command queued successfully", "command_id": 5 }
```

---

## 11. Error Responses

All error responses return JSON with a `message` field.

| Status | Meaning |
|--------|---------|
| `400` | Bad request — missing or invalid parameters |
| `401` | Unauthorized — missing or invalid token |
| `404` | Resource not found |
| `409` | Conflict — duplicate name or device already running |

```json
{ "message": "Human-readable error description" }
```

---

## 12. Data Models

### Field
```json
{
  "id": 1,
  "name": "North Paddock",
  "width": 10,
  "height": 8,
  "partition_type": "grid",
  "partition_count": 80,
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

### Device
```json
{
  "id": 1,
  "name": "AgriBot-01",
  "device_id": "AB01",
  "server_url": "http://192.168.1.10",
  "serial_port": "/dev/ttyUSB0",
  "serial_baud_rate": 115200,
  "camera_index": 0,
  "confidence_threshold": 0.75,
  "status": "online",
  "working": false,
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

### Run
```json
{
  "id": 1,
  "device_id": "AB01",
  "field_id": 1,
  "mode": "grid",
  "started_at": "2024-01-01T09:00:00+00:00",
  "finished_at": "2024-01-01T09:45:00+00:00",
  "total_weeds": 50
}
```

### Detection Log Entry
```json
{
  "id": 1,
  "timestamp": "2024-01-01T09:05:00+00:00",
  "species": "Dandelion",
  "confidence": 0.95,
  "cell": "1,2",
  "photo_url": "/uploads/AB01_weed_001.jpg"
}
```

### Route
```json
{
  "id": 1,
  "name": "Perimeter Sweep",
  "device_id": 1,
  "instructions": [
    { "command": "forward", "value": 200 },
    { "command": "left",    "value": 90  },
    { "command": "forward", "value": 200 }
  ],
  "created_at": "2024-01-01T00:00:00+00:00"
}
```
