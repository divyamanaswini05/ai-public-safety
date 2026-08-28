"""Detector registry — modules 10-14 register their detectors here."""

from __future__ import annotations

from ai.base import BaseDetector

_REGISTRY: dict[str, BaseDetector] = {}


def register_detector(detector: BaseDetector) -> None:
    """Register a detector instance under its unique ``name``."""
    if not isinstance(detector, BaseDetector):
        raise TypeError(f"{detector!r} is not a BaseDetector")
    if detector.name in _REGISTRY:
        raise ValueError(f"Detector '{detector.name}' is already registered")
    _REGISTRY[detector.name] = detector


def unregister_detector(name: str) -> None:
    """Remove a detector (used by tests and when reloading modules)."""
    _REGISTRY.pop(name, None)


def get_detector(name: str) -> BaseDetector | None:
    """Look up a detector by name, or ``None`` when unknown."""
    return _REGISTRY.get(name)


def get_detectors() -> list[BaseDetector]:
    """Every registered detector, in registration order."""
    return list(_REGISTRY.values())
