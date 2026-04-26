import json
import time
import urllib.request
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from models import db, Device, Route, IoTCommand

devices_bp = Blueprint('devices', __name__)


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@devices_bp.route('/api/devices', methods=['GET'])
@jwt_required()
def list_devices():
    return jsonify([d.to_dict() for d in Device.query.order_by(Device.id).all()]), 200


@devices_bp.route('/api/devices/check-name', methods=['GET'])
@jwt_required()
def check_device_name():
    name = request.args.get('name', '')
    available = Device.query.filter_by(name=name).first() is None
    return jsonify({'available': available}), 200


@devices_bp.route('/api/devices/<int:device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    return jsonify(device.to_dict()), 200


@devices_bp.route('/api/devices', methods=['POST'])
@jwt_required()
def create_device():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'message': 'name is required'}), 400
    if not data.get('device_id'):
        return jsonify({'message': 'device_id is required'}), 400
    if Device.query.filter_by(name=data['name']).first():
        return jsonify({'message': 'Device name already exists'}), 409
    if Device.query.filter_by(device_id=data['device_id']).first():
        return jsonify({'message': 'device_id already exists'}), 409

    device = Device(
        name=data['name'],
        device_id=data['device_id'],
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
    return jsonify(device.to_dict()), 201


@devices_bp.route('/api/devices/<int:device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    db.session.delete(device)
    db.session.commit()
    return jsonify({'message': 'Device deleted successfully'}), 200


@devices_bp.route('/api/devices/<int:device_id>/ping', methods=['GET'])
@jwt_required()
def ping_device(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    online = False
    latency_ms = None
    if device.server_url:
        try:
            t0 = time.monotonic()
            urllib.request.urlopen(device.server_url, timeout=3)
            latency_ms = round((time.monotonic() - t0) * 1000)
            online = True
        except Exception:
            pass
    device.status = 'online' if online else 'offline'
    db.session.commit()
    return jsonify({'online': online, 'latency_ms': latency_ms}), 200


@devices_bp.route('/api/devices/<int:device_id>/settings', methods=['GET'])
@jwt_required()
def get_device_settings(device_id):
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'message': 'Device not found'}), 404
    return jsonify(device.settings_dict()), 200


@devices_bp.route('/api/devices/<int:device_id>/settings', methods=['PUT'])
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

    iot_update = {k: data[k] for k in ('confidence_threshold', 'camera_vision_width_cm') if k in data}
    if iot_update:
        db.session.add(IoTCommand(
            device_id=device.device_id,
            command='update',
            payload_json=json.dumps(iot_update),
        ))
    db.session.commit()
    return jsonify(device.settings_dict()), 200


# ---------------------------------------------------------------------------
# Routes (saved movement sequences)
# ---------------------------------------------------------------------------

@devices_bp.route('/api/routes', methods=['GET'])
@jwt_required()
def list_routes():
    device_id = request.args.get('device_id', type=int)
    q = Route.query
    if device_id:
        q = q.filter_by(device_id=device_id)
    return jsonify([r.to_dict() for r in q.order_by(Route.id).all()]), 200


@devices_bp.route('/api/routes/<int:route_id>', methods=['GET'])
@jwt_required()
def get_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({'message': 'Route not found'}), 404
    return jsonify(route.to_dict()), 200


@devices_bp.route('/api/routes', methods=['POST'])
@jwt_required()
def create_route():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'message': 'name is required'}), 400
    if not data.get('device_id'):
        return jsonify({'message': 'device_id is required'}), 400
    route = Route(
        name=data['name'],
        device_id=data['device_id'],
        instructions_json=json.dumps(data.get('instructions', [])),
    )
    db.session.add(route)
    db.session.commit()
    return jsonify(route.to_dict()), 201


@devices_bp.route('/api/routes/<int:route_id>', methods=['PUT'])
@jwt_required()
def update_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({'message': 'Route not found'}), 404
    data = request.get_json() or {}
    if 'name' in data:
        route.name = data['name']
    if 'device_id' in data:
        route.device_id = data['device_id']
    if 'instructions' in data:
        route.instructions_json = json.dumps(data['instructions'])
    db.session.commit()
    return jsonify(route.to_dict()), 200


@devices_bp.route('/api/routes/<int:route_id>', methods=['DELETE'])
@jwt_required()
def delete_route(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({'message': 'Route not found'}), 404
    db.session.delete(route)
    db.session.commit()
    return jsonify({'message': 'Route deleted successfully'}), 200
