import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

from models import (
    db, jwt, User, Field, Device, Route, Run, DetectionLog,
    DeviceCommand, PredictionRecord, CommandQueue, IoTCommand,
    TokenBlocklist, WeedDetection
)

# Create a Blueprint for our API routes
api_bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def downsample_grid(grid, max_cells=3600):
    rows = len(grid)
    if rows == 0:
        return grid
    cols = len(grid[0])
    if rows * cols <= max_cells:
        return grid
    ratio = (max_cells / (rows * cols)) ** 0.5
    target_rows = max(1, int(rows * ratio))
    target_cols = max(1, int(cols * ratio))
    result = [[0] * target_cols for _ in range(target_rows)]
    for r in range(rows):
        tr = r * target_rows // rows
        for c in range(cols):
            result[tr][c * target_cols // cols] += grid[r][c]
    return result


def _get_device_or_404(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return None, jsonify({'message': 'Device not found'}), 404
    return device, None, None


def _auth_iot_device():
    """Authenticate an edge device request using device_id + device_secret.

    Reads from JSON body (POST) or query params (GET).
    Returns (device, None) on success or (None, error_response) on failure.
    """
    if request.method == 'GET':
        device_id = request.args.get('device_id', '')
        device_secret = request.args.get('device_secret', '')
    else:
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id', '')
        device_secret = data.get('device_secret', '')

    device = Device.query.filter_by(device_id=device_id).first()
    if not device or device.device_secret != device_secret:
        return None, (jsonify({'message': 'Unknown device or wrong secret'}), 401)
    return device, None


def _duration_str(started_at, ended_at):
    if not started_at or not ended_at:
        return None
    delta = ended_at - started_at
    total_seconds = int(delta.total_seconds())
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f'{h:02d}:{m:02d}:{s:02d}'


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Login; returns JWT access_token."""
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
        access_token = create_access_token(identity=user.username)
        return jsonify(access_token=access_token), 200
    return jsonify({'message': 'Bad username or password'}), 401


@api_bp.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def auth_logout():
    """Invalidate session (client should discard the token)."""
    return jsonify({'message': 'Logged out successfully'}), 200


@api_bp.route('/api/auth/me', methods=['GET'])
@jwt_required()
def auth_me():
    """Return current user profile."""
    username = get_jwt_identity()
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({'id': user.id, 'username': user.username}), 200


# Legacy login kept for Jetson device compatibility
@api_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
        access_token = create_access_token(identity=user.username)
        return jsonify(access_token=access_token), 200
    return jsonify({'message': 'Bad username or password'}), 401


# ---------------------------------------------------------------------------
# Fields Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/fields', methods=['GET'])
@jwt_required()
def list_fields():
    fields = Field.query.order_by(Field.id).all()
    return jsonify([f.to_dict() for f in fields]), 200


@api_bp.route('/api/fields', methods=['POST'])
@jwt_required()
def create_field():
    data = request.get_json() or {}
    name = data.get('name')
    width = data.get('width')
    length = data.get('length')
    if not name or width is None or length is None:
        return jsonify({'message': 'name, width, and length are required'}), 400
    field = Field(
        name=name,
        width=int(width),
        length=int(length),
        partition_type=data.get('partition_type', 'grid'),
        partition_count=data.get('partition_count', int(width) * int(length)),
    )
    db.session.add(field)
    db.session.commit()
    return jsonify(field.to_dict()), 201


@api_bp.route('/api/fields/<int:field_id>', methods=['PUT'])
@jwt_required()
def update_field(field_id):
    field = db.session.get(Field, field_id)
    if not field:
        return jsonify({'message': 'Field not found'}), 404
    data = request.get_json() or {}
    for attr in ('name', 'width', 'length', 'partition_type', 'partition_count'):
        if attr in data:
            setattr(field, attr, data[attr])
    db.session.commit()
    return jsonify(field.to_dict()), 200


@api_bp.route('/api/fields/<int:field_id>', methods=['DELETE'])
@jwt_required()
def delete_field(field_id):
    field = db.session.get(Field, field_id)
    if not field:
        return jsonify({'message': 'Field not found'}), 404
    db.session.delete(field)
    db.session.commit()
    return jsonify({'message': 'Field deleted'}), 200


# ---------------------------------------------------------------------------
# Devices Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/devices', methods=['GET'])
@jwt_required()
def list_devices():
    devices = Device.query.order_by(Device.id).all()
    return jsonify([d.to_dict() for d in devices]), 200


@api_bp.route('/api/devices/<int:device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    return jsonify(device.to_dict(include_settings=True)), 200


@api_bp.route('/api/devices/check-name', methods=['GET'])
@jwt_required()
def check_device_name():
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'message': 'name query param required'}), 400
    exists = Device.query.filter_by(name=name).first() is not None
    return jsonify({'available': not exists}), 200


@api_bp.route('/api/devices', methods=['POST'])
@jwt_required()
def create_device():
    data = request.get_json() or {}
    name = data.get('name')
    device_id_str = data.get('device_id')
    if not name or not device_id_str:
        return jsonify({'message': 'name and device_id are required'}), 400
    if Device.query.filter_by(name=name).first():
        return jsonify({'message': 'Device name already exists'}), 409
    if Device.query.filter_by(device_id=device_id_str).first():
        return jsonify({'message': 'device_id already exists'}), 409
    device = Device(
        name=name,
        device_id=device_id_str,
        device_secret=data.get('device_secret', ''),
        server_url=data.get('server_url'),
        serial_port=data.get('serial_port'),
        serial_baud_rate=data.get('serial_baud_rate', 115200),
        camera_index=data.get('camera_index', 0),
        confidence_threshold=data.get('confidence_threshold', 0.75),
        camera_vision_width_cm=data.get('camera_vision_width_cm', 50),
    )
    db.session.add(device)
    db.session.commit()
    return jsonify(device.to_dict(include_settings=True)), 201


@api_bp.route('/api/devices/<int:device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    db.session.delete(device)
    db.session.commit()
    return jsonify({'message': 'Device deleted'}), 200


@api_bp.route('/api/devices/<int:device_id>/ping', methods=['GET'])
@jwt_required()
def ping_device(device_id):
    """Connectivity check — marks device online/offline based on reachability."""
    import urllib.request
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    reachable = False
    if device.server_url:
        try:
            urllib.request.urlopen(device.server_url, timeout=3)
            reachable = True
        except Exception:
            reachable = False
    device.status = 'online' if reachable else 'offline'
    db.session.commit()
    return jsonify({'status': device.status, 'reachable': reachable}), 200


# ---------------------------------------------------------------------------
# Device Settings Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/devices/<int:device_id>/settings', methods=['GET'])
@jwt_required()
def get_device_settings(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    return jsonify(device.settings_dict()), 200


@api_bp.route('/api/devices/<int:device_id>/settings', methods=['PUT'])
@jwt_required()
def update_device_settings(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    data = request.get_json() or {}
    for attr in ('server_url', 'serial_port', 'serial_baud_rate', 'camera_index',
                 'confidence_threshold', 'camera_vision_width_cm', 'device_secret'):
        if attr in data:
            setattr(device, attr, data[attr])

    # Queue an update command for the edge device with the remotely-updatable fields
    iot_update_payload = {k: data[k] for k in ('confidence_threshold', 'camera_vision_width_cm') if k in data}
    if iot_update_payload:
        iot_cmd = IoTCommand(
            device_id=device.device_id,
            command='update',
            payload_json=json.dumps(iot_update_payload),
        )
        db.session.add(iot_cmd)

    db.session.commit()
    return jsonify(device.settings_dict()), 200


# ---------------------------------------------------------------------------
# Dashboard Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/dashboard/metrics', methods=['GET'])
@jwt_required()
def dashboard_metrics():
    field_id = request.args.get('field_id', type=int)
    q = Run.query
    if field_id:
        q = q.filter_by(field_id=field_id)
    total_runs = q.count()
    total_weeds = db.session.query(func.sum(Run.total_weeds)).filter(
        Run.field_id == field_id if field_id else True
    ).scalar() or 0
    total_devices = Device.query.count()
    active_devices = Device.query.filter_by(status='online').count()
    return jsonify({
        'total_weeds': int(total_weeds),
        'total_runs': total_runs,
        'active_devices': active_devices,
        'total_devices': total_devices,
    }), 200


@api_bp.route('/api/dashboard/runs-chart', methods=['GET'])
@jwt_required()
def dashboard_runs_chart():
    field_id = request.args.get('field_id', type=int)
    period = request.args.get('period', '30d')
    days = int(period.rstrip('d')) if period.endswith('d') else 30
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = Run.query.filter(Run.started_at >= since)
    if field_id:
        q = q.filter_by(field_id=field_id)
    runs = q.all()
    counts = {}
    for run in runs:
        day = run.started_at.date().isoformat()
        counts[day] = counts.get(day, 0) + 1
    result = [{'date': d, 'runs': c} for d, c in sorted(counts.items())]
    return jsonify(result), 200


@api_bp.route('/api/dashboard/species-breakdown', methods=['GET'])
@jwt_required()
def dashboard_species_breakdown():
    field_id = request.args.get('field_id', type=int)
    run_id_param = request.args.get('run_id', 'latest')
    if run_id_param == 'latest':
        q = Run.query
        if field_id:
            q = q.filter_by(field_id=field_id)
        run = q.order_by(Run.started_at.desc()).first()
        run_id = run.id if run else None
    else:
        run_id = int(run_id_param)
    if not run_id:
        return jsonify([]), 200
    rows = db.session.query(
        DetectionLog.species, func.count(DetectionLog.id).label('count')
    ).filter_by(run_id=run_id).group_by(DetectionLog.species).all()
    return jsonify([{'species': r.species, 'count': r.count} for r in rows]), 200


@api_bp.route('/api/dashboard/density-map', methods=['GET'])
@jwt_required()
def dashboard_density_map():
    field_id = request.args.get('field_id', type=int)
    run_id_param = request.args.get('run_id', 'latest')
    if run_id_param == 'latest':
        q = Run.query
        if field_id:
            q = q.filter_by(field_id=field_id)
        run = q.order_by(Run.started_at.desc()).first()
    else:
        run = db.session.get(Run, int(run_id_param))
    if not run:
        return jsonify([]), 200
    max_cells = request.args.get('max_cells', 3600, type=int)
    return jsonify(downsample_grid(run.get_grid(), max_cells)), 200


@api_bp.route('/api/dashboard/partition-density', methods=['GET'])
@jwt_required()
def dashboard_partition_density():
    field_id = request.args.get('field_id', type=int)
    if not field_id:
        return jsonify({'message': 'field_id is required'}), 400
    field = db.session.get(Field, field_id)
    if not field:
        return jsonify({'message': 'Field not found'}), 404

    n = field.partition_count or 0
    use_row = field.partition_type != 'col'

    result = []
    for i in range(n):
        filter_col = Run.start_row if use_row else Run.start_col
        run = (
            Run.query
            .filter_by(field_id=field_id, status='finished')
            .filter(filter_col == i)
            .order_by(Run.started_at.desc())
            .first()
        )
        result.append(run.get_grid() if run else None)

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# Runs / Analytics Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/runs', methods=['GET'])
@jwt_required()
def list_runs():
    device_id = request.args.get('device_id')
    field_id = request.args.get('field_id', type=int)
    month = request.args.get('month')   # format: YYYY-MM
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 8, type=int)

    q = Run.query
    if device_id:
        q = q.filter_by(device_id=device_id)
    if field_id:
        q = q.filter_by(field_id=field_id)
    if month:
        try:
            year, mon = map(int, month.split('-'))
            start = datetime(year, mon, 1, tzinfo=timezone.utc)
            if mon == 12:
                end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(year, mon + 1, 1, tzinfo=timezone.utc)
            q = q.filter(Run.started_at >= start, Run.started_at < end)
        except ValueError:
            return jsonify({'message': 'month must be YYYY-MM format'}), 400

    total = q.count()
    runs = q.order_by(Run.started_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return jsonify({'total': total, 'runs': [r.to_dict() for r in runs]}), 200


@api_bp.route('/api/runs/<int:run_id>', methods=['GET'])
@jwt_required()
def get_run(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    return jsonify(run.to_dict()), 200


@api_bp.route('/api/runs/<int:run_id>/density-map', methods=['GET'])
@jwt_required()
def run_density_map(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    max_cells = request.args.get('max_cells', 3600, type=int)
    return jsonify(downsample_grid(run.get_grid(), max_cells)), 200


@api_bp.route('/api/runs/<int:run_id>/species', methods=['GET'])
@jwt_required()
def run_species(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    rows = db.session.query(
        DetectionLog.species, func.count(DetectionLog.id).label('count')
    ).filter_by(run_id=run_id).group_by(DetectionLog.species).all()
    return jsonify([{'species': r.species, 'count': r.count} for r in rows]), 200


@api_bp.route('/api/runs/<int:run_id>/device-summary', methods=['GET'])
@jwt_required()
def run_device_summary(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    ended = run.finished_at or run.stopped_at
    return jsonify({
        'device_id': run.device_id,
        'connectivity': 'good',
        'total_weeds': run.total_weeds,
        'total_photos': run.total_photos,
        'run_time': _duration_str(run.started_at, ended),
    }), 200


@api_bp.route('/api/runs/<int:run_id>/detection-logs', methods=['GET'])
@jwt_required()
def run_detection_logs(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    # Per DEVELOPER_REFERENCE, this should return richer log data from WeedDetection
    q = WeedDetection.query.filter_by(run_id=run_id).order_by(WeedDetection.detected_at.asc())
    total = q.count()
    logs = q.offset((page - 1) * limit).limit(limit).all()
    return jsonify({'total': total, 'logs': [l.to_dict() for l in logs]}), 200


# ---------------------------------------------------------------------------
# Device Control — Detection Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/devices/<int:device_id>/detection/start', methods=['POST'])
@jwt_required()
def detection_start(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    if device.working:
        return jsonify({'message': 'Device is already running a detection'}), 409

    data = request.get_json() or {}
    mode = data.get('mode', 'grid')
    field_id = data.get('field_id')

    if not field_id:
        return jsonify({'message': 'field_id is required to start detection'}), 400

    run = Run(
        device_id=device.device_id,
        device_db_id=device.id,
        field_id=field_id,
        mode=mode,
        status='running',
    )

    if mode == 'grid':
        grid_x = data.get('grid_x', 5)
        grid_y = data.get('grid_y', 5)
        run.grid_x = grid_x
        run.grid_y = grid_y
        run.grid_distance = data.get('distance', 100)
        run.grid_state_json = json.dumps([[0] * grid_x for _ in range(grid_y)])
    elif mode == 'route':
        route_id = data.get('route_id')
        if not route_id:
            return jsonify({'message': 'route_id is required for route mode'}), 400
        route = db.session.get(Route, route_id)
        if not route:
            return jsonify({'message': 'Route not found'}), 404

    run.start_row = data.get('start_row', 0)
    run.start_col = data.get('start_col', 0)

    db.session.add(run)
    device.working = True
    db.session.flush()   # populate run.id before building the IoT command payload

    if mode == 'grid':
        iot_payload = {
            'mode': 'B',
            'job_id': run.id,
            'travel_distance_cm': run.grid_distance,
        }
    elif mode == 'route':
        route_obj = db.session.get(Route, data.get('route_id'))
        iot_payload = {
            'mode': 'C',
            'job_id': run.id,
            'route_name': route_obj.name if route_obj else '',
        }
    else:
        iot_payload = {'mode': mode, 'job_id': run.id}

    iot_cmd = IoTCommand(
        device_id=device.device_id,
        command='start',
        payload_json=json.dumps(iot_payload),
    )
    db.session.add(iot_cmd)
    db.session.commit()
    return jsonify({'message': 'Detection started', 'run_id': run.id}), 201


@api_bp.route('/api/devices/<int:device_id>/detection/stop', methods=['POST'])
@jwt_required()
def detection_stop(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    run = Run.query.filter_by(device_db_id=device_id, status='running').order_by(Run.started_at.desc()).first()
    if not run:
        device.working = False
        db.session.commit()
        return jsonify({'message': 'No active run to stop'}), 200
    run.status = 'stopped'
    run.stopped_at = datetime.now(timezone.utc)
    device.working = False
    iot_cmd = IoTCommand(device_id=device.device_id, command='stop', payload_json='{}')
    db.session.add(iot_cmd)
    db.session.commit()
    return jsonify({'message': 'Detection stopped', 'run_id': run.id}), 200


@api_bp.route('/api/devices/<int:device_id>/detection/status', methods=['GET'])
@jwt_required()
def detection_status(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    run = Run.query.filter_by(device_db_id=device_id).order_by(Run.started_at.desc()).first()
    if not run:
        return jsonify({'message': 'No run found for this device'}), 404
    return jsonify({
        'cells_total': run.cells_total(),
        'cells_scanned': run.cells_scanned,
        'weeds_found': run.total_weeds,
        'device_position': None,
        'status': run.status,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        'stopped_at': run.stopped_at.isoformat() if run.stopped_at else None,
    }), 200


@api_bp.route('/api/devices/<int:device_id>/detection/grid', methods=['GET'])
@jwt_required()
def detection_grid(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    run = Run.query.filter_by(device_db_id=device_id).order_by(Run.started_at.desc()).first()
    if not run:
        return jsonify({'message': 'No run found for this device'}), 404
    return jsonify(run.get_grid()), 200


# ---------------------------------------------------------------------------
# Device Control — Manual Movement Endpoint
# ---------------------------------------------------------------------------

@api_bp.route('/api/devices/<int:device_id>/pending-upload/start', methods=['POST'])
@jwt_required()
def pending_upload_start(device_id):
    """Queue a start_pending_upload command for the edge device."""
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    iot_cmd = IoTCommand(device_id=device.device_id, command='start_pending_upload', payload_json='{}')
    db.session.add(iot_cmd)
    db.session.commit()
    return jsonify({'message': 'start_pending_upload queued'}), 201


@api_bp.route('/api/devices/<int:device_id>/pending-upload/stop', methods=['POST'])
@jwt_required()
def pending_upload_stop(device_id):
    """Queue a stop_pending_upload command for the edge device."""
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    iot_cmd = IoTCommand(device_id=device.device_id, command='stop_pending_upload', payload_json='{}')
    db.session.add(iot_cmd)
    db.session.commit()
    return jsonify({'message': 'stop_pending_upload queued'}), 201


@api_bp.route('/api/devices/<int:device_id>/move', methods=['POST'])
@jwt_required()
def device_move(device_id):
    """Send a move command to the device via the command queue."""
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    data = request.get_json() or {}
    command = data.get('command')   # forward | backward | left | right
    value = data.get('value')
    if not command or value is None:
        return jsonify({'message': 'command and value are required'}), 400
    COMMAND_MAP = {'forward': 0, 'backward': 1, 'right': 2, 'left': 3, 'stop': 4}
    if command not in COMMAND_MAP:
        return jsonify({'message': f'Invalid command. Valid values: {list(COMMAND_MAP.keys())}'}), 400
    cmd = DeviceCommand(
        device_id=device.device_id,
        command_value=COMMAND_MAP[command],
        status='pending',
    )
    db.session.add(cmd)
    db.session.commit()
    return jsonify({'message': 'Move command queued', 'command_id': cmd.id}), 201


# ---------------------------------------------------------------------------
# Routes Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/routes', methods=['GET'])
@jwt_required()
def list_routes():
    device_id = request.args.get('device_id', type=int)
    q = Route.query
    if device_id:
        q = q.filter_by(device_id=device_id)
    routes = q.order_by(Route.id).all()
    return jsonify([r.to_dict() for r in routes]), 200


@api_bp.route('/api/routes/<int:route_id>', methods=['GET'])
@jwt_required()
def get_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({'message': 'Route not found'}), 404
    return jsonify(route.to_dict()), 200


@api_bp.route('/api/routes', methods=['POST'])
@jwt_required()
def create_route():
    data = request.get_json() or {}
    name = data.get('name')
    device_id = data.get('device_id')
    instructions = data.get('instructions', [])
    if not name or not device_id:
        return jsonify({'message': 'name and device_id are required'}), 400
    if not db.session.get(Device, device_id):
        return jsonify({'message': 'Device not found'}), 404
    route = Route(name=name, device_id=device_id, instructions_json=json.dumps(instructions))
    db.session.add(route)
    db.session.commit()
    return jsonify(route.to_dict()), 201


@api_bp.route('/api/routes/<int:route_id>', methods=['PUT'])
@jwt_required()
def update_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({'message': 'Route not found'}), 404
    data = request.get_json() or {}
    if 'name' in data:
        route.name = data['name']
    if 'instructions' in data:
        route.instructions_json = json.dumps(data['instructions'])
    db.session.commit()
    return jsonify(route.to_dict()), 200


@api_bp.route('/api/routes/<int:route_id>', methods=['DELETE'])
@jwt_required()
def delete_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({'message': 'Route not found'}), 404
    db.session.delete(route)
    db.session.commit()
    return jsonify({'message': 'Route deleted'}), 200


# ---------------------------------------------------------------------------
# Jetson Device-facing Endpoints (unchanged)
# ---------------------------------------------------------------------------

@api_bp.route('/api/predictions', methods=['POST'])
@jwt_required()
def store_prediction():
    """Stores prediction data and images from a Jetson device."""
    device_id_str = request.form.get('deviceID')
    timestamp_str = request.form.get('timestamp')
    position_in_field = request.form.get('position_in_field')
    prediction_text = request.form.get('prediction_text')

    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid timestamp format. Use ISO format.'}), 400

    if 'original_image' not in request.files or 'annotated_image' not in request.files:
        return jsonify({'message': 'Both original_image and annotated_image files are required'}), 400

    orig_image = request.files['original_image']
    ann_image = request.files['annotated_image']
    orig_filename = secure_filename(orig_image.filename)
    ann_filename = secure_filename(ann_image.filename)
    orig_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f'{device_id_str}_{orig_filename}')
    ann_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f'{device_id_str}_{ann_filename}')
    orig_image.save(orig_path)
    ann_image.save(ann_path)

    new_record = PredictionRecord(
        device_id=device_id_str,
        timestamp=timestamp,
        position_in_field=position_in_field,
        prediction_text=prediction_text,
        original_image_path=orig_path,
        annotated_image_path=ann_path,
    )
    db.session.add(new_record)

    # Update active run if one exists for this device
    device = Device.query.filter_by(device_id=device_id_str).first()
    if device:
        active_run = Run.query.filter_by(device_db_id=device.id, status='running').order_by(Run.started_at.desc()).first()
        if active_run:
            active_run.total_weeds += 1
            active_run.total_photos += 1
            active_run.cells_scanned += 1
            # Add detection log entry
            log = DetectionLog(
                run_id=active_run.id,
                timestamp=timestamp,
                species=prediction_text,
                confidence=1.0,
                cell=position_in_field,
                photo_url=ann_path,
            )
            db.session.add(log)
            # Update grid if cell is in row,col format
            try:
                row, col = map(int, position_in_field.split(','))
                grid = active_run.get_grid()
                if 0 <= row < len(grid) and 0 <= col < len(grid[0]):
                    grid[row][col] += 1
                    active_run.set_grid(grid)
            except (ValueError, AttributeError):
                pass

    db.session.commit()
    return jsonify({'message': 'Prediction record stored successfully', 'id': new_record.id}), 201


@api_bp.route('/api/get-commands/<device_id>', methods=['GET'])
@jwt_required()
def get_pending_commands(device_id):
    """API for the Jetson Nano. Fetches the oldest pending command and marks it executed."""
    pending_cmd = DeviceCommand.query.filter_by(
        device_id=device_id, status='pending'
    ).order_by(DeviceCommand.timestamp.asc()).first()

    if not pending_cmd:
        return jsonify({'message': 'No pending commands', 'command': None}), 200

    pending_cmd.status = 'executed'
    db.session.commit()
    return jsonify({
        'message': 'Command retrieved',
        'command': {
            'id': pending_cmd.id,
            'command_value': pending_cmd.command_value,
            'timestamp': pending_cmd.timestamp.isoformat(),
        },
    }), 200


@api_bp.route('/api/send-command', methods=['POST'])
@jwt_required()
def send_command():
    """Legacy command endpoint for React frontend → Jetson device."""
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON data'}), 400
    device_id = data.get('deviceID')
    command_value = data.get('command_value')
    if not device_id or command_value is None:
        return jsonify({'message': 'deviceID and command_value are required'}), 400
    if command_value not in [0, 1, 2, 3, 4]:
        return jsonify({'message': 'Invalid command value. Must be 0-4.'}), 400
    new_cmd = DeviceCommand(device_id=device_id, command_value=command_value, status='pending')
    db.session.add(new_cmd)
    db.session.commit()
    return jsonify({'message': 'Command queued successfully', 'command_id': new_cmd.id}), 201


# ---------------------------------------------------------------------------
# IoT Device Endpoints  (/api/iot_device/...)
# Auth: device_id + device_secret in request body (POST) or query params (GET)
# ---------------------------------------------------------------------------

@api_bp.route('/api/iot_device/devicecheck', methods=['GET'])
def iot_devicecheck():
    """SR-09: Startup credential verification. Returns 200 if device_id + device_secret are valid."""
    device, err = _auth_iot_device()
    if err:
        return err
    device.status = 'online'
    db.session.commit()
    return jsonify({'message': 'OK'}), 200


@api_bp.route('/api/iot_device/disconnect', methods=['POST'])
def iot_disconnect():
    """Called by edge device on graceful shutdown to mark itself offline."""
    device, err = _auth_iot_device()
    if err:
        return err
    device.status = 'offline'
    device.working = False
    device.state = 'idle'
    db.session.commit()
    return jsonify({'message': 'OK'}), 200


@api_bp.route('/api/iot_device/command', methods=['POST'])
def iot_command_poll():
    """SR-13: Command polling. Returns the next pending IoT command or null."""
    device, err = _auth_iot_device()
    if err:
        return err

    cmd = IoTCommand.query.filter_by(
        device_id=device.device_id, status='pending'
    ).order_by(IoTCommand.created_at.asc()).first()

    if not cmd:
        return jsonify({'command': None}), 200

    cmd.status = 'consumed'
    db.session.commit()

    payload = json.loads(cmd.payload_json or '{}')
    response = {'command': cmd.command}
    if payload:
        response['payload'] = payload
    return jsonify(response), 200


@api_bp.route('/api/iot_device/upload', methods=['POST'])
def iot_upload():
    """SR-38/SR-50: Multipart upload of raw image, annotated image, and detection JSON."""
    device_id_str = request.form.get('device_id', '')
    device_secret = request.form.get('device_secret', '')
    device = Device.query.filter_by(device_id=device_id_str).first()
    if not device or device.device_secret != device_secret:
        current_app.logger.warning(
            'iot_upload: Auth failed for device_id "%s".', device_id_str
        )
        return jsonify({'message': 'Unknown device or wrong secret'}), 401

    job_id = request.form.get('job_id')
    step_index = request.form.get('step_index')
    required_fields = {'job_id': job_id, 'step_index': step_index}
    missing_fields = [k for k, v in required_fields.items() if v is None]
    if missing_fields:
        msg = f"Missing required form field(s): {', '.join(missing_fields)}"
        current_app.logger.warning(
            'iot_upload: Bad request from device "%s". Reason: %s. Form keys: %s',
            device_id_str, msg, list(request.form.keys())
        )
        return jsonify({'message': msg}), 400
    
    # Parse detection data from uploaded JSON file or form field
    detections = []
    if 'detection_json' in request.files:
        try:
            det_data = json.load(request.files['detection_json'])
            detections = det_data.get('detections', [])
        except (json.JSONDecodeError, Exception):
            current_app.logger.warning('iot_upload: Bad request from device "%s". Reason:JSONDecodeError',device_id_str)
            return jsonify({'message': 'Reason:JSONDecodeError'}), 400

    required_files = ['raw_image']
    if detections:
        required_files.append('annotated_image')

    missing_files = [f for f in required_files if f not in request.files]
    if missing_files:
        msg = f"Missing required file(s): {', '.join(missing_files)}"
        current_app.logger.warning(
            'iot_upload: Bad request from device "%s". Reason: %s. File keys: %s',
            device_id_str, msg, list(request.files.keys())
        )
        return jsonify({'message': msg}), 400

    raw_file = request.files['raw_image']
    ann_file = request.files.get('annotated_image')
    stem = f'{device_id_str}_job{job_id}_step{step_index}'
    raw_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f'{stem}_raw.jpg'))
    raw_file.save(raw_path)
    ann_path = None
    if ann_file:
        ann_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f'{stem}_annotated.jpg'))
        ann_file.save(ann_path)

    # Update active run
    run = Run.query.filter_by(id=int(job_id), status='running').first()
    if run:
        run.total_photos += 1
        weed_count = len(detections)
        run.total_weeds += weed_count
        run.cells_scanned += 1

        # Calculate grid position from step_index for grid mode runs
        grid_x, grid_y = None, None
        if run.mode == 'grid' and run.grid_x and run.grid_x > 0:
            try:
                step = int(step_index)
                grid_y = step // run.grid_x
                grid_x = step % run.grid_x
            except (ValueError, TypeError):
                pass  # grid_x/y will remain None

        for det in detections:
            wd = WeedDetection(
                run_id=run.id,
                field_id=run.field_id,
                grid_x=grid_x,
                grid_y=grid_y,
                species=det.get('label', 'weed'),
                original_image_path=raw_path,
                annotated_image_path=ann_path,
            )
            db.session.add(wd)

        if not detections:
            wd = WeedDetection(
                run_id=run.id,
                field_id=run.field_id,
                grid_x=grid_x,
                grid_y=grid_y,
                species='none',
                original_image_path=raw_path,
                annotated_image_path=None,
            )
            db.session.add(wd)

        if run.mode == 'grid' and grid_x is not None and grid_y is not None and weed_count > 0:
            grid = run.get_grid()
            if 0 <= grid_y < len(grid) and 0 <= grid_x < len(grid[0]):
                grid[grid_y][grid_x] += weed_count
                run.set_grid(grid)

        db.session.commit()

    return jsonify({'message': 'Upload received'}), 200


@api_bp.route('/api/iot_device/completed', methods=['POST'])
def iot_completed():
    """SR-26/SR-31: Job completion or abort notification from the device."""
    device, err = _auth_iot_device()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    job_id = data.get('job_id')
    status = data.get('status')   # completed | aborted
    total_distance_cm = data.get('total_distance_cm', 0)
    reason = data.get('reason')   # timeout | err | stopped (only on aborted)

    if not job_id or status not in ('completed', 'aborted'):
        return jsonify({'message': 'job_id and status (completed|aborted) are required'}), 400

    run = db.session.get(Run, int(job_id))
    if not run:
        return jsonify({'message': 'Run not found'}), 404

    now = datetime.now(timezone.utc)
    if status == 'completed':
        run.status = 'finished'
        run.finished_at = now
    else:
        run.status = 'stopped'
        run.stopped_at = now

    run.grid_distance = total_distance_cm
    device.working = False
    device.state = 'idle'
    db.session.commit()

    return jsonify({'message': 'Completion recorded'}), 200


@api_bp.route('/api/iot_device/settings/status', methods=['POST'])
def iot_settings_status():
    """SR-17: Settings update acknowledgement from the device."""
    device, err = _auth_iot_device()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    status = data.get('status')   # success | partial | failed
    applied = data.get('applied', [])
    failed = data.get('failed', [])

    # Apply confirmed settings back to the Device record so the dashboard stays in sync
    if status in ('success', 'partial'):
        if 'confidence_threshold' in applied:
            val = next(
                (v for k, v in data.items() if k == 'confidence_threshold'), None
            )
            # Value not echoed back by device; rely on the device having stored it.
            # Mirror only the fields the device confirmed applied.
            pass
        db.session.commit()

    return jsonify({'message': 'Settings status received', 'status': status}), 200


@api_bp.route('/api/iot_device/device/state', methods=['POST'])
def iot_device_state():
    """SR-49/SR-51: Device state change notification (idle | pending_upload | working)."""
    device, err = _auth_iot_device()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    state = data.get('state')
    if state not in ('idle', 'pending_upload', 'working'):
        return jsonify({'message': 'state must be idle, pending_upload, or working'}), 400

    device.state = state
    if state == 'idle':
        device.working = False
    elif state == 'working':
        device.working = True
    db.session.commit()

    return jsonify({'message': 'State updated'}), 200


@api_bp.route('/api/iot_device/history/completed', methods=['POST'])
def iot_history_completed():
    """SR-51: History (pending) upload completion summary from the device."""
    device, err = _auth_iot_device()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    succeeded = data.get('succeeded', 0)
    failed = data.get('failed', 0)

    # Log the result; the device will follow up with a state:idle notification.
    current_app.logger.info(
        'History upload completed for %s: succeeded=%s failed=%s',
        device.device_id, succeeded, failed,
    )

    return jsonify({'message': 'History upload summary received'}), 200


@api_bp.route('/api/iot_device/route', methods=['GET'])
def iot_get_route():
    """SR-27a: Fetch route steps by route_name for Mode C."""
    device, err = _auth_iot_device()
    if err:
        return err

    route_name = request.args.get('route_name', '').strip()
    if not route_name:
        return jsonify({'message': 'route_name query param is required'}), 400

    route = Route.query.filter_by(name=route_name, device_id=device.id).first()
    if not route:
        return jsonify({'message': 'Route not found'}), 404

    steps = json.loads(route.instructions_json or '[]')
    return jsonify({'steps': steps}), 200
