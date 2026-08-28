"""WTForms for evidence uploads."""

from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileSize
from wtforms import HiddenField, SelectField, SubmitField
from wtforms.validators import DataRequired, ValidationError

from extensions import db
from models import Incident
from models.enums import EvidenceType


class EvidenceUploadForm(FlaskForm):
    """Upload a piece of evidence linked to an incident."""

    incident_id = HiddenField("Incident", validators=[DataRequired()])
    evidence_type = SelectField(
        "Type",
        choices=[(e.value, e.value.title()) for e in EvidenceType],
        validators=[DataRequired()],
    )
    file = FileField(
        "File",
        validators=[
            FileRequired(),
            FileSize(max_size=50 * 1024 * 1024),
        ],
    )
    submit = SubmitField("Upload")

    def validate_incident_id(self, field) -> None:
        try:
            iid = int(field.data)
        except (TypeError, ValueError):
            raise ValidationError("Invalid incident.") from None
        if db.session.get(Incident, iid) is None:
            raise ValidationError("Incident not found.")
