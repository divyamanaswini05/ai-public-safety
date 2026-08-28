"""WTForms for the authentication flows."""

import re

from email_validator import EmailNotValidError, validate_email
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from models import User

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
EMAIL_STRUCTURE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def strong_password(_form, field) -> None:
    """Require a minimum complexity: length, case and a digit."""
    value = field.data or ""
    checks = {
        "at least 8 characters": len(value) >= 8,
        "an uppercase letter": any(char.isupper() for char in value),
        "a lowercase letter": any(char.islower() for char in value),
        "a number": any(char.isdigit() for char in value),
    }
    missing = [label for label, ok in checks.items() if not ok]
    if missing:
        raise ValidationError(
            "Password must include " + " and ".join(missing) + "."
        )


def unique_username(_form, field) -> None:
    """Reject usernames that are already registered."""
    if User.query.filter_by(username=field.data).first() is not None:
        raise ValidationError("This username is already taken.")


def unique_email(_form, field) -> None:
    """Reject emails that are already registered."""
    if User.query.filter_by(email=field.data).first() is not None:
        raise ValidationError("An account with this email already exists.")


def valid_email(_form, field) -> None:
    """Check email syntax without DNS lookups.

    Reserved/internal TLDs (e.g. ``*.local`` used on air-gapped networks)
    fall back to a structural check so offline deployments stay usable.
    """
    value = (field.data or "").strip()
    try:
        validate_email(value, check_deliverability=False, test_environment=True)
    except EmailNotValidError:
        if EMAIL_STRUCTURE.fullmatch(value) is None:
            raise ValidationError("Enter a valid email address.")


class RegisterForm(FlaskForm):
    """New account creation."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=64),
            Regexp(USERNAME_PATTERN, message="Only letters, numbers and underscores are allowed."),
            unique_username,
        ],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), valid_email, unique_email],
    )
    first_name = StringField("First name", validators=[Optional(), Length(max=64)])
    last_name = StringField("Last name", validators=[Optional(), Length(max=64)])
    password = PasswordField(
        "Password",
        validators=[DataRequired(), strong_password],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    """Sign-in with email or username."""

    identity = StringField("Email or username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign In")


class ForgotPasswordForm(FlaskForm):
    """Request a password reset link."""

    email = StringField("Email", validators=[DataRequired(), valid_email])
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    """Choose a new password using a reset token."""

    password = PasswordField(
        "New password",
        validators=[DataRequired(), strong_password],
    )
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset Password")
