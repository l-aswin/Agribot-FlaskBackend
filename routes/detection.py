from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from models import db, Device, DeviceCommand, Run, WeedDetection, ActiveDetection

detection_bp = Blueprint('detection', __name__)

_COMMAND_MAP = {'forward': 0, 'backward': 1, 'right': 2, 'left': 3}


# --- Weed Detection ---

@detection_bp.route('/api/devices/<string:device_id>/detection/start', methods=['POST'])
@jwt_required()
def detection_start(device_id):
    device = Device.query.get_or_404(device_id)
    data = request.get_json() or {}
    mode = data.get('mode', 'grid')

    run = Run(field_id=device.field_id, device_id=device_id)
    db.session.add(run)
    db.session.flush()

    ad = ActiveDetection.query.get(device_id)
    if not ad:
        ad = ActiveDetection(device_id=device_id)
        db.session.add(ad)

    now = datetime.now(timezone.utc)
    ad.run_id = run.id
    ad.status = 'running'
    ad.cells_scanned = 0
    ad.weeds_found = 0
    ad.position_x = data.get('grid_x', 0)
    ad.position_y = data.get('grid_y', 0)
    ad.cells_total = data.get('distance', 0)
    ad.started_at = now
    ad.finished_at = None
    ad.last_updated = now

    device.status = 'working'
    db.session.commit()
    return jsonify({"msg": "Detection started", "run_id": run.id, "mode": mode}), 200


@detection_bp.route('/api/devices/<string:device_id>/detection/stop', methods=['POST'])
@jwt_required()
def detection_stop(device_id):
    ad = ActiveDetection.query.get_or_404(device_id)
    now = datetime.now(timezone.utc)
    ad.status = 'stopped'
    ad.finished_at = now
    ad.last_updated = now

    if ad.run_id:
        run = Run.query.get(ad.run_id)
        if run:
            run.completed_at = now

    device = Device.query.get(device_id)
    if device:
        device.status = 'idle'

    db.session.commit()
    return jsonify({"msg": "Detection stopped", "stopped_at": now.isoformat()}), 200


@detection_bp.route('/api/devices/<string:device_id>/detection/status', methods=['GET'])
@jwt_required()
def detection_status(device_id):
    Device.query.get_or_404(device_id)
    ad = ActiveDetection.query.get(device_id)
    if not ad:
        return jsonify({
            "status": "idle",
            "cells_total": 0,
            "cells_scanned": 0,
            "weeds_found": 0,
            "device_position": {"x": 0, "y": 0},
            "last_updated": None,
        }), 200

    return jsonify({
        "status": ad.status,
        "run_id": ad.run_id,
        "cells_total": ad.cells_total,
        "cells_scanned": ad.cells_scanned,
        "weeds_found": ad.weeds_found,
        "device_position": {"x": ad.position_x, "y": ad.position_y},
        "started_at": ad.started_at.isoformat() if ad.started_at else None,
        "finished_at": ad.finished_at.isoformat() if ad.finished_at else None,
        "last_updated": ad.last_updated.isoformat() if ad.last_updated else None,
    }), 200


@detection_bp.route('/api/devices/<string:device_id>/detection/grid', methods=['GET'])
@jwt_required()
def detection_grid(device_id):
    Device.query.get_or_404(device_id)
    ad = ActiveDetection.query.get(device_id)
    if not ad or not ad.run_id:
        return jsonify([]), 200

    rows = db.session.query(
        WeedDetection.grid_x,
        WeedDetection.grid_y,
        db.func.sum(WeedDetection.count).label('density')
    ).filter_by(run_id=ad.run_id).group_by(
        WeedDetection.grid_x, WeedDetection.grid_y
    ).all()

    return jsonify([{"x": r.grid_x, "y": r.grid_y, "density": int(r.density)} for r in rows]), 200


# --- Manual Control ---

@detection_bp.route('/api/devices/<string:device_id>/move', methods=['POST'])
@jwt_required()
def device_move(device_id):
    Device.query.get_or_404(device_id)
    data = request.get_json() or {}
    command = data.get('command')
    value = data.get('value')

    if command not in _COMMAND_MAP:
        return jsonify({"msg": f"command must be one of {tuple(_COMMAND_MAP)}"}), 400

    new_cmd = DeviceCommand(
        device_id=device_id,
        command_value=_COMMAND_MAP[command],
        status='pending',
    )
    db.session.add(new_cmd)
    db.session.commit()
    return jsonify({
        "msg": "Move command queued",
        "command": command,
        "value": value,
        "command_id": new_cmd.id,
    }), 201
