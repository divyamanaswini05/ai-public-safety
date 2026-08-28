"""Person detector — real-time human detection via YOLO COCO weights.

Person detection is the one category that works out of the box: Ultralytics
auto-downloads the default COCO-pretrained ``yolov8n.pt`` model whose class
``person`` (id 0) is accurate out of the box. Unlike weapon/fire/smoke,
which require custom-trained weight files, this detector is genuinely
functional the moment ``ultralytics`` is installed.

When YOLO is unavailable it degrades gracefully to a no-op and the route
layer surfaces a clear *dependencies missing* status.
"""

from __future__ import annotations

from typing import Any

from ai.base import BaseDetector, BoundingBox, DetectionResult, Frame
from ai.frames import _OPENCV_AVAILABLE
from models.enums import IncidentType, SeverityLevel

# Default Ultralytics COCO model, auto-downloaded on first use.
DEFAULT_MODEL = "yolov8n.pt"
PERSON_CLASS_ID = 0


def _yolo_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


class PersonDetector(BaseDetector):
    """Detects people in camera frames using YOLO COCO weights."""

    name = "person"
    incident_type = IncidentType.PERSON
    MODEL_KEY = "person"

    def __init__(self, confidence_threshold: float = 0.45) -> None:
        self._model: Any = None
        self.confidence_threshold = confidence_threshold

    @property
    def available(self) -> bool:
        """True when YOLO (and thus the auto-downloaded COCO model) is present."""
        return _yolo_available()

    @property
    def yolo_installed(self) -> bool:
        return _yolo_available()

    @property
    def weights_present(self) -> bool:
        """Person detection succeeds whenever YOLO itself is installed."""
        return _yolo_available()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        from ultralytics import YOLO
        self._model = YOLO(DEFAULT_MODEL)
        return self._model

    def _severity(self, confidence: float) -> SeverityLevel:
        if confidence >= 0.85:
            return SeverityLevel.HIGH
        if confidence >= 0.70:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def detect(self, frame: Frame) -> list[DetectionResult]:
        if not self.available or not frame.image:
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
                if cls_id != PERSON_CLASS_ID:
                    continue
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                w, h = x2 - x1, y2 - y1
                # OpenCV images have shape (height, width, channels).
                shape = getattr(img, "shape", None)
                if not shape or len(shape) < 2:
                    frame_w, frame_h = 1, 1
                else:
                    frame_h, frame_w = shape[0], shape[1]
                detections.append(DetectionResult(
                    detector=self.name,
                    incident_type=IncidentType.PERSON,
                    label="person",
                    confidence=round(conf, 3),
                    severity=self._severity(conf),
                    bbox=BoundingBox(
                        x=round(x1 / frame_w, 4),
                        y=round(y1 / frame_h, 4),
                        width=round(w / frame_w, 4),
                        height=round(h / frame_h, 4),
                    ),
                    details={"raw_label": "person", "cls_id": cls_id},
                ))
        return detections


person_detector = PersonDetector()
