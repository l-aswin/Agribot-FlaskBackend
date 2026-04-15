from .auth import auth_bp
from .fields import fields_bp
from .devices import devices_bp
from .dashboard import dashboard_bp
from .analytics import analytics_bp
from .detection import detection_bp
from .device_routes import device_routes_bp
from .media import media_bp

all_blueprints = [
    auth_bp,
    fields_bp,
    devices_bp,
    dashboard_bp,
    analytics_bp,
    detection_bp,
    device_routes_bp,
    media_bp,
]
