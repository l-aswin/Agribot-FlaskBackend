import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

# Initialize extensions (they will be bound to the app in main.py)
db = SQLAlchemy()
jwt = JWTManager()

# Create a Blueprint for our API routes
api_bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Database Models
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class Field(db.Model):
    __tablename__ = 'fields'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    partition_type = db.Column(db.String(50), default='grid')
    partition_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'width': self.width,
            'height': self.height,
            'partition_type': self.partition_type,
            'partition_count': self.partition_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    device_id = db.Column(db.String(50), unique=True, nullable=False)
    server_url = db.Column(db.String(255))
    serial_port = db.Column(db.String(100))
    serial_baud_rate = db.Column(db.Integer, default=115200)
    camera_index = db.Column(db.Integer, default=0)
    confidence_threshold = db.Column(db.Float, default=0.75)
    status = db.Column(db.String(20), default='offline')   # online | offline
    working = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self, include_settings=False):
        d = {
            'id': self.id,
            'name': self.name,
            'device_id': self.device_id,
            'server_url': self.server_url,
            'status': self.status,
            'working': self.working,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_settings:
            d.update({
                'serial_port': self.serial_port,
                'serial_baud_rate': self.serial_baud_rate,
                'camera_index': self.camera_index,
                'confidence_threshold': self.confidence_threshold,
            })
        return d

    def settings_dict(self):
        return {
            'server_url': self.server_url,
            'serial_port': self.serial_port,
            'serial_baud_rate': self.serial_baud_rate,
            'camera_index': self.camera_index,
            'confidence_threshold': self.confidence_threshold,
        }


class Route(db.Model):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    instructions_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'device_id': self.device_id,
            'instructions': json.loads(self.instructions_json or '[]'),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Run(db.Model):
    __tablename__ = 'runs'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)   # device_id string (AB01)
    device_db_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'))
    mode = db.Column(db.String(20), default='grid')        # grid | route
    status = db.Column(db.String(20), default='running')   # running | finished | stopped
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime(timezone=True))
    stopped_at = db.Column(db.DateTime(timezone=True))
    total_weeds = db.Column(db.Integer, default=0)
    total_photos = db.Column(db.Integer, default=0)
    # Grid detection metadata
    grid_x = db.Column(db.Integer, default=0)
    grid_y = db.Column(db.Integer, default=0)
    grid_distance = db.Column(db.Integer, default=0)
    cells_scanned = db.Column(db.Integer, default=0)
    grid_state_json = db.Column(db.Text)   # JSON 2D array of weed counts

    def cells_total(self):
        return self.grid_x * self.grid_y

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'field_id': self.field_id,
            'mode': self.mode,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'total_weeds': self.total_weeds,
        }

    def _init_grid(self):
        """Initialise an empty grid if not set."""
        if not self.grid_state_json and self.grid_x and self.grid_y:
            self.grid_state_json = json.dumps(
                [[0] * self.grid_x for _ in range(self.grid_y)]
            )

    def get_grid(self):
        if not self.grid_state_json:
            self._init_grid()
        return json.loads(self.grid_state_json or '[]')

    def set_grid(self, grid):
        self.grid_state_json = json.dumps(grid)


class DetectionLog(db.Model):
    __tablename__ = 'detection_logs'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    species = db.Column(db.String(100))
    confidence = db.Column(db.Float, default=0.0)
    cell = db.Column(db.String(20))           # e.g. "A3" or "1,2"
    photo_url = db.Column(db.String(255))

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'species': self.species,
            'confidence': self.confidence,
            'cell': self.cell,
            'photo_url': self.photo_url,
        }


# Legacy models kept for Jetson-facing endpoints
class DeviceCommand(db.Model):
    __tablename__ = 'device_commands'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)
    command_value = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PredictionRecord(db.Model):
    __tablename__ = 'predictionbs_history'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    position_in_field = db.Column(db.String(100), nullable=False)
    prediction_text = db.Column(db.Text, nullable=False)
    original_image_path = db.Column(db.String(255), nullable=False)
    annotated_image_path = db.Column(db.String(255), nullable=False)


class CommandQueue(db.Model):
    __tablename__ = 'command_queue'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)
    command_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_device_or_404(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return None, jsonify({'message': 'Device not found'}), 404
    return device, None, None


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
    height = data.get('height')
    if not name or width is None or height is None:
        return jsonify({'message': 'name, width, and height are required'}), 400
    field = Field(
        name=name,
        width=int(width),
        height=int(height),
        partition_type=data.get('partition_type', 'grid'),
        partition_count=data.get('partition_count', int(width) * int(height)),
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
    for attr in ('name', 'width', 'height', 'partition_type', 'partition_count'):
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
        server_url=data.get('server_url'),
        serial_port=data.get('serial_port'),
        serial_baud_rate=data.get('serial_baud_rate', 115200),
        camera_index=data.get('camera_index', 0),
        confidence_threshold=data.get('confidence_threshold', 0.75),
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
    for attr in ('server_url', 'serial_port', 'serial_baud_rate', 'camera_index', 'confidence_threshold'):
        if attr in data:
            setattr(device, attr, data[attr])
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
    return jsonify(run.get_grid()), 200


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
    return jsonify(run.get_grid()), 200


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
    q = DetectionLog.query.filter_by(run_id=run_id).order_by(DetectionLog.timestamp.asc())
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

    db.session.add(run)
    device.working = True
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
        return jsonify({'message': 'No active run found for this device'}), 404
    run.status = 'stopped'
    run.stopped_at = datetime.now(timezone.utc)
    device.working = False
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
