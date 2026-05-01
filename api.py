import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

from models import (
    db, Device, Route, Run, DetectionLog,
    DeviceCommand, PredictionRecord, IoTCommand, WeedDetection
)

api_bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_iot_device():
    """Authenticate an edge device using device_id + device_secret."""
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


_POLL_TIMEOUT_SECONDS = 5

def _mark_stale_if_needed(device):
    """Set device offline if last command poll was more than _POLL_TIMEOUT_SECONDS ago."""
    if device.last_seen is None:
        return
    age = (datetime.now(timezone.utc) - device.last_seen).total_seconds()
    if age > _POLL_TIMEOUT_SECONDS and device.status == 'online':
        device.status = 'offline'
        db.session.commit()


# ---------------------------------------------------------------------------
# Jetson Legacy Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/api/predictions', methods=['POST'])
@jwt_required()
def store_prediction():
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
    orig_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                             f'{device_id_str}_{secure_filename(orig_image.filename)}')
    ann_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                            f'{device_id_str}_{secure_filename(ann_image.filename)}')
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

    device = Device.query.filter_by(device_id=device_id_str).first()
    if device:
        active_run = Run.query.filter_by(device_db_id=device.id, status='running').order_by(Run.started_at.desc()).first()
        if active_run:
            active_run.total_weeds += 1
            active_run.total_photos += 1
            active_run.cells_scanned += 1
            db.session.add(DetectionLog(
                run_id=active_run.id,
                timestamp=timestamp,
                species=prediction_text,
                confidence=1.0,
                cell=position_in_field,
                photo_url=ann_path,
            ))
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
    device, err = _auth_iot_device()
    if err:
        return err
    _mark_stale_if_needed(device)
    return jsonify({'message': 'OK', 'online': device.status == 'online'}), 200


@api_bp.route('/api/iot_device/disconnect', methods=['POST'])
def iot_disconnect():
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
    device, err = _auth_iot_device()
    if err:
        return err

    device.last_seen = datetime.now(timezone.utc)
    device.status = 'online'
    db.session.commit()

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
    device_id_str = request.form.get('device_id', '')
    device_secret = request.form.get('device_secret', '')
    device = Device.query.filter_by(device_id=device_id_str).first()
    if not device or device.device_secret != device_secret:
        return jsonify({'message': 'Unknown device or wrong secret'}), 401

    job_id = request.form.get('job_id')
    step_index = request.form.get('step_index')
    if not job_id or step_index is None:
        return jsonify({'message': 'job_id and step_index are required'}), 400

    detections = []
    if 'detection_json' in request.files:
        try:
            det_data = json.load(request.files['detection_json'])
            detections = det_data.get('detections', [])
        except (json.JSONDecodeError, Exception):
            return jsonify({'message': 'Invalid detection_json'}), 400

    if 'raw_image' not in request.files:
        return jsonify({'message': 'raw_image is required'}), 400
    if detections and 'annotated_image' not in request.files:
        return jsonify({'message': 'annotated_image is required when detections are present'}), 400

    stem = f'{device_id_str}_job{job_id}_step{step_index}'
    raw_file = request.files['raw_image']
    raw_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f'{stem}_raw.jpg'))
    raw_file.save(raw_path)

    ann_path = None
    if 'annotated_image' in request.files:
        ann_file = request.files['annotated_image']
        ann_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(f'{stem}_annotated.jpg'))
        ann_file.save(ann_path)

    run = Run.query.filter_by(id=int(job_id), status='running').first()
    if run:
        run.total_photos += 1
        run.total_weeds += len(detections)
        run.cells_scanned += 1

        grid_x, grid_y = None, None
        if run.mode == 'grid' and run.grid_x and run.grid_x > 0:
            try:
                step = int(step_index)
                grid_y = step // run.grid_x
                grid_x = step % run.grid_x
            except (ValueError, TypeError):
                pass

        for det in detections:
            db.session.add(WeedDetection(
                run_id=run.id,
                field_id=run.field_id,
                grid_x=grid_x,
                grid_y=grid_y,
                species=det.get('label', 'weed'),
                confidence=det.get('confidence'),
                original_image_path=raw_path,
                annotated_image_path=ann_path,
            ))

        if not detections:
            db.session.add(WeedDetection(
                run_id=run.id,
                field_id=run.field_id,
                grid_x=grid_x,
                grid_y=grid_y,
                species='none',
                count=0,
                original_image_path=raw_path,
            ))

        if run.mode == 'grid' and grid_x is not None and grid_y is not None and detections:
            grid = run.get_grid()
            if 0 <= grid_y < len(grid) and 0 <= grid_x < len(grid[0]):
                grid[grid_y][grid_x] += len(detections)
                run.set_grid(grid)

        db.session.commit()

    return jsonify({'message': 'Upload received'}), 200


@api_bp.route('/api/iot_device/completed', methods=['POST'])
def iot_completed():
    device, err = _auth_iot_device()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    job_id = data.get('job_id')
    status = data.get('status')
    total_distance_cm = data.get('total_distance_cm', 0)

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
    device, err = _auth_iot_device()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    db.session.commit()
    return jsonify({'message': 'Settings status received', 'status': status}), 200


@api_bp.route('/api/iot_device/device/state', methods=['POST'])
def iot_device_state():
    device, err = _auth_iot_device()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    state = data.get('state')
    if state not in ('idle', 'pending_upload', 'working'):
        return jsonify({'message': 'state must be idle, pending_upload, or working'}), 400

    device.state = state
    device.working = (state == 'working')
    db.session.commit()
    return jsonify({'message': 'State updated'}), 200


@api_bp.route('/api/iot_device/history/completed', methods=['POST'])
def iot_history_completed():
    device, err = _auth_iot_device()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    current_app.logger.info(
        'History upload completed for %s: succeeded=%s failed=%s',
        device.device_id, data.get('succeeded', 0), data.get('failed', 0),
    )
    return jsonify({'message': 'History upload summary received'}), 200


@api_bp.route('/api/iot_device/route', methods=['GET'])
def iot_get_route():
    device, err = _auth_iot_device()
    if err:
        return err

    route_name = request.args.get('route_name', '').strip()
    if not route_name:
        return jsonify({'message': 'route_name query param is required'}), 400

    route = Route.query.filter_by(name=route_name, device_id=device.id).first()
    if not route:
        return jsonify({'message': 'Route not found'}), 404

    return jsonify({'steps': json.loads(route.instructions_json or '[]')}), 200
