"""Trained model management — resolve and inspect weight files.

Detection modules 10-14 load their YOLO weights from ``ai/weights``.
These helpers give detectors and the AI engine page one shared way to
resolve model files and report which are available, so a detector never
has to guess at paths.
"""

from __future__ import annotations

import os

_WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")

# Canonical model files expected in the weights directory. Each entry maps
# a detector key to (filename, description). The ``person`` entry uses the
# default YOLO COCO weights (no custom file required) — see detectors_person.
MODELS: dict[str, tuple[str, str]] = {
    "fire": ("fire-smoke.pt", "Fire & smoke detector (module 10)"),
    "weapon": ("weapon.pt", "Weapon detector (module 11)"),
    "crowd": ("crowd.pt", "Crowd analyser (module 12)"),
    "intrusion": ("intrusion.pt", "Intrusion detector (module 13)"),
    "face": ("face.pt", "Face recogniser (module 14)"),
    "person": ("yolov8n.pt (auto)", "Person detector (YOLO COCO) — auto-loaded"),
}


def weights_dir() -> str:
    """Absolute path of the weights directory."""
    return _WEIGHTS_DIR


def model_filename(key: str) -> str | None:
    """Canonical weight filename for a detector key, or ``None``."""
    entry = MODELS.get(key)
    return entry[0] if entry else None


def model_path(key: str) -> str | None:
    """Absolute path to a model file, or ``None`` when not present."""
    filename = model_filename(key)
    if not filename:
        return None
    path = os.path.join(_WEIGHTS_DIR, filename)
    return path if os.path.isfile(path) else None


def require_model(key: str) -> str:
    """Resolve a model file or raise ``FileNotFoundError``.

    Detectors call this before loading weights so a missing model fails
    loudly instead of silently degrading.
    """
    path = model_path(key)
    if not path:
        filename = model_filename(key) or key
        raise FileNotFoundError(
            f"Model for '{key}' not found. "
            f"Place {filename} in {_WEIGHTS_DIR}."
        )
    return path


def list_models() -> dict[str, dict]:
    """Report every known model and whether it is available.

    Most models need a weight file on disk. ``person`` is available as soon
    as ``ultralytics`` is installed because its weights auto-download.
    """
    try:
        import ultralytics  # noqa: F401
        yolo_installed = True
    except ImportError:
        yolo_installed = False
    return {
        key: {
            "filename": filename,
            "description": description,
            "available": (model_path(key) is not None) or (key == "person" and yolo_installed),
        }
        for key, (filename, description) in MODELS.items()
    }
