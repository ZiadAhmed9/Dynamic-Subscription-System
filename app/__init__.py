"""Flask application factory.

Creates and configures the Flask app with extensions.
"""

import os

from flask import Flask

from app.config.settings import CONFIG_MAP
from app.extensions import db, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__)
    config_name = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(CONFIG_MAP[config_name])

    db.init_app(app)
    migrate.init_app(app, db)

    return app