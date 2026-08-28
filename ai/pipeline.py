"""Detection pipeline — run detectors over frames and persist the results.

The engine validates every detection against the configured confidence
threshold, deduplicates repeated hits using the alert cooldown window, and
persists incidents and their alerts ready for modules 8-9 to manage.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Iterator

from extensions import db
from models import Alert, Camera, Incident, Setting
from models.base import utcnow
from models.enums import (
    AlertPriority,
    AlertStatus,
    AlertType,
    CameraStatus,
    IncidentStatus,
    IncidentType,
    SeverityLevel,
)
from services import audit_service

from ai.base import DetectionResult, Frame
from ai.registry import get_detectors

DEFAULT_CONFIDENCE = 0.45
DEFAULT_COOLDOWN_SECONDS = 60
DEFAULT_CHANNELS = ["dashboard", "email", "sms", "browser"]

_ALERT_TYPE_MAP: dict[IncidentType, AlertType] = {
    IncidentType.FIRE: AlertType.FIRE,
    IncidentType.SMOKE: AlertType.FIRE,
    IncidentType.WEAPON: AlertType.WEAPON,
    IncidentType.CROWD: AlertType.CROWD,
    IncidentType.INTRUSION: AlertType.INTRUSION,
}

_PRIORITY_MAP: dict[SeverityLevel, AlertPriority] = {
    SeverityLevel.LOW: AlertPriority.LOW,
    SeverityLevel.MEDIUM: AlertPriority.MEDIUM,
    SeverityLevel.HIGH: AlertPriority.HIGH,
    SeverityLevel.CRITICAL: AlertPriority.CRITICAL,
}


def _setting_float(key: str, default: float) -> float:
    """Read a numeric setting, falling back to ``default``."""
    try:
        return float(Setting.get(key, default))
    except (TypeError, ValueError):
        return default


def _alert_type_for(incident_type: IncidentType) -> AlertType:
    """Map an incident category onto the alert taxonomy."""
    return _ALERT_TYPE_MAP.get(incident_type, AlertType.SYSTEM)


def _alert_channels() -> list:
    """Deserialize the configured alert channels from settings."""
    try:
        channels = json.loads(Setting.get("alerts.channels", json.dumps(DEFAULT_CHANNELS)))
        return channels if isinstance(channels, list) else list(DEFAULT_CHANNELS)
    except (TypeError, ValueError):
        return list(DEFAULT_CHANNELS)


def _describe(result: DetectionResult) -> str:
    """Human-readable incident description built from a detection."""
    parts = [f"Detected by {result.detector} at {result.confidence:.0%} confidence"]
    if result.bbox is not None:
        parts.append(f"at ({result.bbox.x:.2f}, {result.bbox.y:.2f})")
    return " — ".join(parts)


def _details(result: DetectionResult) -> dict:
    """Incident details payload: detector metadata plus any detection extras."""
    details = dict(result.details)
    details["detector"] = result.detector
    details["bbox"] = result.bbox.__dict__ if result.bbox else None
    return details


def _raise_alert(incident: Incident, camera: Camera, result: DetectionResult) -> None:
    """Create a pending alert linked to a freshly persisted incident."""
    alert = Alert(
        incident_id=incident.id,
        alert_type=_alert_type_for(result.incident_type),
        priority=_PRIORITY_MAP.get(result.severity, AlertPriority.MEDIUM),
        status=AlertStatus.PENDING,
        title=f"{result.label} on {camera.name}",
        message=(
            f"{result.label} detected by {result.detector} "
            f"on camera '{camera.name}'."
        ),
        channels=_alert_channels(),
    )
    db.session.add(alert)


def process_detection(
    result: DetectionResult, camera: Camera | None = None
) -> Incident | None:
    """Validate, deduplicate and persist a single detection.

    Returns the created :class:`~models.incident.Incident`, or ``None``
    when the detection is below the confidence threshold, the camera is
    not watchable, or a duplicate hit falls inside the cooldown window.
    """
    if result.confidence < _setting_float("alerts.confidence", DEFAULT_CONFIDENCE):
        return None

    if camera is None:
        if result.camera_id is None:
            return None
        camera = db.session.get(Camera, result.camera_id)
        if camera is None:
            return None
    if not camera.is_active or camera.status == CameraStatus.DISABLED:
        return None

    cooldown = int(
        _setting_float("alerts.cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
    )
    cutoff = utcnow() - timedelta(seconds=cooldown)
    recent = Incident.query.filter(
        Incident.camera_id == camera.id,
        Incident.incident_type == result.incident_type,
        Incident.detected_at >= cutoff,
    ).first()
    if recent is not None:
        return None

    incident = Incident(
        camera_id=camera.id,
        incident_type=result.incident_type,
        title=result.label,
        description=_describe(result),
        severity=result.severity,
        confidence=result.confidence,
        details=_details(result),
        status=IncidentStatus.OPEN,
    )
    db.session.add(incident)
    db.session.flush()
    _raise_alert(incident, camera, result)
    audit_service.audit(
        action="ai.detection",
        module="ai",
        message=f"{result.detector}: {result.label} on '{camera.name}'",
        details={"incident_id": incident.id, "confidence": result.confidence},
    )
    return incident


class DetectionEngine:
    """Orchestrates detectors over a frame source and persists hits."""

    def __init__(self, detectors: list | None = None) -> None:
        self.detectors = detectors if detectors is not None else get_detectors()

    def analyze_frames(
        self,
        source,
        save: bool = True,
        frame_limit: int | None = None,
    ) -> tuple[list[DetectionResult], list[Incident], int]:
        """Run every detector over ``source``'s frames.

        Returns ``(detections, created_incidents, frames_processed)``.
        """
        detections: list[DetectionResult] = []
        created: list[Incident] = []
        frames_processed = 0
        for frame in source.stream(limit=frame_limit):
            frames_processed += 1
            for detector in self.detectors:
                for result in detector.detect(frame):
                    result.camera_id = frame.camera_id or result.camera_id
                    detections.append(result)
                    if save:
                        incident = process_detection(result)
                        if incident is not None:
                            created.append(incident)
        return detections, created, frames_processed
