"""Authentication business logic — kept separate from the route handlers."""

from typing import Any

from flask import current_app, render_template, url_for
from sqlalchemy import func, or_

from extensions import db
from models import Role, User
from models.base import utcnow
from models.enums import LogLevel
from services.audit_service import audit
from services.mail_service import send_email
from utils.tokens import generate_token, verify_token

VERIFY_SALT = "email-verification"
RESET_SALT = "password-reset"
VERIFY_MAX_AGE_SECONDS = 24 * 3600  # verification links expire after 24h
RESET_MAX_AGE_SECONDS = 1 * 3600  # reset links expire after 1h


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------
def verification_token_for(user: User) -> str:
    """Return a signed token used to confirm a user's email."""
    return generate_token({"user_id": user.id, "email": user.email}, VERIFY_SALT)


def reset_token_for(user: User) -> str:
    """Return a signed token used to reset a user's password."""
    return generate_token({"user_id": user.id, "email": user.email}, RESET_SALT)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_user(
    username: str,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
    role_slug: str = "viewer",
) -> User:
    """Create an account, dispatch the verification email and audit it."""
    role = Role.query.filter_by(slug=role_slug).first()
    if role is None:
        # Self-healing: create the role if seeding has not run yet.
        role = Role(
            name=role_slug.title(),
            slug=role_slug,
            description=f"Auto-created {role_slug} role",
        )
        db.session.add(role)
        db.session.flush()

    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
        is_verified=False,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    audit(
        "auth.register",
        module="auth",
        message=f"New account registered: {user.email}",
        details={"username": user.username},
    )
    send_verification_email(user)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def authenticate(identity: str, password: str) -> tuple[User | None, str | None]:
    """Validate credentials. Returns (user, None) or (None, error message)."""
    lookup = identity.strip()
    user = User.query.filter(
        or_(
            User.username == lookup,
            func.lower(User.email) == lookup.lower(),
        )
    ).first()

    if user is None:
        return None, "Invalid email/username or password."

    if not user.is_active:
        return None, "This account has been disabled."

    if user.is_locked():
        return None, "Account temporarily locked due to repeated failed attempts."

    if not user.check_password(password):
        user.record_failed_login()
        db.session.commit()
        audit(
            "auth.login.failed",
            module="auth",
            level=LogLevel.WARNING,
            message=f"Failed login attempt for {user.email}",
            details={"attempt": user.failed_login_attempts},
        )
        if user.is_locked():
            return None, "Account locked after repeated failed attempts."
        return None, "Invalid email/username or password."

    user.record_login()
    db.session.commit()
    audit(
        "auth.login.success",
        module="auth",
        message=f"User signed in: {user.email}",
        details={"method": "password"},
    )
    return user, None


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
def send_verification_email(user: User) -> str:
    """Send the verification email; returns the generated link (for dev logs)."""
    token = verification_token_for(user)
    link = url_for("auth.verify_email", token=token, _external=True)
    ok = send_email(
        subject="Verify your SentinelAI account",
        recipients=[user.email],
        text_body=render_template("emails/verify_email.txt", user=user, link=link),
        html_body=render_template("emails/verify_email.html", user=user, link=link),
    )
    if not ok:
        # Development fallback so the flow remains testable without SMTP.
        current_app.logger.warning(
            "Verification email not sent; link for %s: %s", user.email, link
        )
    return link


def verify_email_token(token: str) -> User | None:
    """Resolve a verification token to its user, or None if invalid."""
    data = verify_token(token, VERIFY_SALT, VERIFY_MAX_AGE_SECONDS)
    if data is None:
        return None
    user = db.session.get(User, data.get("user_id"))
    if user is None or user.email != data.get("email"):
        return None
    return user


def confirm_user_email(user: User) -> None:
    """Mark a user's email as verified."""
    user.is_verified = True
    user.email_verified_at = utcnow()
    db.session.commit()
    audit(
        "auth.verify_email",
        module="auth",
        message=f"Email verified: {user.email}",
    )


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def send_password_reset(user: User) -> str:
    """Send the reset email; returns the generated link (for dev logs)."""
    token = reset_token_for(user)
    link = url_for("auth.reset_password", token=token, _external=True)
    ok = send_email(
        subject="Reset your SentinelAI password",
        recipients=[user.email],
        text_body=render_template("emails/reset_password.txt", user=user, link=link),
        html_body=render_template("emails/reset_password.html", user=user, link=link),
    )
    if not ok:
        current_app.logger.warning(
            "Reset email not sent; link for %s: %s", user.email, link
        )
    return link


def validate_reset_token(token: str) -> User | None:
    """Resolve a reset token to its user, or None if invalid/expired."""
    data = verify_token(token, RESET_SALT, RESET_MAX_AGE_SECONDS)
    if data is None:
        return None
    user = db.session.get(User, data.get("user_id"))
    if user is None or user.email != data.get("email"):
        return None
    return user


def reset_password(user: User, new_password: str) -> None:
    """Apply a new password and clear lockout state."""
    user.set_password(new_password)
    user.reset_failed_logins()
    db.session.commit()
    audit(
        "auth.password.reset",
        module="auth",
        level=LogLevel.INFO,
        message=f"Password reset for {user.email}",
    )
