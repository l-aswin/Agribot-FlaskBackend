import os
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, jwt, User
from api import api_bp
from routes.media import media_bp

app = Flask(__name__)
CORS(app)

# --- Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://agribot-admin:1234@localhost:5432/agribot'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-super-secret-jwt-key'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Initialize Extensions ---
db.init_app(app)
jwt.init_app(app)
migrate = Migrate(app, db)

# --- Register Blueprints ---
app.register_blueprint(api_bp)
app.register_blueprint(media_bp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        if not User.query.first():
            db.session.add(User(username="guest", password="guest1234"))
            db.session.commit()

    app.run(debug=True, host='0.0.0.0', port=5000)
