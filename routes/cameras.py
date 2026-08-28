"""Camera management routes — list, add, edit, delete and health checks."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from forms import CameraForm
from models import Camera
from models.enums import CameraStatus, RoleSlug
from services import camera_service
from utils.decorators import role_required

cameras_bp = Blueprint("cameras", __name__, url_prefix="/cameras")

MANAGE_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)

STATUS_CHOICES = {status.value for status in CameraStatus}


@cameras_bp.get("/")
@login_required
def index():
    """List every camera with its health summary."""
    cameras = Camera.query.order_by(Camera.created_at.desc()).all()
    return render_template("cameras/index.html", cameras=cameras)


@cameras_bp.route("/new", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def new():
    """Add a new camera."""
    form = CameraForm()
    if form.validate_on_submit():
        camera = camera_service.create_camera(
            name=form.name.data.strip(),
            location=form.location.data.strip() or None,
            source_type=form.source_type.data,
            source_url=form.source_url.data.strip() or None,
            ip_address=form.ip_address.data.strip() or None,
            port=form.port.data,
            username=form.username.data.strip() or None,
            password=form.password.data or None,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
        )
        flash(f"Camera '{camera.name}' added.", "success")
        return redirect(url_for("cameras.detail", camera_id=camera.id))
    return render_template(
        "cameras/form.html", form=form, camera=None, title="Add Camera"
    )


@cameras_bp.get("/<int:camera_id>")
@login_required
def detail(camera_id: int):
    """Show a single camera's configuration and health."""
    camera = db.get_or_404(Camera, camera_id)
    return render_template(
        "cameras/detail.html",
        camera=camera,
        has_credentials=bool(camera.password_encrypted),
    )


@cameras_bp.route("/<int:camera_id>/edit", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def edit(camera_id: int):
    """Update an existing camera."""
    camera = db.get_or_404(Camera, camera_id)
    form = CameraForm(
        camera=camera,
        data={
            "name": camera.name,
            "location": camera.location or "",
            "source_type": camera.source_type.value,
            "source_url": camera.source_url or "",
            "ip_address": camera.ip_address or "",
            "port": camera.port,
            "username": camera.username or "",
            "latitude": camera.latitude,
            "longitude": camera.longitude,
        },
    )
    if form.validate_on_submit():
        camera_service.update_camera(
            camera,
            name=form.name.data.strip(),
            location=form.location.data.strip() or None,
            source_type=form.source_type.data,
            source_url=form.source_url.data.strip() or None,
            ip_address=form.ip_address.data.strip() or None,
            port=form.port.data,
            username=form.username.data.strip() or None,
            password=form.password.data or None,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
        )
        flash(f"Camera '{camera.name}' updated.", "success")
        return redirect(url_for("cameras.detail", camera_id=camera.id))
    return render_template(
        "cameras/form.html",
        form=form,
        camera=camera,
        title=f"Edit Camera — {camera.name}",
    )


@cameras_bp.post("/<int:camera_id>/delete")
@role_required(*MANAGE_ROLES)
def delete(camera_id: int):
    """Remove a camera permanently."""
    camera = db.get_or_404(Camera, camera_id)
    camera_service.delete_camera(camera)
    flash(f"Camera '{camera.name}' deleted.", "info")
    return redirect(url_for("cameras.index"))


@cameras_bp.post("/<int:camera_id>/status")
@role_required(*MANAGE_ROLES)
def status(camera_id: int):
    """Set a camera's operational status (online / offline / disabled)."""
    camera = db.get_or_404(Camera, camera_id)
    new_status = request.form.get("status", "")
    if new_status not in STATUS_CHOICES:
        flash("Invalid status.", "danger")
        return redirect(url_for("cameras.detail", camera_id=camera_id))
    camera_service.set_status(camera, CameraStatus(new_status))
    flash(f"Camera '{camera.name}' marked {new_status}.", "success")
    return redirect(url_for("cameras.detail", camera_id=camera_id))


@cameras_bp.post("/<int:camera_id>/check")
@role_required(*MANAGE_ROLES)
def check(camera_id: int):
    """Run a connectivity probe and refresh the camera's health."""
    camera = db.get_or_404(Camera, camera_id)
    reachable = camera_service.probe_connection(camera)
    if reachable is None:
        flash(
            "This camera cannot be probed over the network (webcam or no endpoint).",
            "warning",
        )
    elif reachable:
        flash(f"Camera '{camera.name}' is reachable.", "success")
    else:
        flash(f"Camera '{camera.name}' is unreachable.", "danger")
    return redirect(url_for("cameras.detail", camera_id=camera_id))
