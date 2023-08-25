import os
from flask import Flask
from flask_cors import CORS

# Initialize CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = os.urandom(24)
from app import routes
