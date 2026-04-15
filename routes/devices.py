import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone, timedelta
from models import db, Device, DeviceSettings, ActiveDetection

devices_bp = Blueprint('devices', __name__)


def _device_payload(d):
    online = (
        d.last_seen is not None and
        datetime.now(timezone.utc) - d.last_seen < timedelta(minutes=2)
    )
    settings = DeviceSettings.query.get(d.id)
    config = json.loads(settings.config) if settings else {}
    return {
        'id': d.id,
        'name': d.name,
        'field_id': d.field_id,
        'status': d.status,
        'connected': online,
        'last_seen': d.last_seen.isoformat() if d.last_seen else None,
        'created_at': d.created_at.isoformat() if d.created_at else None,
        'server_url': config.get('server_url'),
        'serial_port': config.get('serial_port'),
        'serial_baud_rate': config.get('serial_baud_rate'),
    }


@devices_bp.route('/api/devices', methods=['GET'])
@jwt_required()
def list_devices():
    name = request.args.get('name')
    created_date = request.args.get('created_date')  # YYYY-MM-DD

    q = Device.query
    if name:
        q = q.filter(
            db.or_(Device.name.ilike(f'%{name}%'), Device.id.ilike(f'%{name}%'))
        )
    if created_date:
        try:
            day_start = datetime.strptime(created_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            q = q.filter(Device.created_at >= day_start, Device.created_at < day_end)
        except ValueError:
            return jsonify({"msg": "created_date must be YYYY-MM-DD"}), 400

    return jsonify([_device_payload(d) for d in q.all()]), 200


@devices_bp.route('/api/devices', methods=['POST'])
@jwt_required()
def create_device():
    data = request.get_json() or {}
    device_id = data.get('id')
    name = data.get('name')
    field_id = data.get('field_id')

    if not device_id or not name:
        return jsonify({"msg": "id and name are required"}), 400
    if Device.query.get(device_id):
        return jsonify({"msg": "Device ID already exists"}), 409

    device = Device(id=device_id, name=name, field_id=field_id)
    db.session.add(device)

    default_config = {
        "device_id": device_id,
        "server_url": "http://192.168.1.18:5000",
        "serial_port": "/dev/ttyUSB0",
        "serial_baud_rate": 115200,
        "camera_index": 0,
        "confidence_threshold": 0.75,
    }
    db.session.add(DeviceSettings(device_id=device_id, config=json.dumps(default_config)))
    db.session.commit()
    return jsonify({"msg": "Device created", "id": device_id}), 201


@devices_bp.route('/api/devices/<string:device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    d = Device.query.get_or_404(device_id)
    return jsonify(_device_payload(d)), 200


@devices_bp.route('/api/devices/<string:device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    device = Device.query.get_or_404(device_id)
    ActiveDetection.query.filter_by(device_id=device_id).delete()
    DeviceSettings.query.filter_by(device_id=device_id).delete()
    db.session.delete(device)
    db.session.commit()
    return jsonify({"msg": "Device deleted"}), 200


@devices_bp.route('/api/devices/<string:device_id>/ping', methods=['GET'])
@jwt_required()
def ping_device(device_id):
    d = Device.query.get_or_404(device_id)
    online = (
        d.last_seen is not None and
        datetime.now(timezone.utc) - d.last_seen < timedelta(minutes=2)
    )
    return jsonify({"device_id": device_id, "online": online}), 200


@devices_bp.route('/api/devices/<string:device_id>/settings', methods=['GET'])
@jwt_required()
def get_device_settings(device_id):
    Device.query.get_or_404(device_id)
    settings = DeviceSettings.query.get(device_id)
    config = json.loads(settings.config) if settings else {}
    return jsonify({"device_id": device_id, "config": config}), 200


@devices_bp.route('/api/devices/<string:device_id>/settings', methods=['PUT'])
@jwt_required()
def update_device_settings(device_id):
    Device.query.get_or_404(device_id)
    data = request.get_json() or {}
    config = data.get('config', {})

    settings = DeviceSettings.query.get(device_id)
    if not settings:
        settings = DeviceSettings(device_id=device_id, config=json.dumps(config))
        db.session.add(settings)
    else:
        existing = json.loads(settings.config)
        existing.update(config)
        settings.config = json.dumps(existing)
        settings.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"msg": "Settings updated"}), 200
