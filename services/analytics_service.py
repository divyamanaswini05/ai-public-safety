"""Analytics service — aggregated statistics and chart data."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, case

from extensions import db
from models import Alert, Camera, Evidence, Incident, User
from models.enums import (
    AlertPriority,
    AlertStatus,
    IncidentStatus,
    IncidentType,
    SeverityLevel,
)
from models.base import utcnow


def overview() -> dict:
    """High-level counts for the stats cards."""
    return {
        "cameras": db.session.query(func.count()).select_from(Camera).scalar(),
        "incidents": db.session.query(func.count()).select_from(Incident).scalar(),
        "alerts": db.session.query(func.count()).select_from(Alert).scalar(),
        "evidence": db.session.query(func.count()).select_from(Evidence).scalar(),
        "users": db.session.query(func.count()).select_from(User).scalar(),
    }


def incidents_by_type() -> dict[str, int]:
    rows = (
        db.session.query(Incident.incident_type, func.count())
        .group_by(Incident.incident_type)
        .all()
    )
    return {t.value: c for t, c in rows}


def incidents_by_severity() -> dict[str, int]:
    rows = (
        db.session.query(Incident.severity, func.count())
        .group_by(Incident.severity)
        .all()
    )
    return {s.value: c for s, c in rows}


def incidents_by_status() -> dict[str, int]:
    rows = (
        db.session.query(Incident.status, func.count())
        .group_by(Incident.status)
        .all()
    )
    return {s.value: c for s, c in rows}


def alerts_by_priority() -> dict[str, int]:
    rows = (
        db.session.query(Alert.priority, func.count())
        .group_by(Alert.priority)
        .all()
    )
    return {p.value: c for p, c in rows}


def alerts_by_status() -> dict[str, int]:
    rows = (
        db.session.query(Alert.status, func.count())
        .group_by(Alert.status)
        .all()
    )
    return {s.value: c for s, c in rows}


def incidents_last_7_days() -> dict[str, int]:
    """Incident count per day for the past 7 days (oldest-first)."""
    now = utcnow()
    start = now - timedelta(days=6)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.session.query(
            func.date(Incident.detected_at).label("day"),
            func.count(),
        )
        .filter(Incident.detected_at >= start)
        .group_by(func.date(Incident.detected_at))
        .order_by(func.date(Incident.detected_at))
        .all()
    )
    mapping = {str(day): cnt for day, cnt in rows}
    result = {}
    for i in range(7):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        result[d] = mapping.get(d, 0)
    return result
