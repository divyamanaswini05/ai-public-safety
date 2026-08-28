"""Live surveillance — active camera grid, status snapshots and feed data."""

from __future__ import annotations

from models import Camera, Incident


def get_surveillance_cameras() -> list[Camera]:
    """Active cameras for the live grid, newest registration first."""
    return (
        Camera.query.filter_by(is_active=True)
        .order_by(Camera.created_at.desc())
        .all()
    )


def get_status_snapshot() -> list[dict]:
    """Lightweight health snapshot consumed by the client polling endpoint."""
    return [
        {
            "id": camera.id,
            "name": camera.name,
            "status": camera.status.value,
            "health": camera.health_score,
            "last_seen": (
                camera.last_seen_at.isoformat() if camera.last_seen_at else None
            ),
        }
        for camera in get_surveillance_cameras()
    ]


def get_camera_incidents(camera: Camera, limit: int = 5) -> list[Incident]:
    """Most recently detected incidents for a single camera feed."""
    return (
        Incident.query.filter_by(camera_id=camera.id)
        .order_by(Incident.detected_at.desc())
        .limit(limit)
        .all()
    )
