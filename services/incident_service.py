"""Incident management business logic — querying, CRUD and status flow."""

from __future__ import annotations

from sqlalchemy import func

from extensions import db
from models import Incident
from models.base import utcnow
from models.enums import IncidentStatus, IncidentType, SeverityLevel
from services.audit_service import audit

RESOLVED_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}


def _enum_value(cls, value: str):
    """Coerce a raw string to an enum member, or ``None`` when invalid."""
    if value is None:
        return None
    try:
        return cls(value)
    except ValueError:
        return None


def list_incidents(
    status: str | None = None,
    severity: str | None = None,
    incident_type: str | None = None,
    camera_id: int | None = None,
    search: str | None = None,
) -> list[Incident]:
    """Query incidents ordered newest-first, applying any supplied filters."""
    query = Incident.query

    status_enum = _enum_value(IncidentStatus, status)
    if status_enum is not None:
        query = query.filter(Incident.status == status_enum)

    severity_enum = _enum_value(SeverityLevel, severity)
    if severity_enum is not None:
        query = query.filter(Incident.severity == severity_enum)

    type_enum = _enum_value(IncidentType, incident_type)
    if type_enum is not None:
        query = query.filter(Incident.incident_type == type_enum)

    if camera_id:
        query = query.filter(Incident.camera_id == camera_id)

    if search and search.strip():
        query = query.filter(Incident.title.ilike(f"%{search.strip()}%"))

    return query.order_by(Incident.detected_at.desc()).all()


def get_incident_counts() -> dict[str, int]:
    """Incident totals per status (every status represented)."""
    counts = dict.fromkeys((s.value for s in IncidentStatus), 0)
    rows = (
        db.session.query(Incident.status, func.count())
        .group_by(Incident.status)
        .all()
    )
    for status, total in rows:
        counts[status.value] = total
    return counts


def create_incident(
    *,
    title: str,
    incident_type: IncidentType | str,
    severity: SeverityLevel | str = SeverityLevel.MEDIUM,
    camera_id: int | None = None,
    description: str | None = None,
    created_by: int | None = None,
) -> Incident:
    """Persist a manually reported incident in the open state."""
    incident = Incident(
        title=title,
        incident_type=_enum_value(IncidentType, incident_type.value)
        if isinstance(incident_type, IncidentType)
        else incident_type,
        severity=_enum_value(SeverityLevel, severity.value)
        if isinstance(severity, SeverityLevel)
        else severity,
        status=IncidentStatus.OPEN,
        camera_id=camera_id,
        description=description,
        created_by=created_by,
        details={},
    )
    db.session.add(incident)
    db.session.flush()
    audit(
        action="incident.create",
        module="incidents",
        message=f"Incident '{title}' reported",
        details={"incident_id": incident.id},
    )
    return incident


def update_incident(
    incident: Incident,
    *,
    title: str,
    incident_type: IncidentType | str,
    severity: SeverityLevel | str,
    description: str | None = None,
) -> Incident:
    """Apply edits to an incident's classification and notes."""
    incident.title = title
    incident.incident_type = (
        incident_type
        if isinstance(incident_type, IncidentType)
        else IncidentType(incident_type)
    )
    incident.severity = (
        severity
        if isinstance(severity, SeverityLevel)
        else SeverityLevel(severity)
    )
    incident.description = description
    db.session.flush()
    audit(
        action="incident.update",
        module="incidents",
        message=f"Incident '{title}' updated",
        details={"incident_id": incident.id},
    )
    return incident


def set_status(incident: Incident, status: IncidentStatus) -> Incident:
    """Move an incident through its lifecycle, tracking resolution time."""
    incident.status = status
    incident.resolved_at = utcnow() if status in RESOLVED_STATUSES else None
    db.session.flush()
    audit(
        action="incident.status",
        module="incidents",
        message=f"Incident '{incident.title}' marked {status.value}",
        details={"incident_id": incident.id},
    )
    return incident


def delete_incident(incident: Incident) -> None:
    """Remove an incident (alerts/evidence cascade or stay linked)."""
    title = incident.title
    db.session.delete(incident)
    audit(
        action="incident.delete",
        module="incidents",
        message=f"Incident '{title}' deleted",
    )
