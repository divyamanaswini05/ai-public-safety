"""AI engine routes — capability status and one-shot detection runs."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ai.service import engine_status, run_detection
from extensions import db
from models import Camera, Setting
from models.enums import RoleSlug
from services import dashboard_service
from utils.decorators import role_required

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")

RUN_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)


@ai_bp.get("/")
@login_required
def index():
    """Show engine capabilities, detection settings and recent detections."""
    settings = {
        "confidence": Setting.get("alerts.confidence", "0.45"),
        "cooldown": Setting.get("alerts.cooldown_seconds", "60"),
        "fps": Setting.get("surveillance.fps", "15"),
    }
    return render_template(
        "ai/index.html",
        status=engine_status(),
        settings=settings,
        cameras=Camera.query.order_by(Camera.name).all(),
        recent_incidents=dashboard_service.get_recent_incidents(8),
    )


@ai_bp.post("/run")
@role_required(*RUN_ROLES)
def run():
    """Run a one-shot detection pass over a selected camera."""
    camera = db.get_or_404(Camera, request.form.get("camera_id", type=int))
    detector_name = request.form.get("detector") or None
    result = run_detection(camera, detector_name=detector_name)
    if result["status"] != "ok":
        flash(
            f"Detection run on '{camera.name}' could not start "
            f"({result['status']}).",
            "warning",
        )
        return redirect(url_for("ai.index"))
    flash(
        f"Detection on '{camera.name}' via {result['detector']} "
        f"({result['source']}): {result['detections']} detection(s), "
        f"{result['incidents_created']} incident(s) created.",
        "success",
    )
    return redirect(url_for("ai.index"))
