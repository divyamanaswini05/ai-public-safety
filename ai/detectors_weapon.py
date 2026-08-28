"""Weapon detector — Module 11.

Wraps a YOLO model (``ai/weights/weapon.pt``) to detect weapons and
firearms in camera frames.  When YOLO or the weight file is missing the
detector gracefully degrades to no-op, and the route layer surfaces a
clear *dependencies missing* status to the operator.
"""

from __future__ import annotations

from typing import Any

from ai.base import BaseDetector, BoundingBox, DetectionResult, Frame
from ai.frames import _OPENCV_AVAILABLE
from models.enums import IncidentType, SeverityLevel
from ai.weights import model_path as _model_path


def _yolo_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


class WeaponDetector(BaseDetector):
    """Weapon detection backed by a YOLOv8 model."""

    name = "weapon"
    incident_type = IncidentType.WEAPON
    MODEL_KEY = "weapon"

    def __init__(self) -> None:
        self._model: Any = None

    @property
    def available(self) -> bool:
        return _yolo_available() and _model_path(self.MODEL_KEY) is not None

    @property
    def yolo_installed(self) -> bool:
        return _yolo_available()

    @property
    def weights_present(self) -> bool:
        return _model_path(self.MODEL_KEY) is not None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        from ultralytics import YOLO
        self._model = YOLO(_model_path(self.MODEL_KEY))
        return self._model

    def _severity(self, confidence: float) -> SeverityLevel:
        if confidence >= 0.85:
            return SeverityLevel.CRITICAL
        if confidence >= 0.70:
            return SeverityLevel.HIGH
        if confidence >= 0.55:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def detect(self, frame: Frame) -> list[DetectionResult]:
        if not self.available:
            return []
        try:
            model = self._load_model()
            import numpy as np
            img = np.frombuffer(frame.image, dtype=np.uint8)
            if _OPENCV_AVAILABLE:
                import cv2
                img = cv2.imdecode(img, cv2.IMREAD_COLOR)
            results = model(img, verbose=False)
        except Exception:
            return []

        detections: list[DetectionResult] = []
        for result in results:
            for box in getattr(result, "boxes", []):
                cls_id = int(box.cls[0])
                label = result.names.get(cls_id, "unknown")
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                w, h = x2 - x1, y2 - y1
                frame_w, frame_h = getattr(img, "shape", (1, 1))[:2]
                detections.append(DetectionResult(
                    detector=self.name,
                    incident_type=IncidentType.WEAPON,
                    label=label,
                    confidence=round(conf, 3),
                    severity=self._severity(conf),
                    bbox=BoundingBox(
                        x=round(x1 / frame_w, 4),
                        y=round(y1 / frame_h, 4),
                        width=round(w / frame_w, 4),
                        height=round(h / frame_h, 4),
                    ),
                    details={"raw_label": label, "cls_id": cls_id},
                ))
        return detections


weapon_detector = WeaponDetector()
