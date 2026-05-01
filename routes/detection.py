import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from models import db, Device, DeviceCommand, Run, WeedDetection, IoTCommand

detection_bp = Blueprint('detection', __name__)

_COMMAND_MAP = {'forward': 0, 'backward': 1, 'right': 2, 'left': 3, 'weed': 5}


def _total_steps_for_run(run):
    field = run.field
    device = db.session.get(Device, run.device_db_id)
    camera_width = device.camera_vision_width_cm if device else None
    if not field or not camera_width:
        return 0
    forward_cm = field.length * 100 if field.partition_type == 'row' else field.width * 100
    return round(forward_cm / camera_width)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@detection_bp.route('/api/devices/<int:device_id>/detection/start', methods=['POST'])
@jwt_required()
def detection_start(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    if device.working:
        return jsonify({'message': 'Device is already running a detection'}), 409

    data = request.get_json() or {}
    field_id = data.get('field_id')
    if not field_id:
        return jsonify({'message': 'field_id is required'}), 400

    mode = data.get('mode', 'grid')
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
        run.start_row = data.get('start_row', 0)
        run.start_col = data.get('start_col', 0)
        run.grid_state_json = json.dumps([[0] * grid_x for _ in range(grid_y)])
        iot_payload = {'mode': 'B', 'job_id': None, 'travel_distance_cm': run.grid_distance}
    elif mode == 'route':
        route_id = data.get('route_id')
        if not route_id:
            return jsonify({'message': 'route_id is required for route mode'}), 400
        iot_payload = {'mode': 'C', 'job_id': None, 'route_id': route_id}
    else:
        iot_payload = {'mode': mode, 'job_id': None}

    db.session.add(run)
    device.working = True
    device.state = 'working'
    db.session.flush()

    iot_payload['job_id'] = run.id
    db.session.add(IoTCommand(
        device_id=device.device_id,
        command='start',
        payload_json=json.dumps(iot_payload),
    ))
    db.session.commit()
    return jsonify({'message': 'Detection started'}), 200


@detection_bp.route('/api/devices/<int:device_id>/detection/stop', methods=['POST'])
@jwt_required()
def detection_stop(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404

    run = Run.query.filter_by(device_db_id=device_id, status='running').order_by(Run.started_at.desc()).first()
    now = datetime.now(timezone.utc)
    if run:
        run.status = 'stopped'
        run.stopped_at = now

    device.working = False
    device.state = 'idle'
    db.session.add(IoTCommand(device_id=device.device_id, command='stop', payload_json='{}'))
    db.session.commit()
    return jsonify({'message': 'Detection stopped'}), 200


@detection_bp.route('/api/devices/<int:device_id>/detection/status', methods=['GET'])
@jwt_required()
def detection_status(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404

    run = Run.query.filter_by(device_db_id=device_id).order_by(Run.started_at.desc()).first()
    if not run:
        return jsonify({
            'status': 'idle',
            'current_steps': 0,
            'total_steps': 0,
            'total_distance_cm': 0,
            'cells_scanned': 0,
            'weeds_found': 0,
            'finished_at': None,
            'stopped_at': None,
        }), 200

    total_steps = _total_steps_for_run(run)
    return jsonify({
        'status': run.status,
        'current_steps': run.cells_scanned,
        'total_steps': total_steps,
        'total_distance_cm': run.grid_distance or 0,
        'cells_scanned': run.cells_scanned,
        'weeds_found': run.total_weeds,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        'stopped_at': run.stopped_at.isoformat() if run.stopped_at else None,
    }), 200


@detection_bp.route('/api/devices/<int:device_id>/detection/grid', methods=['GET'])
@jwt_required()
def detection_grid(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404

    run = Run.query.filter_by(device_db_id=device_id).order_by(Run.started_at.desc()).first()
    if not run:
        return jsonify([{'cell': i, 'weed_count': 0, 'step_count': 0} for i in range(20)]), 200

    detections = WeedDetection.query.filter_by(run_id=run.id).order_by(WeedDetection.id).all()
    GRID_SIZE = 20
    total_steps = _total_steps_for_run(run)
    scanned = run.cells_scanned

    cells_per_step = GRID_SIZE / total_steps if total_steps > 0 else GRID_SIZE
    buckets = [{'weed_count': 0, 'step_count': 0} for _ in range(GRID_SIZE)]

    # Mark all scanned steps as visited (step_count=1) across their display cells
    for step_i in range(min(scanned, total_steps or scanned)):
        start = round(step_i * cells_per_step)
        end = round((step_i + 1) * cells_per_step)
        for ci in range(start, min(end, GRID_SIZE)):
            buckets[ci]['step_count'] = 1

    # Distribute weed counts: each detection record corresponds to one step (in order)
    for i, det in enumerate(detections):
        if total_steps > 0 and i >= total_steps:
            break
        step_i = i
        start = round(step_i * cells_per_step)
        end = round((step_i + 1) * cells_per_step)
        for ci in range(start, min(end, GRID_SIZE)):
            if det.species != 'none':
                buckets[ci]['weed_count'] += det.count

    return jsonify([{'cell': i, **b} for i, b in enumerate(buckets)]), 200


# ---------------------------------------------------------------------------
# Manual Control
# ---------------------------------------------------------------------------

@detection_bp.route('/api/devices/<int:device_id>/move', methods=['POST'])
@jwt_required()
def device_move(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    data = request.get_json() or {}
    command = data.get('command')
    value = data.get('value')
    if not command or value is None:
        return jsonify({'message': 'command and value are required'}), 400
    if command not in _COMMAND_MAP:
        return jsonify({'message': f'command must be one of {list(_COMMAND_MAP)}'}), 400

    db.session.add(DeviceCommand(
        device_id=device.device_id,
        command_value=_COMMAND_MAP[command],
        status='pending',
    ))
    db.session.commit()
    return jsonify({'message': 'Command sent'}), 200
