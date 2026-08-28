"""Incident routes — list, report, review and manage incidents."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import IncidentForm
from models import Camera, Incident
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from services import incident_service
from utils.decorators import role_required

incidents_bp = Blueprint("incidents", __name__, url_prefix="/incidents")

MANAGE_ROLES = (
    RoleSlug.ADMIN.value,
    RoleSlug.OPERATOR.value,
    RoleSlug.ANALYST.value,
)
DELETE_ROLES = (RoleSlug.ADMIN.value,)

STATUS_VALUES = {status.value for status in IncidentStatus}


@incidents_bp.get("/")
@login_required
def index():
    """List incidents, optionally filtered by status/severity/type/camera."""
    filters = {
        "status": request.args.get("status") or None,
        "severity": request.args.get("severity") or None,
        "incident_type": request.args.get("type") or None,
        "camera_id": request.args.get("camera_id", type=int),
        "search": request.args.get("q") or None,
    }
    return render_template(
        "incidents/index.html",
        incidents=incident_service.list_incidents(**filters),
        filters=filters,
        counts=incident_service.get_incident_counts(),
        cameras=Camera.query.order_by(Camera.name).all(),
        statuses=IncidentStatus,
        severities=SeverityLevel,
        types=IncidentType,
    )


@incidents_bp.route("/new", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def new():
    """Report a new incident manually."""
    form = IncidentForm()
    if form.validate_on_submit():
        incident = incident_service.create_incident(
            title=form.title.data.strip(),
            incident_type=IncidentType(form.incident_type.data),
            severity=SeverityLevel(form.severity.data),
            camera_id=form.camera_id.data or None,
            description=(
                form.description.data.strip() if form.description.data else None
            ),
            created_by=current_user.id,
        )
        flash(f"Incident '{incident.title}' reported.", "success")
        return redirect(url_for("incidents.detail", incident_id=incident.id))
    return render_template(
        "incidents/form.html", form=form, incident=None, title="Report Incident"
    )


@incidents_bp.get("/<int:incident_id>")
@login_required
def detail(incident_id: int):
    """Show a single incident with its alerts and evidence."""
    incident = db.get_or_404(Incident, incident_id)
    return render_template("incidents/detail.html", incident=incident)


@incidents_bp.route("/<int:incident_id>/edit", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def edit(incident_id: int):
    """Update an incident's classification and notes."""
    incident = db.get_or_404(Incident, incident_id)
    form = IncidentForm(
        data={
            "title": incident.title,
            "incident_type": incident.incident_type.value,
            "severity": incident.severity.value,
            "camera_id": incident.camera_id or 0,
            "description": incident.description or "",
        }
    )
    if form.validate_on_submit():
        incident_service.update_incident(
            incident,
            title=form.title.data.strip(),
            incident_type=IncidentType(form.incident_type.data),
            severity=SeverityLevel(form.severity.data),
            description=(
                form.description.data.strip() if form.description.data else None
            ),
        )
        flash(f"Incident '{incident.title}' updated.", "success")
        return redirect(url_for("incidents.detail", incident_id=incident.id))
    return render_template(
        "incidents/form.html",
        form=form,
        incident=incident,
        title=f"Edit Incident — {incident.title}",
    )


@incidents_bp.post("/<int:incident_id>/status")
@role_required(*MANAGE_ROLES)
def status(incident_id: int):
    """Move an incident through its lifecycle."""
    incident = db.get_or_404(Incident, incident_id)
    new_status = request.form.get("status", "")
    if new_status not in STATUS_VALUES:
        flash("Invalid status.", "danger")
        return redirect(url_for("incidents.detail", incident_id=incident_id))
    incident_service.set_status(incident, IncidentStatus(new_status))
    flash(f"Incident marked {new_status}.", "success")
    return redirect(url_for("incidents.detail", incident_id=incident_id))


@incidents_bp.post("/<int:incident_id>/delete")
@role_required(*DELETE_ROLES)
def delete(incident_id: int):
    """Remove an incident permanently (administrators only)."""
    incident = db.get_or_404(Incident, incident_id)
    incident_service.delete_incident(incident)
    flash(f"Incident '{incident.title}' deleted.", "info")
    return redirect(url_for("incidents.index"))
