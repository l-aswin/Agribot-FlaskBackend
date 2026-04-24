from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone, timedelta
from models import db, Device, Run, WeedDetection

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/dashboard/metrics', methods=['GET'])
@jwt_required()
def dashboard_metrics():
    field_id = request.args.get('field_id', type=int)

    runs_q = Run.query
    if field_id:
        runs_q = runs_q.filter_by(field_id=field_id)

    total_weeds = db.session.query(db.func.sum(WeedDetection.count)).filter(
        WeedDetection.field_id == field_id if field_id else True
    ).scalar() or 0

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
    active_devices = Device.query.filter(Device.last_seen >= cutoff).count()

    return jsonify({
        "total_weeds_detected": total_weeds,
        "total_runs": runs_q.count(),
        "active_device_count": active_devices,
    }), 200


@dashboard_bp.route('/api/dashboard/species-breakdown', methods=['GET'])
@jwt_required()
def dashboard_species_breakdown():
    field_id = request.args.get('field_id', type=int)
    run_id = request.args.get('run_id')

    if run_id == 'latest' or run_id is None:
        q = Run.query
        if field_id:
            q = q.filter_by(field_id=field_id)
        latest_run = q.order_by(Run.started_at.desc()).first()
        run_id = latest_run.id if latest_run else None

    if run_id is None:
        return jsonify([]), 200

    rows = db.session.query(
        WeedDetection.species,
        db.func.sum(WeedDetection.count).label('total')
    ).filter_by(run_id=run_id).group_by(WeedDetection.species).all()

    return jsonify([{"species": r.species, "count": int(r.total)} for r in rows]), 200


@dashboard_bp.route('/api/dashboard/density-map', methods=['GET'])
@jwt_required()
def dashboard_density_map():
    field_id = request.args.get('field_id', type=int)
    run_id = request.args.get('run_id')

    if run_id == 'latest' or run_id is None:
        q = Run.query
        if field_id:
            q = q.filter_by(field_id=field_id)
        latest_run = q.order_by(Run.started_at.desc()).first()
        run_id = latest_run.id if latest_run else None

    if run_id is None:
        return jsonify([]), 200

    rows = db.session.query(
        WeedDetection.grid_x,
        WeedDetection.grid_y,
        db.func.sum(WeedDetection.count).label('density')
    ).filter_by(run_id=run_id).group_by(
        WeedDetection.grid_x, WeedDetection.grid_y
    ).all()

    return jsonify([{"x": r.grid_x, "y": r.grid_y, "density": int(r.density)} for r in rows]), 200


@dashboard_bp.route('/api/dashboard/runs-chart', methods=['GET'])
@jwt_required()
def dashboard_runs_chart():
    field_id = request.args.get('field_id', type=int)
    period = request.args.get('period', '30d')

    days = int(period.rstrip('d')) if period.endswith('d') else 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    q = Run.query.filter(Run.started_at >= cutoff)
    if field_id:
        q = q.filter_by(field_id=field_id)

    return jsonify([{
        "run_id": r.id,
        "started_at": r.started_at.isoformat(),
        "total_weeds": r.total_weeds,
    } for r in q.order_by(Run.started_at.asc()).all()]), 200
