from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from models import db, Field

fields_bp = Blueprint('fields', __name__)


@fields_bp.route('/api/fields', methods=['GET'])
@jwt_required()
def list_fields():
    return jsonify([f.to_dict() for f in Field.query.order_by(Field.id).all()]), 200


@fields_bp.route('/api/fields', methods=['POST'])
@jwt_required()
def create_field():
    data = request.get_json() or {}
    required = ('name', 'width', 'length', 'partition_type', 'partition_count')
    missing = [k for k in required if data.get(k) is None]
    if missing:
        return jsonify({'message': f'Missing required fields: {missing}'}), 400

    field = Field(
        name=data['name'],
        width=data['width'],
        length=data['length'],
        partition_type=data['partition_type'],
        partition_count=data['partition_count'],
    )
    db.session.add(field)
    db.session.commit()
    return jsonify(field.to_dict()), 201


@fields_bp.route('/api/fields/<int:field_id>', methods=['PUT'])
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


@fields_bp.route('/api/fields/<int:field_id>', methods=['DELETE'])
@jwt_required()
def delete_field(field_id):
    field = db.session.get(Field, field_id)
    if not field:
        return jsonify({'message': 'Field not found'}), 404
    db.session.delete(field)
    db.session.commit()
    return jsonify({'message': 'Field deleted successfully'}), 200
