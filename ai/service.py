"""AI orchestration — engine status reporting and one-shot analysis runs."""

from __future__ import annotations

from models import Camera
from models.enums import CameraSource

from ai.frames import (
    _OPENCV_AVAILABLE,
    OpenCVFrameSource,
    SyntheticFrameSource,
)
from ai.pipeline import DetectionEngine
from ai.registry import get_detector, get_detectors
from ai.weights import list_models

DEFAULT_FRAME_BUDGET = 10


def engine_status() -> dict:
    """Report runtime capabilities: optional backends, detectors and models."""
    try:
        import ultralytics  # noqa: F401

        yolo_available = True
    except ImportError:
        yolo_available = False
    return {
        "opencv": _OPENCV_AVAILABLE,
        "yolo": yolo_available,
        "detectors": [detector.name for detector in get_detectors()],
        "models": list_models(),
    }


def _build_source(
    camera: Camera, frame_limit: int | None
) -> tuple[SyntheticFrameSource | OpenCVFrameSource | None, str]:
    """Choose a frame source for the camera, reporting which one is used.

    Prefers real capture whenever OpenCV is available: IP/RTSP cameras use
    their stream URL and webcams use the local device index ``0``. Falls
    back to the synthetic source when capture is disabled (forced in the
    test configuration) or unavailable.
    """
    from flask import current_app

    budget = frame_limit or DEFAULT_FRAME_BUDGET
    force_synthetic = bool(current_app.config.get("FORCE_SYNTHETIC_SOURCE", False))

    if not force_synthetic and _OPENCV_AVAILABLE:
        if camera.source_type == CameraSource.WEBCAM:
            return (
                OpenCVFrameSource(0, camera_id=camera.id),
                "opencv-webcam",
            )
        endpoint = camera.source_url or (camera.ip_address or "")
        if endpoint:
            return (
                OpenCVFrameSource(endpoint, camera_id=camera.id),
                "opencv",
            )
        return None, "no_endpoint"
    return (
        SyntheticFrameSource(camera_id=camera.id, frame_count=budget, seed=camera.id or 0),
        "synthetic",
    )


def run_detection(
    camera: Camera,
    detector_name: str | None = None,
    frame_limit: int | None = None,
) -> dict:
    """Run the engine once over a camera's feed and persist the results.

    Returns a summary dict; ``status == "ok"`` marks a successful run.
    """
    if detector_name:
        detector = get_detector(detector_name)
        if detector is None:
            return {"status": "unknown_detector", "detector": detector_name}
        detectors = [detector]
    else:
        detectors = get_detectors()

    engine = DetectionEngine(detectors=detectors)
    if not engine.detectors:
        return {"status": "no_detectors", "camera": camera.name}

    source, source_kind = _build_source(camera, frame_limit)
    if source is None:
        return {"status": "capture_unavailable", "camera": camera.name, "source": source_kind}

    try:
        detections, created, frames = engine.analyze_frames(source, save=True)
    finally:
        source.close()

    return {
        "status": "ok",
        "camera": camera.name,
        "detector": detector_name or "all",
        "source": source_kind,
        "frames": frames,
        "detections": len(detections),
        "incidents_created": len(created),
        "incident_ids": [incident.id for incident in created],
    }
