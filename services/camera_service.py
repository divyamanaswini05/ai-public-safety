"""Camera management business logic — CRUD, status and health probing."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from extensions import db
from models import Camera
from models.base import utcnow
from models.enums import CameraSource, CameraStatus
from services import crypto_service
from services.audit_service import audit

PROBE_TIMEOUT_SECONDS = 3


def _coerce_source_type(source_type: CameraSource | str) -> CameraSource:
    """Normalize a raw form value into a CameraSource member."""
    if isinstance(source_type, CameraSource):
        return source_type
    return CameraSource(source_type)


def create_camera(
    *,
    name: str,
    location: str | None = None,
    source_type: CameraSource | str,
    source_url: str | None = None,
    ip_address: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Camera:
    """Persist a new camera, encrypting any stream credential."""
    camera = Camera(
        name=name,
        location=location,
        source_type=_coerce_source_type(source_type),
        source_url=source_url,
        ip_address=ip_address,
        port=port,
        username=username,
        status=CameraStatus.OFFLINE,
        is_active=True,
        latitude=latitude,
        longitude=longitude,
    )
    if password:
        camera.password_encrypted = crypto_service.encrypt_secret(password)
    db.session.add(camera)
    db.session.flush()
    audit(action="camera.create", module="cameras", message=f"Camera '{name}' added")
    return camera


def update_camera(
    camera: Camera,
    *,
    name: str,
    location: str | None = None,
    source_type: CameraSource | str,
    source_url: str | None = None,
    ip_address: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Camera:
    """Apply edits to a camera; a blank password keeps the stored one."""
    camera.name = name
    camera.location = location
    camera.source_type = _coerce_source_type(source_type)
    camera.source_url = source_url
    camera.ip_address = ip_address
    camera.port = port
    camera.username = username
    camera.latitude = latitude
    camera.longitude = longitude
    if password:
        camera.password_encrypted = crypto_service.encrypt_secret(password)
    db.session.flush()
    audit(action="camera.update", module="cameras", message=f"Camera '{name}' updated")
    return camera


def delete_camera(camera: Camera) -> None:
    """Remove a camera (linked incidents keep their history via SET NULL)."""
    name = camera.name
    db.session.delete(camera)
    audit(action="camera.delete", module="cameras", message=f"Camera '{name}' removed")


def set_status(camera: Camera, status: CameraStatus) -> Camera:
    """Manually set a camera's operational status."""
    camera.status = status
    audit(
        action="camera.status",
        module="cameras",
        message=f"Camera '{camera.name}' status set to {status.value}",
    )
    return camera


def toggle_active(camera: Camera) -> Camera:
    """Flip the camera's enabled/disabled flag."""
    camera.is_active = not camera.is_active
    audit(
        action="camera.active",
        module="cameras",
        message=f"Camera '{camera.name}' "
        + ("enabled" if camera.is_active else "disabled"),
    )
    return camera


def _default_port(source_type: CameraSource | str) -> int:
    """Default port per source type when none is configured."""
    return 554 if source_type == CameraSource.RTSP else 80


def _camera_endpoint(camera: Camera) -> tuple[str, int] | None:
    """Resolve the host/port used for health checks, when available."""
    if camera.ip_address:
        return camera.ip_address, camera.port or _default_port(camera.source_type)
    if camera.source_url:
        parsed = urlparse(camera.source_url)
        host = parsed.hostname
        if not host:
            return None
        return host, parsed.port or _default_port(camera.source_type)
    return None


def probe_connection(camera: Camera, timeout: int = PROBE_TIMEOUT_SECONDS) -> bool | None:
    """Attempt a TCP handshake against the camera and update its health.

    Returns True when reachable, False when not, and None for cameras that
    cannot be probed (e.g. a local webcam).
    """
    if camera.source_type == CameraSource.WEBCAM:
        return None
    endpoint = _camera_endpoint(camera)
    if endpoint is None:
        return None
    host, port = endpoint
    try:
        with socket.create_connection((host, port), timeout=timeout):
            camera.status = CameraStatus.ONLINE
            camera.health_score = 100.0
    except OSError:
        camera.status = CameraStatus.OFFLINE
        camera.health_score = 0.0
    camera.last_seen_at = utcnow()
    audit(
        action="camera.check",
        module="cameras",
        message=f"Health probe for '{camera.name}': {camera.status.value}",
    )
    return camera.status == CameraStatus.ONLINE
