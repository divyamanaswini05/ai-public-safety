"""Alert management business logic — listing, status flow and acknowledgement."""

from __future__ import annotations

from sqlalchemy import func

from extensions import db
from models import Alert
from models.base import utcnow
from models.enums import AlertPriority, AlertStatus, AlertType
from services.audit_service import audit


def _enum_value(cls, value: str):
    if value is None:
        return None
    try:
        return cls(value)
    except ValueError:
        return None


def list_alerts(
    status: str | None = None,
    priority: str | None = None,
    alert_type: str | None = None,
    incident_id: int | None = None,
    search: str | None = None,
) -> list[Alert]:
    """Query alerts newest-first with optional filters."""
    query = Alert.query

    status_enum = _enum_value(AlertStatus, status)
    if status_enum is not None:
        query = query.filter(Alert.status == status_enum)

    priority_enum = _enum_value(AlertPriority, priority)
    if priority_enum is not None:
        query = query.filter(Alert.priority == priority_enum)

    type_enum = _enum_value(AlertType, alert_type)
    if type_enum is not None:
        query = query.filter(Alert.alert_type == type_enum)

    if incident_id:
        query = query.filter(Alert.incident_id == incident_id)

    if search and search.strip():
        query = query.filter(Alert.title.ilike(f"%{search.strip()}%"))

    return query.order_by(Alert.created_at.desc()).all()


def get_alert_counts() -> dict[str, int]:
    """Total alerts per status value."""
    counts = dict.fromkeys((s.value for s in AlertStatus), 0)
    rows = (
        db.session.query(Alert.status, func.count())
        .group_by(Alert.status)
        .all()
    )
    for status, total in rows:
        counts[status.value] = total
    return counts


def mark_sent(alert: Alert) -> Alert:
    """Transition an alert to the sent state."""
    alert.mark_sent()
    db.session.flush()
    audit(
        action="alert.send",
        module="alerts",
        message=f"Alert '{alert.title}' marked sent",
        details={"alert_id": alert.id, "incident_id": alert.incident_id},
    )
    return alert


def acknowledge(alert: Alert, user_id: int) -> Alert:
    """Record that an operator has seen and handled this alert."""
    alert.acknowledge()
    alert.acknowledged_by = user_id
    db.session.flush()
    audit(
        action="alert.acknowledge",
        module="alerts",
        message=f"Alert '{alert.title}' acknowledged",
        details={"alert_id": alert.id, "user_id": user_id},
    )
    return alert


def expire(alert: Alert) -> Alert:
    """Mark an alert as expired (e.g. timed out without response)."""
    alert.status = AlertStatus.EXPIRED
    db.session.flush()
    audit(
        action="alert.expire",
        module="alerts",
        message=f"Alert '{alert.title}' expired",
        details={"alert_id": alert.id},
    )
    return alert
