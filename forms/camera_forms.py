"""WTForms for camera management."""

from __future__ import annotations

import ipaddress
import re

from flask_wtf import FlaskForm
from wtforms import (
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from models import Camera
from models.enums import CameraSource

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-\.]*$")


class CameraForm(FlaskForm):
    """Create or edit a camera."""

    name = StringField(
        "Name",
        validators=[
            DataRequired(),
            Length(min=2, max=128),
            Regexp(
                NAME_PATTERN,
                message="Use letters, numbers, spaces, dots, dashes or underscores.",
            ),
        ],
    )
    location = StringField("Location", validators=[Optional(), Length(max=255)])
    source_type = SelectField(
        "Source type",
        choices=[(source.value, source.value.upper()) for source in CameraSource],
        validators=[DataRequired()],
    )
    source_url = StringField(
        "Stream URL (RTSP)",
        validators=[Optional(), Length(max=500)],
        description="e.g. rtsp://host:554/stream — used when no IP/port is given",
    )
    ip_address = StringField(
        "IP address", validators=[Optional(), Length(max=64)]
    )
    port = IntegerField(
        "Port", validators=[Optional(), NumberRange(min=1, max=65535)]
    )
    username = StringField("Username", validators=[Optional(), Length(max=128)])
    password = PasswordField(
        "Password", validators=[Optional(), Length(max=256)]
    )
    latitude = FloatField(
        "Latitude", validators=[Optional(), NumberRange(min=-90, max=90)]
    )
    longitude = FloatField(
        "Longitude", validators=[Optional(), NumberRange(min=-180, max=180)]
    )
    submit = SubmitField("Save Camera")

    def __init__(self, *args, camera: Camera | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._camera = camera

    def validate_name(self, field) -> None:
        """Reject duplicate names, ignoring the camera being edited."""
        query = Camera.query.filter_by(name=field.data.strip())
        if self._camera is not None:
            query = query.filter(Camera.id != self._camera.id)
        if query.first() is not None:
            raise ValidationError("A camera with this name already exists.")

    def validate_ip_address(self, field) -> None:
        """Reject malformed IP literals when an address is supplied."""
        value = (field.data or "").strip()
        if not value:
            return
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValidationError("Enter a valid IP address.") from None

    def validate(self, extra_validators=None) -> bool:
        """Enforce that non-webcam sources have a resolvable endpoint."""
        if not super().validate(extra_validators):
            return False
        if self.source_type.data == CameraSource.WEBCAM.value:
            return True
        if not (self.ip_address.data or "").strip() and not (
            self.source_url.data or ""
        ).strip():
            self.source_url.errors.append(
                "Provide an IP address or stream URL for this source type."
            )
            return False
        return True
