"""WTForms for incident management."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from extensions import db
from models import Camera
from models.enums import IncidentType, SeverityLevel

NO_CAMERA = 0


class IncidentForm(FlaskForm):
    """Create or edit an incident."""

    title = StringField(
        "Title",
        validators=[DataRequired(), Length(min=3, max=255)],
    )
    incident_type = SelectField(
        "Type",
        choices=[(t.value, t.value.title()) for t in IncidentType],
        validators=[DataRequired()],
    )
    severity = SelectField(
        "Severity",
        choices=[(s.value, s.value.title()) for s in SeverityLevel],
        validators=[DataRequired()],
    )
    camera_id = SelectField(
        "Camera",
        coerce=int,
        choices=[(NO_CAMERA, "No camera")],
        validators=[Optional()],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=5000)],
    )
    submit = SubmitField("Save Incident")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cameras = Camera.query.order_by(Camera.name).all()
        self.camera_id.choices = [(NO_CAMERA, "No camera")] + [
            (camera.id, camera.name) for camera in cameras
        ]

    def validate_camera_id(self, field) -> None:
        """Reject cameras that no longer exist."""
        if field.data and field.data != NO_CAMERA:
            if db.session.get(Camera, field.data) is None:
                raise ValidationError("Select a valid camera.")
