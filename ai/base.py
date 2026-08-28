"""Core detection primitives — result payloads and the detector contract.

Modules 7-14 build on these types. A detector receives a :class:`Frame`
and returns zero or more :class:`DetectionResult` objects that the engine
validates, deduplicates and persists as incidents and alerts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from models.base import utcnow
from models.enums import IncidentType, SeverityLevel


@dataclass
class BoundingBox:
    """An axis-aligned box in normalized ``[0, 1]`` frame coordinates."""

    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        """Fraction of the frame covered by the box."""
        return self.width * self.height


@dataclass
class Frame:
    """A single image submitted to detection, plus its provenance."""

    image: bytes
    camera_id: int | None = None
    timestamp: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    """A single positive detection produced by a detector."""

    detector: str
    incident_type: IncidentType
    label: str
    confidence: float
    severity: SeverityLevel = SeverityLevel.MEDIUM
    camera_id: int | None = None
    bbox: BoundingBox | None = None
    details: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=utcnow)


class BaseDetector(ABC):
    """Interface every detection module (10-14) implements.

    Subclasses set a unique :attr:`name` and :attr:`incident_type`, then
    implement :meth:`detect` which inspects a frame and returns any
    detections found.
    """

    name: str = ""
    incident_type: IncidentType = IncidentType.UNKNOWN

    @abstractmethod
    def detect(self, frame: Frame) -> list[DetectionResult]:
        """Return detections found in ``frame`` (empty list when none)."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"
