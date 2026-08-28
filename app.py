"""Application entry point for the AI Public Safety Surveillance System.

Module 1 - Project setup
  * Application factory (``create_app``)
  * Extension wiring: db, migrate, bcrypt, csrf, mail, socketio, login
  * Blueprint registration
  * Global error handlers and template context

Module 2 - Database
  * SQLAlchemy models registered with the ORM
  * Flask-Migrate schema management (``flask db migrate`` / ``upgrade``)
  * CLI seeding (``flask seed``)

Module 3 - Authentication
  * Flask-Login bound with a user loader
  * Register / login / logout / forgot & reset password / email verification
  * Role-based access control helpers

Run locally with ``python app.py`` (websocket-enabled) or ``flask run``.
"""

import os
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template

import models  # noqa: F401  # registers every table with SQLAlchemy
from cli import register_cli_commands
from config import config
from extensions import bcrypt, csrf, db, login_manager, mail, migrate, socketio
from models import User

APP_NAME = "SentinelAI"
APP_VERSION = "1.0.0"


def _ensure_runtime_directories(app: Flask) -> None:
    """Create every folder the application needs at runtime."""
    folders = (
        Path(app.instance_path),
        Path(app.config["UPLOAD_FOLDER"]),
        Path(app.config["EVIDENCE_FOLDER"]),
        Path(app.config["ALERT_FOLDER"]),
        Path(app.config["WEIGHTS_FOLDER"]),
    )
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


def _register_error_handlers(app: Flask) -> None:
    """Serve themed HTML pages for fatal HTTP errors."""

    @app.errorhandler(404)
    def handle_not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def handle_forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def handle_internal_server_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure a Flask application instance."""
    selected = (config_name or os.getenv("FLASK_ENV") or "development").strip()
    if selected not in config:
        selected = "development"

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[selected])
    app.config["APP_NAME"] = APP_NAME
    app.config["APP_VERSION"] = APP_VERSION

    _ensure_runtime_directories(app)

    # --- Extensions ---------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        """Resolve the signed-in user for Flask-Login sessions."""
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # --- Blueprints -----------------------------------------------------------
    from routes import register_blueprints

    register_blueprints(app)

    # --- CLI commands -----------------------------------------------------------
    register_cli_commands(app)

    # --- Global handlers --------------------------------------------------------
    _register_error_handlers(app)

    @app.context_processor
    def inject_global_template_variables() -> dict:
        """Variables available in every rendered template."""
        return {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "current_year": datetime.now().year,
        }

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    socketio.run(app, host=host, port=port, debug=debug)
