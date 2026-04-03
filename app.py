import os

import CORS
from flask import Flask
# Import the blueprint, extensions, and models from api.py
from api import api_bp, db, jwt, User

app = Flask(__name__)
# Enable CORS so  React frontend can communicate with this API
CORS(app)
# --- Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/dbname'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-super-secret-jwt-key'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Initialize Extensions ---
# This binds the db and jwt instances from api.py to this specific Flask app
db.init_app(app)
jwt.init_app(app)

# --- Register Blueprints ---
# This tells Flask about all the routes you defined in api.py
app.register_blueprint(api_bp)

if __name__ == '__main__':
    # Initialize the database tables before running
    with app.app_context():
        db.create_all()

        # Create a dummy user for testing if the table is empty
        if not User.query.first():
            test_user = User(username="user1", password="password123")
            db.session.add(test_user)
            db.session.commit()

    # Run the server
    app.run(debug=True, host='0.0.0.0', port=5000)