import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from models import db, Run, WeedDetection

analytics_bp = Blueprint('analytics', __name__)


def _run_payload(r):
    duration = None
    if r.completed_at and r.started_at:
        duration = int((r.completed_at - r.started_at).total_seconds())
    return {
        "id": r.id,
        "field_id": r.field_id,
        "device_id": r.device_id,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "total_weeds": r.total_weeds,
        "duration_seconds": duration,
    }


@analytics_bp.route('/api/runs', methods=['GET'])
@jwt_required()
def list_runs():
    device_id = request.args.get('device_id')
    field_id = request.args.get('field_id', type=int)
    month = request.args.get('month')       # YYYY-MM
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    q = Run.query
    if device_id:
        q = q.filter_by(device_id=device_id)
    if field_id:
        q = q.filter_by(field_id=field_id)
    if month:
        try:
            start = datetime.strptime(month, '%Y-%m').replace(tzinfo=timezone.utc)
            end = start.replace(year=start.year + 1, month=1) if start.month == 12 \
                else start.replace(month=start.month + 1)
            q = q.filter(Run.started_at >= start, Run.started_at < end)
        except ValueError:
            return jsonify({"msg": "month must be YYYY-MM"}), 400

    pagination = q.order_by(Run.started_at.desc()).paginate(page=page, per_page=limit, error_out=False)
    return jsonify({
        "page": page,
        "limit": limit,
        "total": pagination.total,
        "runs": [_run_payload(r) for r in pagination.items],
    }), 200


@analytics_bp.route('/api/runs/<int:run_id>', methods=['GET'])
@jwt_required()
def get_run(run_id):
    r = Run.query.get_or_404(run_id)
    return jsonify(_run_payload(r)), 200


@analytics_bp.route('/api/runs/<int:run_id>/density-map', methods=['GET'])
@jwt_required()
def run_density_map(run_id):
    Run.query.get_or_404(run_id)
    rows = db.session.query(
        WeedDetection.grid_x,
        WeedDetection.grid_y,
        db.func.sum(WeedDetection.count).label('density')
    ).filter_by(run_id=run_id).group_by(WeedDetection.grid_x, WeedDetection.grid_y).all()
    return jsonify([{"x": r.grid_x, "y": r.grid_y, "density": int(r.density)} for r in rows]), 200


@analytics_bp.route('/api/runs/<int:run_id>/species', methods=['GET'])
@jwt_required()
def run_species(run_id):
    Run.query.get_or_404(run_id)
    rows = db.session.query(
        WeedDetection.species,
        db.func.sum(WeedDetection.count).label('total')
    ).filter_by(run_id=run_id).group_by(WeedDetection.species).all()
    return jsonify([{"species": r.species, "count": int(r.total)} for r in rows]), 200


@analytics_bp.route('/api/runs/<int:run_id>/device-summary', methods=['GET'])
@jwt_required()
def run_device_summary(run_id):
    r = Run.query.get_or_404(run_id)
    photo_count = WeedDetection.query.filter_by(run_id=run_id).filter(
        WeedDetection.original_image_path.isnot(None)
    ).count()
    run_time_s = None
    if r.completed_at and r.started_at:
        run_time_s = int((r.completed_at - r.started_at).total_seconds())
    return jsonify({
        "device_id": r.device_id,
        "total_weeds": r.total_weeds,
        "total_photos": photo_count,
        "run_time_seconds": run_time_s,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }), 200


@analytics_bp.route('/api/runs/<int:run_id>/detection-logs', methods=['GET'])
@jwt_required()
def run_detection_logs(run_id):
    Run.query.get_or_404(run_id)
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)

    pagination = WeedDetection.query.filter_by(run_id=run_id).order_by(
        WeedDetection.detected_at.asc()
    ).paginate(page=page, per_page=limit, error_out=False)

    base_url = request.host_url.rstrip('/')

    def image_url(path, kind):
        if not path:
            return None
        return f"{base_url}/api/media/{kind}/{os.path.basename(path)}"

    return jsonify({
        "page": page,
        "limit": limit,
        "total": pagination.total,
        "logs": [{
            "id": d.id,
            "grid_x": d.grid_x,
            "grid_y": d.grid_y,
            "coord_x": d.coord_x,
            "coord_y": d.coord_y,
            "species": d.species,
            "count": d.count,
            "detected_at": d.detected_at.isoformat(),
            "original_image_url": image_url(d.original_image_path, 'original'),
            "annotated_image_url": image_url(d.annotated_image_path, 'annotated'),
        } for d in pagination.items],
    }), 200
