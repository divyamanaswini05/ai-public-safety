"""Fernet encryption for camera stream credentials.

RTSP/IP camera passwords are never stored in plaintext. A ``FERNET_KEY``
config value is preferred; otherwise a stable key is derived from the
application ``SECRET_KEY`` so no extra deployment step is required.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet() -> Fernet:
    """Build the Fernet cipher from configuration."""
    configured = current_app.config.get("FERNET_KEY")
    if configured:
        key = configured.encode("utf-8")
    else:
        digest = hashlib.sha256(
            current_app.config["SECRET_KEY"].encode("utf-8")
        ).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret (e.g. an RTSP password)."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str | None) -> str | None:
    """Decrypt a stored secret, returning None when absent or unreadable."""
    if not encrypted:
        return None
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        current_app.logger.warning("Could not decrypt a stored camera credential")
        return None
