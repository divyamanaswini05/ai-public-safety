"""Audit trail helper — records security-relevant actions."""

from typing import Any

from flask import request
from flask_login import current_user

from extensions import db
from models import AuditLog
from models.enums import LogLevel


def _resolve_user_id() -> int | None:
    """Return the signed-in user id, or None outside a request context."""
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        return None
    return None


def _request_meta() -> tuple[str | None, str | None]:
    """Extract client IP and user-agent from the current request, if any."""
    try:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.remote_addr
        user_agent = str(request.user_agent)[:255] if request.user_agent else None
        return ip_address, user_agent
    except Exception:
        return None, None


def audit(
    action: str,
    module: str | None = None,
    message: str = "",
    level: LogLevel = LogLevel.INFO,
    details: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> AuditLog:
    """Persist an audit entry, resolving user/IP metadata when available."""
    ip_address, user_agent = _request_meta()
    resolved_user = user_id if user_id is not None else _resolve_user_id()
    entry = AuditLog(
        action=action,
        module=module,
        level=level,
        message=message,
        details=details or {},
        user_id=resolved_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
