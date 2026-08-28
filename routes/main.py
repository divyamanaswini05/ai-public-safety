"""Public routes shared by all users (landing page and health probe)."""

from flask import Blueprint, current_app, jsonify, render_template

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    """Landing page describing the system and its modules."""
    return render_template("index.html")


@main_bp.get("/health")
def health():
    """Liveness probe used by load balancers and uptime monitors."""
    return jsonify(
        status="ok",
        service=current_app.config["APP_NAME"],
        version=current_app.config["APP_VERSION"],
    )
