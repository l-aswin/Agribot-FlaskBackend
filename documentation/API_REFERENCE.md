# AgriBot Backend — API Reference

> **Base URL:** `http://localhost:5000` (configurable via `VITE_API_BASE_URL` on the frontend)
>
> **Authentication:** All endpoints except login and the IoT device endpoints require a Bearer token in the `Authorization` header.
> ```
> Authorization: Bearer <access_token>
> ```
> Obtain a token from `POST /api/auth/login`.
>
> IoT device endpoints (under `/api/iot_device/`) authenticate using `device_id` and `device_secret` in the request body or query parameters — no JWT required.

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
9. [Device Control — Pending Upload](#9-device-control--pending-upload)
10. [Media Files](#10-media-files)
11. [Routes](#11-routes)
12. [IoT Device Endpoints](#12-iot-device-endpoints)
13. [Legacy Endpoints](#13-legacy-endpoints)
14. [Error Responses](#14-error-responses)
15. [Data Models](#15-data-models)

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
    "length": 8,
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
  "length": 8,
  "partition_type": "grid",
  "partition_count": 80
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Field name |
| `width` | integer | Yes | Grid width (columns) |
| `length` | integer | Yes | Grid length (rows) |
| `partition_type` | string | No | Default: `"grid"` |
| `partition_count` | integer | No | Default: `width × length` |

**Response `201`:** Field object (same shape as GET list item)

**Response `400`:**
```json
{ "message": "name, width, and length are required" }
```

---

### PUT `/api/fields/{id}`

Update an existing field.

**Auth required:** Yes

**Request body:** Any subset of the field properties (`name`, `width`, `length`, `partition_type`, `partition_count`).

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
    "state": "idle",
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
  "confidence_threshold": 0.75,
  "camera_vision_width_cm": 50
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
  "device_secret": "my-secret",
  "server_url": "http://192.168.1.11",
  "serial_port": "/dev/ttyUSB0",
  "serial_baud_rate": 115200,
  "camera_index": 0,
  "confidence_threshold": 0.75,
  "camera_vision_width_cm": 50
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique human-readable name |
| `device_id` | string | Yes | Unique device identifier matching the edge device's `config.json` |
| `device_secret` | string | Yes | Secret matching the edge device's `config.json` |
| `server_url` | string | No | Device HTTP address |
| `serial_port` | string | No | Serial port path |
| `serial_baud_rate` | integer | No | Default: `115200` |
| `camera_index` | integer | No | Default: `0` |
| `confidence_threshold` | float | No | Default: `0.75` |
| `camera_vision_width_cm` | integer | No | Default: `50` |

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
  "confidence_threshold": 0.75,
  "camera_vision_width_cm": 50
}
```

---

### PUT `/api/devices/{id}/settings`

Push updated configuration to a device. If `confidence_threshold` or `camera_vision_width_cm` are included, an `update` command is automatically queued for the edge device to consume on its next poll.

**Auth required:** Yes

**Request body:** Any subset of the settings fields.

| Field | Type | Description |
|-------|------|-------------|
| `server_url` | string | Device HTTP address |
| `serial_port` | string | Serial port path |
| `serial_baud_rate` | integer | Baud rate |
| `camera_index` | integer | Camera device index |
| `confidence_threshold` | float | YOLO confidence threshold `[0.0, 1.0]` |
| `camera_vision_width_cm` | integer | Camera frame ground width in cm |
| `device_secret` | string | Edge device authentication secret |

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
      "run_id": 1,
      "run_number": 3,
      "device_id": "AB01",
      "field_id": 1,
      "field": "North Paddock",
      "mode": "grid",
      "status": "finished",
      "datetime": "2024-01-01T09:00:00+00:00",
      "started_at": "2024-01-01T09:00:00+00:00",
      "finished_at": "2024-01-01T09:45:00+00:00",
      "weeds": 50,
      "total_weeds": 50,
      "duration": "00:45:00"
    }
  ]
}
```

`status` values: `"running"` | `"finished"` | `"stopped"`

---

### GET `/api/runs/{runId}`

Fetch metadata for a single run.

**Auth required:** Yes

**Response `200`:**
```json
{
  "run_id": 1,
  "run_number": 3,
  "device_id": "AB01",
  "field_id": 1,
  "field": "North Paddock",
  "mode": "grid",
  "status": "finished",
  "datetime": "2024-01-01T09:00:00+00:00",
  "started_at": "2024-01-01T09:00:00+00:00",
  "finished_at": "2024-01-01T09:45:00+00:00",
  "weeds": 50,
  "total_weeds": 50,
  "duration": "00:45:00"
}
```

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
      "grid_pos": "1,2",
      "original_url": "/api/media/original/AB01_job7_step1_raw.jpg",
      "annotated_url": "/api/media/annotated/AB01_job7_step1_annotated.jpg",
      "species": "Dandelion",
      "timestamp": "2024-01-01T09:05:00+00:00"
    }
  ]
}
```

---

## 7. Device Control — Detection

### POST `/api/devices/{id}/detection/start`

Start a detection run on a device. Automatically queues a `start` IoT command for the edge device to consume on its next poll.

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
| `mode` | `"grid"` \| `"route"` | Yes | Detection mode (`"grid"` maps to Mode B on the device; `"route"` maps to Mode C) |
| `field_id` | integer | Yes | Associated field |
| `grid_x` | integer | Grid mode | Number of columns |
| `grid_y` | integer | Grid mode | Number of rows |
| `distance` | integer | Grid mode | Cell distance in cm (sent as `travel_distance_cm` to the device) |
| `route_id` | integer | Route mode | ID of a saved route |

**IoT command queued (grid mode):**
```json
{ "command": "start", "payload": { "mode": "B", "job_id": 7, "travel_distance_cm": 100 } }
```

**IoT command queued (route mode):**
```json
{ "command": "start", "payload": { "mode": "C", "job_id": 7, "route_name": "Perimeter Sweep" } }
```

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

Stop the active detection run on a device. Queues a `stop` IoT command for the edge device.

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

Send a single move command to a device. The command is queued in the legacy `DeviceCommand` table.

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

---

## 9. Device Control — Pending Upload

These endpoints queue commands that trigger or cancel the History Data Upload Mode on the edge device (SRS Section 4a).

### POST `/api/devices/{id}/pending-upload/start`

Queue a `start_pending_upload` command for the edge device.

**Auth required:** Yes

**Response `201`:**
```json
{ "message": "start_pending_upload queued" }
```

---

### POST `/api/devices/{id}/pending-upload/stop`

Queue a `stop_pending_upload` command to cancel an in-progress pending upload on the edge device.

**Auth required:** Yes

**Response `201`:**
```json
{ "message": "stop_pending_upload queued" }
```

---

## 10. Media Files

Endpoints that serve stored images. The URLs returned by `GET /api/runs/{runId}/detection-logs` point here.

### GET `/api/media/original/<filename>`

Serve a raw (unprocessed) camera image by filename.

**Auth required:** Yes

**Response `200`:** JPEG image (`image/jpeg`)

**Response `404`:** File not found

---

### GET `/api/media/annotated/<filename>`

Serve an annotated image (bounding boxes overlaid) by filename.

**Auth required:** Yes

**Response `200`:** JPEG image (`image/jpeg`)

**Response `404`:** File not found

---

### POST `/api/media/upload`

Alternative multipart image upload endpoint (mirrors `POST /api/iot_device/upload` but authenticated via JWT rather than device credentials).

**Auth required:** Yes

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | Yes | Device string identifier |
| `job_id` | string | Yes | Run ID this upload belongs to |
| `step_index` | string | Yes | Zero-based step counter |
| `raw_image` | file | Yes | Raw camera photo |
| `annotated_image` | file | Yes | Annotated photo with bounding boxes |
| `detection_json` | file | No | Detection metadata JSON |

**Response `200`:**
```json
{ "message": "Upload received" }
```

---

## 11. Routes

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
      { "type": "forward",    "value": 200 },
      { "type": "turn_left",  "value": 90  },
      { "type": "forward",    "value": 200 }
    ],
    "created_at": "2024-01-01T00:00:00+00:00"
  }
]
```

> **Note:** Route instructions use `type` (`"forward"`, `"turn_left"`, `"turn_right"`) and `value` to match the edge device's expected format (SRS SR-28). The frontend UI may display these as `command`/`value` — ensure the frontend maps them to `type`/`value` before saving.

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
    { "type": "forward",    "value": 200 },
    { "type": "turn_left",  "value": 90  },
    { "type": "forward",    "value": 200 }
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

## 12. IoT Device Endpoints

These endpoints are called by the Jetson Nano edge device. They do **not** require a JWT token. Authentication is performed using `device_id` and `device_secret` in the request body (POST) or query parameters (GET). All paths are under the `/api/iot_device/` prefix, which matches `base_api_url` in the device's `config.json`.

On authentication failure any of these endpoints returns:

**Response `401`:**
```json
{ "message": "Unknown device or wrong secret" }
```

---

### GET `/api/iot_device/devicecheck`

Startup credential verification (SRS SR-09). The device calls this once at boot before entering the polling loop. Returns HTTP 200 if `device_id` and `device_secret` are valid; marks the device `status` as `"online"`.

**Auth required:** No (uses `device_id` + `device_secret` query params)

**Query params:**

| Param | Type | Required |
|-------|------|----------|
| `device_id` | string | Yes |
| `device_secret` | string | Yes |

**Response `200`:**
```json
{ "message": "OK" }
```

---

### POST `/api/iot_device/disconnect`

Device disconnect notification. The device calls this on shutdown to mark itself `"offline"` in the database.

**Auth required:** No (uses body fields)

**Request body:**
```json
{ "device_id": "jetson-nano-01", "device_secret": "..." }
```

**Response `200`:**
```json
{ "message": "OK" }
```

---

### POST `/api/iot_device/command`

Command polling endpoint (SRS SR-13). The device calls this every 2 seconds. Returns the oldest unconsumed IoT command and marks it consumed, or `null` if no command is pending.

**Auth required:** No (uses body fields)

**Request body:**
```json
{ "device_id": "jetson-nano-01", "device_secret": "..." }
```

**Response `200` — command pending:**
```json
{
  "command": "start",
  "payload": {
    "mode": "B",
    "job_id": 7,
    "travel_distance_cm": 500
  }
}
```

**Response `200` — no pending command:**
```json
{ "command": null }
```

**Possible `command` values:**

| Value | Payload | Description |
|-------|---------|-------------|
| `"start"` | `{ mode, job_id, travel_distance_cm }` or `{ mode, job_id, route_name }` | Begin a detection run |
| `"stop"` | _(none)_ | Abort the active run |
| `"update"` | `{ confidence_threshold?, camera_vision_width_cm? }` | Update device settings |
| `"start_pending_upload"` | _(none)_ | Begin uploading files from `pending_uploads_dir` |
| `"stop_pending_upload"` | _(none)_ | Cancel an in-progress pending upload |

---

### POST `/api/iot_device/upload`

Multipart image and detection data upload (SRS SR-38, SR-50). Called after each weed detection iteration and during History Data Upload Mode.

**Auth required:** No (uses form fields)

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_id` | string | Yes | Device identifier |
| `device_secret` | string | Yes | Device secret |
| `job_id` | string | Yes | Run ID this upload belongs to |
| `step_index` | string | Yes | Zero-based step counter for this iteration |
| `raw_image` | file | Yes | Raw camera photo (`{stem}_raw.jpg`) |
| `annotated_image` | file | Yes | Annotated photo with bounding boxes (`{stem}_annotated.jpg`) |
| `detection_json` | file | No | Detection metadata JSON (`{stem}.json`) — contains `detections` array with `label` and `confidence` per object |

**Response `200`:**
```json
{ "message": "Upload received" }
```

---

### POST `/api/iot_device/completed`

Job completion or abort notification (SRS SR-26, SR-31). Called by the device when a Mode B or Mode C run finishes or is aborted.

**Auth required:** No (uses body fields)

**Request body — completed:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "job_id": 7,
  "status": "completed",
  "total_distance_cm": 500
}
```

**Request body — aborted:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "job_id": 7,
  "status": "aborted",
  "reason": "stopped",
  "total_distance_cm": 250
}
```

| Field | Type | Values |
|-------|------|--------|
| `status` | string | `"completed"` \| `"aborted"` |
| `reason` | string | `"timeout"` \| `"err"` \| `"stopped"` (only when `status` is `"aborted"`) |

**Response `200`:**
```json
{ "message": "Completion recorded" }
```

---

### POST `/api/iot_device/settings/status`

Settings update acknowledgement (SRS SR-17). The device calls this after applying (or failing to apply) an `update` command.

**Auth required:** No (uses body fields)

**Request body — success:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "status": "success",
  "applied": ["confidence_threshold"]
}
```

**Request body — partial:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "status": "partial",
  "applied": ["confidence_threshold"],
  "failed": [{ "field": "camera_vision_width_cm", "reason": "wds_active" }]
}
```

**Request body — failed:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "status": "failed",
  "failed": [{ "field": "confidence_threshold", "reason": "validation_error" }]
}
```

| `status` | Meaning |
|----------|---------|
| `"success"` | All fields applied |
| `"partial"` | Some fields applied, some blocked |
| `"failed"` | No fields applied |

`"reason"` values in `failed` entries: `"validation_error"`, `"wds_active"`, `"unrecognised_field"`, `"disk_write_error"`

**Response `200`:**
```json
{ "message": "Settings status received", "status": "success" }
```

---

### POST `/api/iot_device/device/state`

Device state change notification (SRS SR-49, SR-51). Called when the device enters or exits a special mode.

**Auth required:** No (uses body fields)

**Request body:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "state": "pending_upload"
}
```

| `state` | Meaning |
|---------|---------|
| `"idle"` | Device is idle, ready for commands |
| `"working"` | Device is executing a detection job |
| `"pending_upload"` | Device is in History Data Upload Mode |

**Response `200`:**
```json
{ "message": "State updated" }
```

---

### POST `/api/iot_device/history/completed`

History (pending) upload completion summary (SRS SR-51). Called when the device finishes processing all bundles in `pending_uploads_dir`.

**Auth required:** No (uses body fields)

**Request body:**
```json
{
  "device_id": "jetson-nano-01",
  "device_secret": "...",
  "succeeded": 5,
  "failed": 1
}
```

**Response `200`:**
```json
{ "message": "History upload summary received" }
```

---

### GET `/api/iot_device/route`

Fetch route steps by name for Mode C (SRS SR-27a).

**Auth required:** No (uses `device_id` + `device_secret` query params)

**Query params:**

| Param | Type | Required |
|-------|------|----------|
| `device_id` | string | Yes |
| `device_secret` | string | Yes |
| `route_name` | string | Yes |

**Response `200`:**
```json
{
  "steps": [
    { "type": "forward",    "value": 200 },
    { "type": "turn_left",  "value": 90  },
    { "type": "forward",    "value": 200 }
  ]
}
```

**Response `404`:**
```json
{ "message": "Route not found" }
```

---

## 13. Legacy Endpoints

These endpoints are kept for backward compatibility.

### POST `/api/login`

Identical to `POST /api/auth/login`.

---

### POST `/api/predictions`

Submit a weed detection result using the old JWT-authenticated format. Prefer `POST /api/iot_device/upload` for new firmware.

**Auth required:** Yes (JWT)

**Content-Type:** `multipart/form-data`

**Form fields:** `deviceID`, `timestamp` (ISO 8601), `position_in_field` (`"row,col"`), `prediction_text`, `original_image` (file), `annotated_image` (file)

**Response `201`:**
```json
{ "message": "Prediction record stored successfully", "id": 42 }
```

---

### GET `/api/get-commands/{device_id}`

Poll for the next pending move command (legacy integer format). Prefer `POST /api/iot_device/command` for new firmware.

**Auth required:** Yes (JWT)

**Response `200`:**
```json
{
  "message": "Command retrieved",
  "command": { "id": 5, "command_value": 0, "timestamp": "2024-01-01T09:00:00+00:00" }
}
```

Command value mapping: `0` = Forward, `1` = Backward, `2` = Right, `3` = Left, `4` = Stop

---

### POST `/api/send-command`

Queue a command using the legacy integer-based format.

**Auth required:** Yes (JWT)

**Request body:** `{ "deviceID": "AB01", "command_value": 0 }`

---

## 14. Error Responses

All error responses return JSON with a `message` field.

| Status | Meaning |
|--------|---------|
| `400` | Bad request — missing or invalid parameters |
| `401` | Unauthorized — missing/invalid JWT token, or unknown device/wrong secret (IoT endpoints) |
| `404` | Resource not found |
| `409` | Conflict — duplicate name or device already running |

```json
{ "message": "Human-readable error description" }
```

---

## 15. Data Models

### Field
```json
{
  "id": 1,
  "name": "North Paddock",
  "width": 10,
  "length": 8,
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
  "camera_vision_width_cm": 50,
  "status": "online",
  "working": false,
  "state": "idle",
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

### Run
```json
{
  "run_id": 1,
  "run_number": 3,
  "device_id": "AB01",
  "field_id": 1,
  "field": "North Paddock",
  "mode": "grid",
  "status": "finished",
  "datetime": "2024-01-01T09:00:00+00:00",
  "started_at": "2024-01-01T09:00:00+00:00",
  "finished_at": "2024-01-01T09:45:00+00:00",
  "stopped_at": null,
  "weeds": 50,
  "total_weeds": 50,
  "total_photos": 120,
  "duration": "00:45:00"
}
```

`status` values: `"running"` | `"finished"` | `"stopped"`

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
    { "type": "forward",    "value": 200 },
    { "type": "turn_left",  "value": 90  },
    { "type": "forward",    "value": 200 }
  ],
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

### IoT Command (internal)

Stored in the `iot_commands` table. Created by the backend when the frontend triggers a detection start/stop or settings update; consumed by the edge device via `POST /api/iot_device/command`.

```json
{
  "id": 1,
  "device_id": "jetson-nano-01",
  "command": "start",
  "payload": { "mode": "B", "job_id": 7, "travel_distance_cm": 500 },
  "status": "pending",
  "created_at": "2024-01-01T09:00:00+00:00"
}
```
