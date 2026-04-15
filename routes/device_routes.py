import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from models import db, Route

device_routes_bp = Blueprint('device_routes', __name__)


@device_routes_bp.route('/api/routes', methods=['GET'])
@jwt_required()
def list_routes():
    device_id = request.args.get('device_id')
    q = Route.query
    if device_id:
        q = q.filter_by(device_id=device_id)
    return jsonify([_route_payload(r, include_instructions=False)
                    for r in q.order_by(Route.created_at.desc()).all()]), 200


@device_routes_bp.route('/api/routes/<int:route_id>', methods=['GET'])
@jwt_required()
def get_route(route_id):
    r = Route.query.get_or_404(route_id)
    return jsonify(_route_payload(r, include_instructions=True)), 200


@device_routes_bp.route('/api/routes', methods=['POST'])
@jwt_required()
def create_route():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({"msg": "name is required"}), 400

    route = Route(
        name=name,
        device_id=data.get('device_id'),
        instructions=json.dumps(data.get('instructions', [])),
    )
    db.session.add(route)
    db.session.commit()
    return jsonify({"msg": "Route created", "id": route.id}), 201


@device_routes_bp.route('/api/routes/<int:route_id>', methods=['PUT'])
@jwt_required()
def update_route(route_id):
    r = Route.query.get_or_404(route_id)
    data = request.get_json() or {}
    if 'name' in data:
        r.name = data['name']
    if 'instructions' in data:
        r.instructions = json.dumps(data['instructions'])
    if 'device_id' in data:
        r.device_id = data['device_id']
    db.session.commit()
    return jsonify({"msg": "Route updated"}), 200


@device_routes_bp.route('/api/routes/<int:route_id>', methods=['DELETE'])
@jwt_required()
def delete_route(route_id):
    r = Route.query.get_or_404(route_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"msg": "Route deleted"}), 200


def _route_payload(r, include_instructions=True):
    payload = {
        "id": r.id,
        "name": r.name,
        "device_id": r.device_id,
        "created_at": r.created_at.isoformat(),
    }
    if include_instructions:
        payload["instructions"] = json.loads(r.instructions)
    return payload
