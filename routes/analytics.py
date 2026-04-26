import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from models import db, Run, WeedDetection, Device

analytics_bp = Blueprint('analytics', __name__)


def _run_payload(r):
    duration = None
    if r.started_at and r.finished_at:
        duration = int((r.finished_at - r.started_at).total_seconds())
    return {
        'id': r.id,
        'run_number': r.id,
        'device_id': r.device_id,
        'field': {'id': r.field.id, 'name': r.field.name} if r.field else None,
        'datetime': r.started_at.isoformat() if r.started_at else None,
        'duration': duration,
        'weeds': r.total_weeds,
    }


@analytics_bp.route('/api/runs', methods=['GET'])
@jwt_required()
def list_runs():
    device_id = request.args.get('device_id')
    field_id = request.args.get('field_id', type=int)
    month = request.args.get('month')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    q = Run.query
    if device_id:
        q = q.filter_by(device_id=device_id)
    if field_id:
        q = q.filter_by(field_id=field_id)
    if month:
        try:
            year, mon = map(int, month.split('-'))
            start = datetime(year, mon, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if mon == 12 \
                else datetime(year, mon + 1, 1, tzinfo=timezone.utc)
            q = q.filter(Run.started_at >= start, Run.started_at < end)
        except ValueError:
            return jsonify({'message': 'month must be YYYY-MM'}), 400

    total = q.count()
    runs = q.order_by(Run.started_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return jsonify({'runs': [_run_payload(r) for r in runs], 'total': total}), 200


@analytics_bp.route('/api/runs/<int:run_id>', methods=['GET'])
@jwt_required()
def get_run(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    return jsonify(_run_payload(run)), 200


@analytics_bp.route('/api/runs/<int:run_id>/density-map', methods=['GET'])
@jwt_required()
def run_density_map(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    return jsonify(run.get_grid()), 200


@analytics_bp.route('/api/runs/<int:run_id>/species', methods=['GET'])
@jwt_required()
def run_species(run_id):
    if not db.session.get(Run, run_id):
        return jsonify({'message': 'Run not found'}), 404
    rows = db.session.query(
        WeedDetection.species,
        db.func.sum(WeedDetection.count).label('total')
    ).filter_by(run_id=run_id).group_by(WeedDetection.species).all()
    return jsonify([{'species': r.species, 'count': int(r.total)} for r in rows]), 200


@analytics_bp.route('/api/runs/<int:run_id>/device-summary', methods=['GET'])
@jwt_required()
def run_device_summary(run_id):
    run = db.session.get(Run, run_id)
    if not run:
        return jsonify({'message': 'Run not found'}), 404
    device = Device.query.filter_by(device_id=run.device_id).first()
    return jsonify({
        'device_id': run.device_id,
        'device_name': device.name if device else None,
        'serial_port': device.serial_port if device else None,
        'camera_index': device.camera_index if device else None,
        'confidence_threshold': device.confidence_threshold if device else None,
    }), 200


@analytics_bp.route('/api/runs/<int:run_id>/detection-logs', methods=['GET'])
@jwt_required()
def run_detection_logs(run_id):
    if not db.session.get(Run, run_id):
        return jsonify({'message': 'Run not found'}), 404
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    q = WeedDetection.query.filter_by(run_id=run_id).order_by(WeedDetection.detected_at.asc())
    total = q.count()
    logs = q.offset((page - 1) * limit).limit(limit).all()

    base_url = request.host_url.rstrip('/')

    def image_url(path, kind):
        if not path:
            return None
        return f"{base_url}/api/media/{kind}/{os.path.basename(path)}"

    return jsonify({
        'total': total,
        'logs': [{
            'id': d.id,
            'timestamp': d.detected_at.isoformat() if d.detected_at else None,
            'species': d.species,
            'confidence': d.confidence,
            'cell': d.grid_x,
            'image_url': image_url(d.annotated_image_path, 'annotated')
                         or image_url(d.original_image_path, 'original'),
        } for d in logs],
    }), 200
