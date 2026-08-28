"""Development/demo detectors — exercise the engine without ML weights.

Real detectors (fire, smoke, weapon, crowd, intrusion, face) are added by
modules 10-14 under :mod:`ai.detectors`. :class:`SimulationDetector` exists
so the pipeline, incident persistence and alert fan-out can be demonstrated
and tested in environments where no YOLO model files are present.
"""

from __future__ import annotations

from ai.base import BaseDetector, DetectionResult, Frame
from models.enums import IncidentType, SeverityLevel

_SCHEDULED_TYPES = (
    IncidentType.FIRE,
    IncidentType.SMOKE,
    IncidentType.WEAPON,
    IncidentType.CROWD,
    IncidentType.INTRUSION,
)


class SimulationDetector(BaseDetector):
    """Deterministic detector emitting hits on a schedule.

    Emits one detection every ``emit_every`` frames, cycling through the
    scheduled incident types. Confidence is derived from the frame index so
    identical inputs always produce identical output.
    """

    name = "simulation"

    def __init__(self, emit_every: int = 3) -> None:
        self.emit_every = max(1, emit_every)

    def _severity(self, confidence: float) -> SeverityLevel:
        if confidence >= 0.9:
            return SeverityLevel.CRITICAL
        if confidence >= 0.75:
            return SeverityLevel.HIGH
        if confidence >= 0.6:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def detect(self, frame: Frame) -> list[DetectionResult]:
        index = frame.metadata.get("index", 0)
        if index % self.emit_every != 0:
            return []
        incident_type = _SCHEDULED_TYPES[index % len(_SCHEDULED_TYPES)]
        confidence = round(0.5 + ((index * 7) % 45) / 100, 2)
        return [
            DetectionResult(
                detector=self.name,
                incident_type=incident_type,
                label=f"Simulated {incident_type.value}",
                confidence=confidence,
                severity=self._severity(confidence),
            )
        ]
