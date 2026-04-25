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
    name = db.Column(db.String(100), nullable=False)
    width = db.Column(db.Integer, nullable=False)
    length = db.Column(db.Integer, nullable=False)
    partition_type = db.Column(db.String(50), default='grid')
    partition_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'width': self.width,
            'length': self.length,
            'partition_type': self.partition_type,
            'partition_count': self.partition_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    device_id = db.Column(db.String(50), unique=True, nullable=False)
    device_secret = db.Column(db.String(255), nullable=False, default='')
    server_url = db.Column(db.String(255))
    serial_port = db.Column(db.String(100))
    serial_baud_rate = db.Column(db.Integer, default=115200)
    camera_index = db.Column(db.Integer, default=0)
    confidence_threshold = db.Column(db.Float, default=0.75)
    camera_vision_width_cm = db.Column(db.Integer, default=50)
    status = db.Column(db.String(20), default='offline')   # online | offline
    working = db.Column(db.Boolean, default=False)
    state = db.Column(db.String(20), default='idle')   # idle | working | pending_upload
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self, include_settings=False):
        d = {
            'id': self.id,
            'name': self.name,
            'device_id': self.device_id,
            'server_url': self.server_url,
            'status': self.status,
            'online': self.status == 'online',
            'working': self.working,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_settings:
            d.update({
                'serial_port': self.serial_port,
                'serial_baud_rate': self.serial_baud_rate,
                'camera_index': self.camera_index,
                'confidence_threshold': self.confidence_threshold,
            })
        return d

    def settings_dict(self):
        return {
            'server_url': self.server_url,
            'serial_port': self.serial_port,
            'serial_baud_rate': self.serial_baud_rate,
            'camera_index': self.camera_index,
            'confidence_threshold': self.confidence_threshold,
            'camera_vision_width_cm': self.camera_vision_width_cm,
        }


class Run(db.Model):
    __tablename__ = 'runs'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)   # device_id string (AB01)
    device_db_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=False)
    mode = db.Column(db.String(20), default='grid')        # grid | route
    status = db.Column(db.String(20), default='running')   # running | finished | stopped
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    stopped_at = db.Column(db.DateTime(timezone=True), nullable=True)
    total_weeds = db.Column(db.Integer, default=0)
    total_photos = db.Column(db.Integer, default=0)
    # Grid detection metadata
    grid_x = db.Column(db.Integer, default=0)
    grid_y = db.Column(db.Integer, default=0)
    grid_distance = db.Column(db.Integer, default=0)
    cells_scanned = db.Column(db.Integer, default=0)
    grid_state_json = db.Column(db.Text)   # JSON 2D array of weed counts

    field = db.relationship('Field', foreign_keys=[field_id], lazy='joined')

    def cells_total(self):
        return self.grid_x * self.grid_y

    def to_dict(self):
        duration = None
        if self.started_at and self.finished_at:
            duration = int((self.finished_at - self.started_at).total_seconds())
        return {
            'run_id': self.id,
            'run_number': self.id,
            'device_id': self.device_id,
            'field_id': self.field_id,
            'field': self.field.name if self.field else None,
            'mode': self.mode,
            'status': self.status,
            'datetime': self.started_at.isoformat() if self.started_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'weeds': self.total_weeds,
            'total_weeds': self.total_weeds,
            'duration': duration,
        }

    def _init_grid(self):
        if not self.grid_state_json and self.grid_x and self.grid_y:
            self.grid_state_json = json.dumps(
                [[0] * self.grid_x for _ in range(self.grid_y)]
            )

    def get_grid(self):
        if not self.grid_state_json:
            self._init_grid()
        return json.loads(self.grid_state_json or '[]')

    def set_grid(self, grid):
        self.grid_state_json = json.dumps(grid)


class WeedDetection(db.Model):
    __tablename__ = 'weed_detections'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id'), nullable=False)
    grid_x = db.Column(db.Integer, nullable=True)
    grid_y = db.Column(db.Integer, nullable=True)
    coord_x = db.Column(db.Float, nullable=True)
    coord_y = db.Column(db.Float, nullable=True)
    species = db.Column(db.String(100), nullable=False)
    count = db.Column(db.Integer, default=1)
    original_image_path = db.Column(db.String(255), nullable=True)
    annotated_image_path = db.Column(db.String(255), nullable=True)
    detected_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Serializes the object to a dictionary matching the format in DEVELOPER_REFERENCE.md."""
        import os
        original_filename = os.path.basename(self.original_image_path) if self.original_image_path else None
        annotated_filename = os.path.basename(self.annotated_image_path) if self.annotated_image_path else None

        grid_pos_str = f"{self.grid_x},{self.grid_y}" if self.grid_x is not None and self.grid_y is not None else None

        return {
            'id': self.id,
            'grid_pos': grid_pos_str,
            'original_url': f"/api/media/original/{original_filename}" if original_filename else None,
            'annotated_url': f"/api/media/annotated/{annotated_filename}" if annotated_filename else None,
            'species': self.species,
            'timestamp': self.detected_at.isoformat() if self.detected_at else None,
        }


class Route(db.Model):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    instructions_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'device_id': self.device_id,
            'instructions': json.loads(self.instructions_json or '[]'),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


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


class DetectionLog(db.Model):
    __tablename__ = 'detection_logs'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    species = db.Column(db.String(100))
    confidence = db.Column(db.Float, default=0.0)
    cell = db.Column(db.String(20))
    photo_url = db.Column(db.String(255))

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'species': self.species,
            'confidence': self.confidence,
            'cell': self.cell,
            'photo_url': self.photo_url,
        }


class IoTCommand(db.Model):
    __tablename__ = 'iot_commands'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, index=True)
    command = db.Column(db.String(50), nullable=False)
    payload_json = db.Column(db.Text, default='{}')
    status = db.Column(db.String(20), default='pending', nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
