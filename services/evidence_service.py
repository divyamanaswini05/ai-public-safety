"""Evidence management business logic — upload, listing and deletion."""

from __future__ import annotations

import os
import uuid

from flask import current_app

from extensions import db
from models import Evidence
from models.base import utcnow
from models.enums import EvidenceType
from services.audit_service import audit


def _storage_dir() -> str:
    """Return the evidence storage directory, creating it if needed."""
    path = os.path.join(
        current_app.instance_path, "storage", "evidence"
    )
    os.makedirs(path, exist_ok=True)
    return path


def list_evidence(
    incident_id: int | None = None,
    evidence_type: str | None = None,
) -> list[Evidence]:
    query = Evidence.query
    if incident_id:
        query = query.filter(Evidence.incident_id == incident_id)
    if evidence_type:
        try:
            query = query.filter(Evidence.evidence_type == EvidenceType(evidence_type))
        except ValueError:
            pass
    return query.order_by(Evidence.captured_at.desc()).all()


def create_evidence(
    *,
    incident_id: int,
    evidence_type: EvidenceType | str,
    file_name: str,
    file_content: bytes,
    mime_type: str | None = None,
) -> Evidence:
    """Persist an evidence file and its metadata."""
    etype = (
        evidence_type
        if isinstance(evidence_type, EvidenceType)
        else EvidenceType(evidence_type)
    )
    ext = os.path.splitext(file_name)[1] or ".bin"
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage = _storage_dir()
    file_path = os.path.join(storage, stored_name)
    try:
        with open(file_path, "wb") as fh:
            fh.write(file_content)
    except OSError:
        file_path = ""

    evidence = Evidence(
        incident_id=incident_id,
        evidence_type=etype,
        file_name=file_name,
        file_path=file_path,
        mime_type=mime_type,
        file_size=len(file_content),
        captured_at=utcnow(),
    )
    db.session.add(evidence)
    db.session.flush()
    audit(
        action="evidence.upload",
        module="evidence",
        message=f"Evidence '{file_name}' uploaded",
        details={"evidence_id": evidence.id, "incident_id": incident_id},
    )
    return evidence


def delete_evidence(evidence: Evidence) -> None:
    """Remove an evidence record and attempt to delete its stored file."""
    title = evidence.file_name
    path = evidence.file_path
    db.session.delete(evidence)
    audit(
        action="evidence.delete",
        module="evidence",
        message=f"Evidence '{title}' deleted",
        details={"evidence_id": evidence.id},
    )
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
