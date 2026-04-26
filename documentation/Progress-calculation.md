# Progress Bar Calculation

## Overview

The progress bar shows how far the robot has advanced along the current detection path. It is computed entirely on the frontend using field dimensions, device camera width, and the live `current_steps` count polled from the backend.

---

## Formula

```
forward_distance_cm = field.length × 100   (if partition_type == 'row')
                    = field.width  × 100   (if partition_type == 'column')

total_steps_for_path = round(forward_distance_cm / camera_vision_width_cm)

progress_pct = min(100, round(current_steps / total_steps_for_path × 100))
```

---

## Step-by-step for different field sizes

| Field | Partition type | Camera width | forward_distance_cm | total_steps_for_path | Steps at 100% |
|---|---|---|---|---|---|
| 10 m × 5 m | row | 50 cm | 1000 cm | round(1000/50) = **20** | 20 |
| 10 m × 5 m | column | 50 cm | 500 cm | round(500/50) = **10** | 10 |
| 50 m × 20 m | row | 50 cm | 5000 cm | round(5000/50) = **100** | 100 |
| 50 m × 20 m | column | 50 cm | 2000 cm | round(2000/50) = **40** | 40 |
| 100 m × 30 m | row | 30 cm | 10000 cm | round(10000/30) = **333** | 333 |
| 100 m × 30 m | column | 30 cm | 3000 cm | round(3000/30) = **100** | 100 |

---

## Variables

| Variable | Source | Description |
|---|---|---|
| `partition_type` | `field.partition_type` | `'row'` — robot moves along field length; `'column'` — robot moves along field width |
| `field.length` | Field record (metres) | Physical length of the field |
| `field.width` | Field record (metres) | Physical width of the field |
| `camera_vision_width_cm` | Device record (cm) | Distance covered by one robot step |
| `current_steps` | `GET /detection/status` polled every 2 s | Number of weed detection rows written for the active run |
| `total_steps_for_path` | Computed on frontend | Steps required to traverse one path end-to-end |

---

## Edge cases

| Scenario | Behaviour |
|---|---|
| `camera_vision_width_cm` is 0 or not set | `total_steps_for_path = 0` → `progress_pct = 0` (bar stays empty) |
| `current_steps` exceeds `total_steps_for_path` | `min(100, ...)` clamps progress to 100% |
| Detection stopped before completion | Polling stops; progress bar freezes at the last polled value |
| Field not selected | `forwardDistanceCm = 0` → `total_steps_for_path = 0` → bar stays empty |
