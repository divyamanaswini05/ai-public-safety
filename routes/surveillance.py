"""Live surveillance routes — camera grid, single feed and status polling."""

from flask import Blueprint, jsonify, render_template
from flask_login import login_required

from extensions import db
from models import Camera
from services import surveillance_service

surveillance_bp = Blueprint(
    "surveillance", __name__, url_prefix="/surveillance"
)

COUNT_FIELDS = ("online", "offline", "disabled")


@surveillance_bp.get("/")
@login_required
def index():
    """Render the live surveillance grid for signed-in users."""
    cameras = surveillance_service.get_surveillance_cameras()
    counts = {field: 0 for field in COUNT_FIELDS}
    for camera in cameras:
        if camera.status.value in counts:
            counts[camera.status.value] += 1
    return render_template(
        "surveillance/index.html",
        cameras=cameras,
        counts=counts,
        total=len(cameras),
    )


@surveillance_bp.get("/status")
@login_required
def status():
    """JSON snapshot of every active camera's health for client polling."""
    return jsonify({"cameras": surveillance_service.get_status_snapshot()})


@surveillance_bp.get("/feed/<int:camera_id>")
@login_required
def feed(camera_id: int):
    """Dedicated live view for a single camera."""
    camera = db.get_or_404(Camera, camera_id)
    return render_template(
        "surveillance/feed.html",
        camera=camera,
        incidents=surveillance_service.get_camera_incidents(camera),
    )
