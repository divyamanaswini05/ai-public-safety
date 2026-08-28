"""Evidence routes — list, upload, view and delete."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models import Evidence, Incident
from models.enums import RoleSlug
from forms import EvidenceUploadForm
from services import evidence_service
from utils.decorators import role_required

evidence_bp = Blueprint("evidence", __name__, url_prefix="/evidence")

MANAGE_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)
DELETE_ROLES = (RoleSlug.ADMIN.value,)


@evidence_bp.get("/")
@login_required
def index():
    incident_id = request.args.get("incident_id", type=int)
    evidence_type = request.args.get("type") or None
    return render_template(
        "evidence/index.html",
        evidence_items=evidence_service.list_evidence(
            incident_id=incident_id, evidence_type=evidence_type
        ),
        incidents=Incident.query.order_by(Incident.detected_at.desc()).all(),
        filters={"incident_id": incident_id, "evidence_type": evidence_type},
    )


@evidence_bp.route("/upload", methods=["GET", "POST"])
@role_required(*MANAGE_ROLES)
def upload():
    form = EvidenceUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        evidence = evidence_service.create_evidence(
            incident_id=int(form.incident_id.data),
            evidence_type=form.evidence_type.data,
            file_name=file.filename or "upload",
            file_content=file.read(),
            mime_type=file.content_type,
        )
        flash(f"Evidence '{evidence.file_name}' uploaded.", "success")
        return redirect(url_for("evidence.detail", evidence_id=evidence.id))
    preselect = request.args.get("incident_id", type=int)
    return render_template(
        "evidence/upload.html",
        form=form,
        incidents=Incident.query.order_by(Incident.detected_at.desc()).all(),
        preselect_incident_id=preselect,
    )


@evidence_bp.get("/<int:evidence_id>")
@login_required
def detail(evidence_id: int):
    evidence = db.get_or_404(Evidence, evidence_id)
    return render_template("evidence/detail.html", evidence=evidence)


@evidence_bp.post("/<int:evidence_id>/delete")
@role_required(*DELETE_ROLES)
def delete(evidence_id: int):
    evidence = db.get_or_404(Evidence, evidence_id)
    incident_id = evidence.incident_id
    evidence_service.delete_evidence(evidence)
    flash("Evidence deleted.", "info")
    return redirect(url_for("evidence.index", incident_id=incident_id))
