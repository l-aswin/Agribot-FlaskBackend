import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from models import db, Field

fields_bp = Blueprint('fields', __name__)


@fields_bp.route('/api/fields', methods=['GET'])
@jwt_required()
def list_fields():
    fields = Field.query.all()
    return jsonify([_field_payload(f) for f in fields]), 200


@fields_bp.route('/api/fields', methods=['POST'])
@jwt_required()
def create_field():
    data = request.get_json()
    name = data.get('name')
    width_m = data.get('width_m')
    height_m = data.get('height_m')
    partition_config = data.get('partition_config')

    if not name or width_m is None or height_m is None:
        return jsonify({"msg": "name, width_m, and height_m are required"}), 400

    field = Field(
        name=name,
        width_m=width_m,
        height_m=height_m,
        partition_config=json.dumps(partition_config) if partition_config else None,
    )
    db.session.add(field)
    db.session.commit()
    return jsonify({"msg": "Field created", "id": field.id}), 201


@fields_bp.route('/api/fields/<int:field_id>', methods=['GET'])
@jwt_required()
def get_field(field_id):
    f = Field.query.get_or_404(field_id)
    return jsonify(_field_payload(f)), 200


@fields_bp.route('/api/fields/<int:field_id>', methods=['PUT'])
@jwt_required()
def update_field(field_id):
    f = Field.query.get_or_404(field_id)
    data = request.get_json()
    if 'name' in data:
        f.name = data['name']
    if 'width_m' in data:
        f.width_m = data['width_m']
    if 'height_m' in data:
        f.height_m = data['height_m']
    if 'partition_config' in data:
        f.partition_config = json.dumps(data['partition_config'])
    db.session.commit()
    return jsonify({"msg": "Field updated"}), 200


@fields_bp.route('/api/fields/<int:field_id>', methods=['DELETE'])
@jwt_required()
def delete_field(field_id):
    f = Field.query.get_or_404(field_id)
    db.session.delete(f)
    db.session.commit()
    return jsonify({"msg": "Field deleted"}), 200


def _field_payload(f):
    return {
        'id': f.id,
        'name': f.name,
        'width_m': f.width_m,
        'height_m': f.height_m,
        'partition_config': json.loads(f.partition_config) if f.partition_config else None,
        'created_at': f.created_at.isoformat(),
    }
