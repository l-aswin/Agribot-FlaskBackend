import os
from flask import Blueprint, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

# Initialize extensions (they will be bound to the app in main.py)
db = SQLAlchemy()
jwt = JWTManager()

# Create a Blueprint for our API routes
api_bp = Blueprint('api', __name__)


# --- Database Models ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class DeviceCommand(db.Model):
    __tablename__ = 'device_commands'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)

    # Stores the integer command (0: Forward, 1: Backward, 2: Right, 3: Left, 4: Stop)
    command_value = db.Column(db.Integer, nullable=False)

    # Status can be 'pending' or 'executed'
    status = db.Column(db.String(20), default='pending', nullable=False)
    # Updated to use timezone-aware UTC
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PredictionRecord(db.Model):
    __tablename__ = 'predictionbs_history'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    position_in_field = db.Column(db.String(100), nullable=False)
    prediction_text = db.Column(db.Text, nullable=False)
    original_image_path = db.Column(db.String(255), nullable=False)
    annotated_image_path = db.Column(db.String(255), nullable=False)

# --- Database Structure ---
class CommandQueue(db.Model):
    """
    Stores commands sent from the React frontend to be picked up by the device.
    """
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)

    # Example commands: "Move Forward", "Turn Left", "Stop", etc.
    command_name = db.Column(db.String(50), nullable=False)

    # Statuses: 'pending', 'processing', 'completed'
    status = db.Column(db.String(20), default='pending')
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# --- API Endpoints ---

@api_bp.route('/api/login', methods=['POST'])
def login():
    """Validates username and password and returns an access token."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and user.password == password:
        access_token = create_access_token(identity=user.username)
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "Bad username or password"}), 401

#Jetson to cloud endpoints
@api_bp.route('/api/predictions', methods=['POST'])
@jwt_required()
def store_prediction():
    """Stores prediction data and images."""
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

    orig_filename = secure_filename(orig_image.filename)
    ann_filename = secure_filename(ann_image.filename)

    # Notice we use current_app.config here instead of app.config
    orig_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{device_id}_{orig_filename}")
    ann_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{device_id}_{ann_filename}")

    orig_image.save(orig_path)
    ann_image.save(ann_path)

    new_record = PredictionRecord(
        device_id=device_id,
        timestamp=timestamp,
        position_in_field=position_in_field,
        prediction_text=prediction_text,
        original_image_path=orig_path,
        annotated_image_path=ann_path
    )

    db.session.add(new_record)
    db.session.commit()

    return jsonify({"msg": "Prediction record stored successfully", "id": new_record.id}), 201


@api_bp.route('/api/get-commands/<device_id>', methods=['GET'])
@jwt_required()
def get_pending_commands(device_id):
    """
    API for the Jetson Nano.
    Fetches the oldest 'pending' command for the specific device and marks it 'executed'.
    """
    # Find the oldest pending command for this specific device
    pending_cmd = DeviceCommand.query.filter_by(
        device_id=device_id,
        status='pending'
    ).order_by(DeviceCommand.timestamp.asc()).first()

    if not pending_cmd:
        return jsonify({"msg": "No pending commands", "command": None}), 200

    # Mark as executed so it isn't pulled twice
    pending_cmd.status = 'executed'
    db.session.commit()

    return jsonify({
        "msg": "Command retrieved",
        "command": {
            "id": pending_cmd.id,
            "command_value": pending_cmd.command_value,
            "timestamp": pending_cmd.timestamp.isoformat()
        }
    }), 200

#endpoints from react frontend to backend

@api_bp.route('/api/send-command', methods=['POST'])
@jwt_required()
def send_command():
    """
    API for the React Frontend.
    Expects JSON: { "deviceID": "Jetson_01", "command_value": 0 }
    """
    data = request.get_json()

    if not data:
        return jsonify({"msg": "Missing JSON data"}), 400

    device_id = data.get('deviceID')
    command_value = data.get('command_value')

    # Validate inputs
    if not device_id or command_value is None:
        return jsonify({"msg": "deviceID and command_value are required"}), 400

    if command_value not in [0, 1, 2, 3, 4]:
        return jsonify({"msg": "Invalid command value. Must be 0-4."}), 400

    # Create a new command record in the database
    new_cmd = DeviceCommand(
        device_id=device_id,
        command_value=command_value,
        status='pending'
    )

    db.session.add(new_cmd)
    db.session.commit()

    return jsonify({"msg": "Command queued successfully", "command_id": new_cmd.id}), 201

