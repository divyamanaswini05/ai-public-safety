"""Crowd analysis routes — Module 12.

Surfaces detector status, recent crowd incidents and a one-shot
manual run control.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models import Camera, Incident
from models.enums import IncidentType, RoleSlug
from ai.detectors_crowd import crowd_detector
from ai.weights import model_path, weights_dir
from utils.decorators import role_required

crowd_bp = Blueprint("crowd", __name__, url_prefix="/detection/crowd")

MANAGE_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)


def _detector_status() -> dict:
    return {
        "name": crowd_detector.name,
        "yolo_installed": crowd_detector.yolo_installed,
        "weights_present": crowd_detector.weights_present,
        "weights_path": model_path("crowd") or f"{weights_dir()}\\crowd.pt",
        "available": crowd_detector.available,
    }


def _recent_incidents() -> list[Incident]:
    return (
        Incident.query
        .filter(Incident.incident_type == IncidentType.CROWD)
        .order_by(Incident.detected_at.desc())
        .limit(20)
        .all()
    )


@crowd_bp.get("/")
@login_required
def index():
    return render_template(
        "detection/crowd.html",
        status=_detector_status(),
        incidents=_recent_incidents(),
        cameras=Camera.query.filter(Camera.is_active.is_(True)).order_by(Camera.name).all(),
    )


@crowd_bp.route("/run", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def run():
    camera_id = request.args.get("camera_id") or request.form.get("camera_id", type=int)
    camera = db.get_or_404(Camera, camera_id) if camera_id else None
    if not camera:
        flash("Select a valid camera.", "warning")
        return redirect(url_for("crowd.index"))
    if not crowd_detector.available:
        flash("Crowd analyser unavailable — install YOLO and place crowd.pt in ai/weights/.", "danger")
        return redirect(url_for("crowd.index"))
    from ai.service import run_detection
    result = run_detection(camera, detector_name="crowd")
    if result["status"] == "ok":
        n = result["incidents_created"]
        flash(f"Analysis complete — {n} incident(s) created.", "success" if n else "info")
    else:
        flash(f"Detection failed: {result['status']}.", "danger")
    return redirect(url_for("crowd.index"))
