"""Fire & smoke detection routes — Module 10.

Surfaces detector status, recent fire/smoke incidents and a one-shot
manual run control.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models import Camera, Incident
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from services import incident_service
from ai.detectors_fire_smoke import fire_smoke_detector
from ai.weights import model_path, weights_dir
from utils.decorators import role_required

fire_smoke_bp = Blueprint("fire_smoke", __name__, url_prefix="/detection/fire")

MANAGE_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)


def _detector_status() -> dict:
    return {
        "name": fire_smoke_detector.name,
        "yolo_installed": fire_smoke_detector.yolo_installed,
        "weights_present": fire_smoke_detector.weights_present,
        "weights_path": model_path("fire") or f"{weights_dir()}\\fire-smoke.pt",
        "available": fire_smoke_detector.available,
    }


def _recent_incidents() -> list[Incident]:
    return (
        Incident.query
        .filter(Incident.incident_type.in_([IncidentType.FIRE, IncidentType.SMOKE]))
        .order_by(Incident.detected_at.desc())
        .limit(20)
        .all()
    )


@fire_smoke_bp.get("/")
@login_required
def index():
    return render_template(
        "detection/fire.html",
        status=_detector_status(),
        incidents=_recent_incidents(),
        cameras=Camera.query.filter(Camera.is_active.is_(True)).order_by(Camera.name).all(),
        Incident=Incident,
    )


@fire_smoke_bp.route("/run", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def run():
    camera_id = request.args.get("camera_id") or request.form.get("camera_id", type=int)
    camera = db.get_or_404(Camera, camera_id) if camera_id else None
    if not camera:
        flash("Select a valid camera.", "warning")
        return redirect(url_for("fire_smoke.index"))
    if not fire_smoke_detector.available:
        flash("Fire/smoke detector unavailable — install YOLO and place fire-smoke.pt in ai/weights/.", "danger")
        return redirect(url_for("fire_smoke.index"))
    from ai.service import run_detection
    result = run_detection(camera, detector_name="fire_smoke")
    if result["status"] == "ok":
        n = result["incidents_created"]
        flash(f"Analysis complete — {n} incident(s) created.", "success" if n else "info")
    else:
        flash(f"Detection failed: {result['status']}.", "danger")
    return redirect(url_for("fire_smoke.index"))
