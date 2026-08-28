"""Dashboard aggregations — KPIs, chart series and recent activity feeds."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func

from extensions import db
from models import Alert, AuditLog, Camera, Incident, User
from models.base import utcnow
from models.enums import (
    AlertPriority,
    AlertStatus,
    CameraStatus,
    IncidentStatus,
)

TREND_DAYS = 14


def get_kpis() -> dict:
    """Return the headline numbers shown on the dashboard stat cards."""
    incidents_active = Incident.query.filter(
        Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING])
    ).count()
    alerts_unhandled = Alert.query.filter(
        Alert.status.in_([AlertStatus.PENDING, AlertStatus.SENT])
    ).count()
    alerts_critical = Alert.query.filter(
        Alert.priority == AlertPriority.CRITICAL,
        Alert.status.in_([AlertStatus.PENDING, AlertStatus.SENT]),
    ).count()

    return {
        "cameras": {
            "total": Camera.query.count(),
            "online": Camera.query.filter_by(status=CameraStatus.ONLINE).count(),
            "offline": Camera.query.filter_by(status=CameraStatus.OFFLINE).count(),
            "disabled": Camera.query.filter_by(status=CameraStatus.DISABLED).count(),
        },
        "incidents": {
            "open": Incident.query.filter_by(status=IncidentStatus.OPEN).count(),
            "active": incidents_active,
            "resolved": Incident.query.filter_by(
                status=IncidentStatus.RESOLVED
            ).count(),
            "total": Incident.query.count(),
        },
        "alerts": {
            "pending": Alert.query.filter_by(status=AlertStatus.PENDING).count(),
            "unhandled": alerts_unhandled,
            "critical": alerts_critical,
            "acknowledged": Alert.query.filter_by(
                status=AlertStatus.ACKNOWLEDGED
            ).count(),
            "total": Alert.query.count(),
        },
        "users": {
            "total": User.query.count(),
            "active": User.query.filter_by(is_active=True).count(),
            "verified": User.query.filter_by(is_verified=True).count(),
        },
    }


def _daily_trend(model, column, days: int = TREND_DAYS) -> tuple[list[str], list[int]]:
    """Build (labels, counts) covering the last ``days`` days for a datetime column."""
    start = (utcnow() - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rows = (
        db.session.query(func.date(column).label("day"), func.count())
        .filter(column >= start)
        .group_by("day")
        .all()
    )
    counts = {day: total for day, total in rows}
    labels: list[str] = []
    values: list[int] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.strftime("%d %b"))
        values.append(counts.get(day.date().isoformat(), 0))
    return labels, values


def get_incident_trend(days: int = TREND_DAYS) -> dict:
    """Daily incident volume for the last ``days`` days."""
    labels, values = _daily_trend(Incident, Incident.detected_at, days)
    return {"labels": labels, "values": values}


def get_alert_trend(days: int = TREND_DAYS) -> dict:
    """Daily alert volume for the last ``days`` days."""
    labels, values = _daily_trend(Alert, Alert.created_at, days)
    return {"labels": labels, "values": values}


def get_incidents_by_type() -> dict:
    """Incident counts grouped by detection category."""
    rows = (
        db.session.query(Incident.incident_type, func.count())
        .group_by(Incident.incident_type)
        .order_by(func.count().desc())
        .all()
    )
    return {
        "labels": [label.value.title() for label, _ in rows],
        "values": [count for _, count in rows],
    }


def get_incidents_by_severity() -> dict:
    """Incident counts grouped by severity (low -> critical)."""
    rows = (
        db.session.query(Incident.severity, func.count())
        .group_by(Incident.severity)
        .all()
    )
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    rows.sort(key=lambda row: order.get(row[0].value, 9))
    return {
        "labels": [label.value.title() for label, _ in rows],
        "values": [count for _, count in rows],
    }


def get_camera_status_split() -> dict:
    """Camera distribution by operational state (all states present)."""
    counts = dict.fromkeys(CameraStatus, 0)
    for status, count in (
        db.session.query(Camera.status, func.count()).group_by(Camera.status).all()
    ):
        counts[status] = count
    return {
        "labels": [status.value.title() for status in CameraStatus],
        "values": [counts[status] for status in CameraStatus],
    }


def get_recent_incidents(limit: int = 6) -> list[Incident]:
    """The most recently detected incidents."""
    return (
        Incident.query.order_by(Incident.detected_at.desc()).limit(limit).all()
    )


def get_recent_alerts(limit: int = 6) -> list[Alert]:
    """The most recently created alerts."""
    return Alert.query.order_by(Alert.created_at.desc()).limit(limit).all()


def get_recent_activity(limit: int = 8) -> list[AuditLog]:
    """The most recent audit trail entries."""
    return (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    )
