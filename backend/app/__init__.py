"""Application package providing the Flask app factory and shared extensions."""
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app() -> Flask:
    """Create and configure a Flask application instance."""
    app = Flask(__name__)

    database_url = os.environ.get("DATABASE_URL", "sqlite:///map360.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    return app
