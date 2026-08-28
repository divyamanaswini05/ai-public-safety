"""Secure, signed, expiring tokens built on itsdangerous.

Used for email verification and password-reset links. Payloads are signed
with the application SECRET_KEY, so they cannot be forged or modified.
"""

from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(payload: dict[str, Any], salt: str) -> str:
    """Create a signed token carrying the given payload."""
    return _serializer().dumps(payload, salt=salt)


def verify_token(token: str, salt: str, max_age_seconds: int) -> dict[str, Any] | None:
    """Validate a token; returns the payload or None if invalid/expired."""
    try:
        return _serializer().loads(token, salt=salt, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
