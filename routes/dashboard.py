from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone, timedelta
from models import db, Device, Field, Run, WeedDetection

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/dashboard/metrics', methods=['GET'])
@jwt_required()
def dashboard_metrics():
    field_id = request.args.get('field_id', type=int)

    weeds_q = db.session.query(db.func.sum(WeedDetection.count))
    runs_q = Run.query
    if field_id:
        weeds_q = weeds_q.filter(WeedDetection.field_id == field_id)
        runs_q = runs_q.filter_by(field_id=field_id)

    total_weeds = weeds_q.scalar() or 0
    total_runs = runs_q.count()
    total_devices = Device.query.count()
    active_devices = Device.query.filter_by(status='online').count()

    return jsonify({
        'total_weeds': total_weeds,
        'total_runs': total_runs,
        'active_devices': active_devices,
        'total_devices': total_devices,
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
        latest = q.order_by(Run.started_at.desc()).first()
        run_id = latest.id if latest else None

    if run_id is None:
        return jsonify([]), 200

    rows = db.session.query(
        WeedDetection.species,
        db.func.sum(WeedDetection.count).label('total')
    ).filter_by(run_id=run_id).group_by(WeedDetection.species).all()

    return jsonify([{'species': r.species, 'count': int(r.total)} for r in rows]), 200


@dashboard_bp.route('/api/dashboard/density-map', methods=['GET'])
@jwt_required()
def dashboard_density_map():
    field_id = request.args.get('field_id', type=int)
    run_id = request.args.get('run_id')

    if run_id == 'latest' or run_id is None:
        q = Run.query
        if field_id:
            q = q.filter_by(field_id=field_id)
        latest = q.order_by(Run.started_at.desc()).first()
        run_id = latest.id if latest else None

    if run_id is None:
        return jsonify([]), 200

    run = db.session.get(Run, run_id)
    return jsonify(run.get_grid() if run else []), 200


@dashboard_bp.route('/api/dashboard/partition-density', methods=['GET'])
@jwt_required()
def dashboard_partition_density():
    field_id = request.args.get('field_id', type=int)
    if not field_id:
        return jsonify([]), 200

    field = db.session.get(Field, field_id)
    if not field:
        return jsonify({'message': 'Field not found'}), 404

    partition_count = field.partition_count or 0
    result = []
    for partition_idx in range(partition_count):
        run = Run.query.filter_by(field_id=field_id).filter(
            Run.start_col == partition_idx
        ).order_by(Run.started_at.desc()).first()
        result.append(run.get_grid() if run else None)

    return jsonify(result), 200


@dashboard_bp.route('/api/dashboard/runs-chart', methods=['GET'])
@jwt_required()
def dashboard_runs_chart():
    field_id = request.args.get('field_id', type=int)
    period = request.args.get('period', '30d')

    try:
        days = int(period.rstrip('d')) if period.endswith('d') else 30
    except ValueError:
        days = 30

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = Run.query.filter(Run.started_at >= cutoff)
    if field_id:
        q = q.filter_by(field_id=field_id)

    runs = q.order_by(Run.started_at.asc()).all()

    by_date = {}
    for r in runs:
        date_str = r.started_at.date().isoformat()
        if date_str not in by_date:
            by_date[date_str] = {'weeds': 0, 'runs': 0}
        by_date[date_str]['weeds'] += r.total_weeds or 0
        by_date[date_str]['runs'] += 1

    return jsonify([
        {'date': d, 'weeds': v['weeds'], 'runs': v['runs']}
        for d, v in sorted(by_date.items())
    ]), 200
