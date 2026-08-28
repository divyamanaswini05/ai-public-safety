"""Weapon detection routes — Module 11.

Surfaces detector status, recent weapon incidents and a one-shot
manual run control.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models import Camera, Incident
from models.enums import IncidentType, RoleSlug, SeverityLevel
from ai.detectors_weapon import weapon_detector
from ai.weights import model_path, weights_dir
from utils.decorators import role_required

weapon_bp = Blueprint("weapon", __name__, url_prefix="/detection/weapon")

MANAGE_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)


def _detector_status() -> dict:
    return {
        "name": weapon_detector.name,
        "yolo_installed": weapon_detector.yolo_installed,
        "weights_present": weapon_detector.weights_present,
        "weights_path": model_path("weapon") or f"{weights_dir()}\\weapon.pt",
        "available": weapon_detector.available,
    }


def _recent_incidents() -> list[Incident]:
    return (
        Incident.query
        .filter(Incident.incident_type == IncidentType.WEAPON)
        .order_by(Incident.detected_at.desc())
        .limit(20)
        .all()
    )


@weapon_bp.get("/")
@login_required
def index():
    return render_template(
        "detection/weapon.html",
        status=_detector_status(),
        incidents=_recent_incidents(),
        cameras=Camera.query.filter(Camera.is_active.is_(True)).order_by(Camera.name).all(),
    )


@weapon_bp.route("/run", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def run():
    camera_id = request.args.get("camera_id") or request.form.get("camera_id", type=int)
    camera = db.get_or_404(Camera, camera_id) if camera_id else None
    if not camera:
        flash("Select a valid camera.", "warning")
        return redirect(url_for("weapon.index"))
    if not weapon_detector.available:
        flash("Weapon detector unavailable — install YOLO and place weapon.pt in ai/weights/.", "danger")
        return redirect(url_for("weapon.index"))
    from ai.service import run_detection
    result = run_detection(camera, detector_name="weapon")
    if result["status"] == "ok":
        n = result["incidents_created"]
        flash(f"Analysis complete — {n} incident(s) created.", "success" if n else "info")
    else:
        flash(f"Detection failed: {result['status']}.", "danger")
    return redirect(url_for("weapon.index"))
