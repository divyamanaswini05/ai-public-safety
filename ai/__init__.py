"""AI detection engine.

Modules 7-14 build on this package: the engine (pipeline, registry and
frame sources) lives here and each detection module (10-14) registers its
own detector with :func:`ai.registry.register_detector`. The ``weights``
subfolder stores trained model files.
"""

from ai.base import BaseDetector, BoundingBox, DetectionResult, Frame
from ai.detectors import SimulationDetector
from ai.detectors_crowd import CrowdDetector, crowd_detector
from ai.detectors_face import FaceDetector, face_detector
from ai.detectors_fire_smoke import FireSmokeDetector, fire_smoke_detector
from ai.detectors_intrusion import IntrusionDetector, intrusion_detector
from ai.detectors_person import PersonDetector, person_detector
from ai.detectors_weapon import WeaponDetector, weapon_detector
from ai.frames import FrameSourceError, OpenCVFrameSource, SyntheticFrameSource
from ai.pipeline import DetectionEngine, process_detection
from ai.registry import (
    get_detector,
    get_detectors,
    register_detector,
    unregister_detector,
)
from ai.service import engine_status, run_detection
from ai.weights import list_models, model_path, require_model, weights_dir

# The simulation detector ships with the engine so the pipeline can be
# exercised (and demoed) before any trained model files are present.
try:
    register_detector(SimulationDetector())
except ValueError:
    pass

# Module 10 — fire & smoke detector (gracefully skips when deps missing).
try:
    register_detector(fire_smoke_detector)
except ValueError:
    pass

# Module 11 — weapon detector (gracefully skips when deps missing).
try:
    register_detector(weapon_detector)
except ValueError:
    pass

# Module 12 — crowd analyser (gracefully skips when deps missing).
try:
    register_detector(crowd_detector)
except ValueError:
    pass

# Module 13 — intrusion detector (gracefully skips when deps missing).
try:
    register_detector(intrusion_detector)
except ValueError:
    pass

# Module 14 — face recogniser (gracefully skips when deps missing).
try:
    register_detector(face_detector)
except ValueError:
    pass

# Person detector — real-time human detection via default YOLO COCO weights.
# Functional immediately once ultralytics is installed.
try:
    register_detector(person_detector)
except ValueError:
    pass

__all__ = [
    "BaseDetector",
    "BoundingBox",
    "CrowdDetector",
    "DetectionEngine",
    "DetectionResult",
    "FaceDetector",
    "FireSmokeDetector",
    "Frame",
    "FrameSourceError",
    "IntrusionDetector",
    "OpenCVFrameSource",
    "SyntheticFrameSource",
    "WeaponDetector",
    "crowd_detector",
    "engine_status",
    "face_detector",
    "fire_smoke_detector",
    "get_detector",
    "get_detectors",
    "intrusion_detector",
    "list_models",
    "model_path",
    "process_detection",
    "register_detector",
    "require_model",
    "run_detection",
    "unregister_detector",
    "weapon_detector",
    "weights_dir",
]
