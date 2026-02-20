"""Flask application factory.

Creates and configures the Flask app, registers extensions, error
handlers, and API namespaces.
"""

import json
import logging
import os
from decimal import Decimal

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_restx import Api

from app.config.settings import CONFIG_MAP
from app.extensions import db


class CustomJSONProvider(DefaultJSONProvider):
    """Extend Flask's default JSON provider to handle Decimal types."""

    @staticmethod
    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'production'.
                     Defaults to the FLASK_ENV environment variable.
    """
    app = Flask(__name__)
    app.json_provider_class = CustomJSONProvider
    app.json = CustomJSONProvider(app)

    # --- Configuration ---
    config_name = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(CONFIG_MAP[config_name])

    # --- Extensions ---
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # --- Logging ---
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # --- API ---
    api = Api(
        app,
        title="Dynamic Subscription System",
        version="1.0",
        description="A fully dynamic, configuration-driven subscription engine",
    )

    # Register namespaces
    from app.api.mobile import ns as mobile_ns
    from app.api.dashboard import ns as dashboard_ns

    api.add_namespace(mobile_ns, path="/mobile")
    api.add_namespace(dashboard_ns, path="/dashboard")

    # --- Global error handler ---
    _register_error_handlers(app)

    return app


def _register_error_handlers(app: Flask) -> None:
    """Map application exceptions to JSON responses."""
    from app.domain.exceptions import AppError  # noqa: avoid circular import

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        from app.schemas.response import error_response
        return error_response(error.message, error.error_code, error.status_code)

    @app.errorhandler(404)
    def handle_not_found(_error):
        from app.schemas.response import error_response
        return error_response("Resource not found", "NOT_FOUND", 404)

    @app.errorhandler(500)
    def handle_internal(_error):
        from app.schemas.response import error_response
        logging.getLogger(__name__).exception("Unhandled server error")
        return error_response("Internal server error", "INTERNAL_ERROR", 500)
