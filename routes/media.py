import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from models import db, DeviceCommand, PredictionRecord, Run, WeedDetection

media_bp = Blueprint('media', __name__)


@media_bp.route('/api/media/original/<path:filename>', methods=['GET'])
@jwt_required()
def serve_original(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@media_bp.route('/api/media/annotated/<path:filename>', methods=['GET'])
@jwt_required()
def serve_annotated(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@media_bp.route('/api/media/upload', methods=['POST'])
@jwt_required()
def media_upload():
    """Upload original + annotated images with prediction metadata (Jetson → cloud)."""
    device_id = request.form.get('deviceID')
    timestamp_str = request.form.get('timestamp')
    grid_x = request.form.get('grid_x', type=int)
    grid_y = request.form.get('grid_y', type=int)
    coord_x = request.form.get('coord_x', type=float)
    coord_y = request.form.get('coord_y', type=float)
    prediction_text = request.form.get('prediction_text', '')
    run_id = request.form.get('run_id', type=int)

    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return jsonify({"msg": "Invalid timestamp format. Use ISO format."}), 400

    if 'original_image' not in request.files or 'annotated_image' not in request.files:
        return jsonify({"msg": "Both original_image and annotated_image files are required"}), 400

    orig_file = request.files['original_image']
    ann_file = request.files['annotated_image']

    upload_folder = current_app.config['UPLOAD_FOLDER']
    orig_filename = secure_filename(f"{device_id}_{orig_file.filename}")
    ann_filename = secure_filename(f"{device_id}_ann_{ann_file.filename}")
    orig_path = os.path.join(upload_folder, orig_filename)
    ann_path = os.path.join(upload_folder, ann_filename)
    orig_file.save(orig_path)
    ann_file.save(ann_path)

    db.session.add(PredictionRecord(
        device_id=device_id,
        timestamp=timestamp,
        position_in_field=f"{grid_x},{grid_y}" if grid_x is not None else '',
        prediction_text=prediction_text,
        original_image_path=orig_path,
        annotated_image_path=ann_path,
    ))

    if run_id and grid_x is not None and grid_y is not None:
        run = Run.query.get(run_id)
        if run:
            db.session.add(WeedDetection(
                run_id=run_id,
                field_id=run.field_id,
                grid_x=grid_x,
                grid_y=grid_y,
                coord_x=coord_x,
                coord_y=coord_y,
                species=prediction_text or 'unknown',
                count=1,
                original_image_path=orig_path,
                annotated_image_path=ann_path,
                detected_at=timestamp,
            ))
            run.total_weeds = (run.total_weeds or 0) + 1

    db.session.commit()
    return jsonify({"msg": "Upload successful", "original": orig_filename, "annotated": ann_filename}), 201


# --- Legacy Jetson endpoints ---

@media_bp.route('/api/predictions', methods=['POST'])
@jwt_required()
def store_prediction():
    device_id = request.form.get('deviceID')
    timestamp_str = request.form.get('timestamp')
    position_in_field = request.form.get('position_in_field')
    prediction_text = request.form.get('prediction_text')

    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return jsonify({"msg": "Invalid timestamp format. Use ISO format."}), 400

    if 'original_image' not in request.files or 'annotated_image' not in request.files:
        return jsonify({"msg": "Both original_image and annotated_image files are required"}), 400

    orig_image = request.files['original_image']
    ann_image = request.files['annotated_image']
    upload_folder = current_app.config['UPLOAD_FOLDER']
    orig_path = os.path.join(upload_folder, secure_filename(f"{device_id}_{orig_image.filename}"))
    ann_path = os.path.join(upload_folder, secure_filename(f"{device_id}_{ann_image.filename}"))
    orig_image.save(orig_path)
    ann_image.save(ann_path)

    record = PredictionRecord(
        device_id=device_id,
        timestamp=timestamp,
        position_in_field=position_in_field,
        prediction_text=prediction_text,
        original_image_path=orig_path,
        annotated_image_path=ann_path,
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"msg": "Prediction record stored successfully", "id": record.id}), 201


@media_bp.route('/api/get-commands/<device_id>', methods=['GET'])
@jwt_required()
def get_pending_commands(device_id):
    pending_cmd = DeviceCommand.query.filter_by(
        device_id=device_id, status='pending'
    ).order_by(DeviceCommand.timestamp.asc()).first()

    if not pending_cmd:
        return jsonify({"msg": "No pending commands", "command": None}), 200

    pending_cmd.status = 'executed'
    db.session.commit()
    return jsonify({
        "msg": "Command retrieved",
        "command": {
            "id": pending_cmd.id,
            "command_value": pending_cmd.command_value,
            "timestamp": pending_cmd.timestamp.isoformat(),
        },
    }), 200


@media_bp.route('/api/send-command', methods=['POST'])
@jwt_required()
def send_command():
    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON data"}), 400

    device_id = data.get('deviceID')
    command_value = data.get('command_value')

    if not device_id or command_value is None:
        return jsonify({"msg": "deviceID and command_value are required"}), 400
    if command_value not in [0, 1, 2, 3, 4]:
        return jsonify({"msg": "Invalid command value. Must be 0-4."}), 400

    new_cmd = DeviceCommand(device_id=device_id, command_value=command_value, status='pending')
    db.session.add(new_cmd)
    db.session.commit()
    return jsonify({"msg": "Command queued successfully", "command_id": new_cmd.id}), 201
