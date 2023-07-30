import os
from flask import Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)
from app import routes
