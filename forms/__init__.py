"""WTForms classes used across the application."""

from forms.auth_forms import (
    ForgotPasswordForm,
    LoginForm,
    RegisterForm,
    ResetPasswordForm,
)
from forms.camera_forms import CameraForm
from forms.evidence_forms import EvidenceUploadForm
from forms.incident_forms import IncidentForm

__all__ = [
    "CameraForm",
    "EvidenceUploadForm",
    "ForgotPasswordForm",
    "IncidentForm",
    "LoginForm",
    "RegisterForm",
    "ResetPasswordForm",
]
