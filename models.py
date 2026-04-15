import json
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from datetime import datetime, timezone

db = SQLAlchemy()
jwt = JWTManager()


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class TokenBlocklist(db.Model):
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Field(db.Model):
    __tablename__ = 'fields'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    width_m = db.Column(db.Float, nullable=False)
    height_m = db.Column(db.Float, nullable=False)
    partition_config = db.Column(db.Text, nullable=True)  # JSON string
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=True)
    last_seen = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), default='idle')  # 'working' or 'idle'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DeviceSettings(db.Model):
    __tablename__ = 'device_settings'
    device_id = db.Column(db.String(50), db.ForeignKey('devices.id'), primary_key=True)
    config = db.Column(db.Text, nullable=False, default='{}')  # JSON config blob
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Run(db.Model):
    __tablename__ = 'runs'
    id = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=False)
    device_id = db.Column(db.String(50), db.ForeignKey('devices.id'), nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    total_weeds = db.Column(db.Integer, default=0)


class WeedDetection(db.Model):
    __tablename__ = 'weed_detections'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=False)
    grid_x = db.Column(db.Integer, nullable=False)
    grid_y = db.Column(db.Integer, nullable=False)
    coord_x = db.Column(db.Float, nullable=True)
    coord_y = db.Column(db.Float, nullable=True)
    species = db.Column(db.String(100), nullable=False)
    count = db.Column(db.Integer, default=1)
    original_image_path = db.Column(db.String(255), nullable=True)
    annotated_image_path = db.Column(db.String(255), nullable=True)
    detected_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ActiveDetection(db.Model):
    """Tracks the in-progress detection session for a device (one row per device)."""
    __tablename__ = 'active_detections'
    device_id = db.Column(db.String(50), db.ForeignKey('devices.id'), primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=True)
    status = db.Column(db.String(20), default='idle')  # running|idle|completed|stopped
    cells_total = db.Column(db.Integer, default=0)
    cells_scanned = db.Column(db.Integer, default=0)
    weeds_found = db.Column(db.Integer, default=0)
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_updated = db.Column(db.DateTime(timezone=True), nullable=True)


class Route(db.Model):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    device_id = db.Column(db.String(50), db.ForeignKey('devices.id'), nullable=True)
    instructions = db.Column(db.Text, nullable=False)  # JSON list of ordered steps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# --- Legacy models (kept for backwards compatibility with Jetson endpoints) ---

class DeviceCommand(db.Model):
    __tablename__ = 'device_commands'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)
    command_value = db.Column(db.Integer, nullable=False)  # 0=Fwd 1=Bwd 2=Right 3=Left 4=Stop
    status = db.Column(db.String(20), default='pending', nullable=False)
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


class CommandQueue(db.Model):
    __tablename__ = 'command_queue'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)
    command_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
