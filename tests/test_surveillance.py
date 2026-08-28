"""Live surveillance tests — grid, status polling JSON and single-feed pages."""

import pytest

from app import create_app
from extensions import db
from models import Camera, Incident, Role, User
from models.enums import CameraSource, CameraStatus, IncidentType, RoleSlug, SeverityLevel


@pytest.fixture()
def app():
    """A testing application with an empty in-memory schema."""
    application = create_app("testing")
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_user(role_slug=RoleSlug.OPERATOR.value, username="surv", email="surv@sentinel.local") -> User:
    role = Role.query.filter_by(slug=role_slug).first()
    if role is None:
        role = Role(name=role_slug.title(), slug=role_slug, description="test role")
        db.session.add(role)
        db.session.flush()
    user = User(
        username=username,
        email=email,
        role=role,
        is_active=True,
        is_verified=True,
    )
    user.set_password("CorrectHorseBattery99!")
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username="surv") -> None:
    client.post(
        "/auth/login",
        data={"identity": username, "password": "CorrectHorseBattery99!"},
    )


def _make_camera(
    name: str,
    status: CameraStatus = CameraStatus.ONLINE,
    is_active: bool = True,
    source_type: CameraSource = CameraSource.IP,
) -> Camera:
    camera = Camera(
        name=name,
        status=status,
        is_active=is_active,
        source_type=source_type,
    )
    db.session.add(camera)
    db.session.flush()
    return camera


def _make_incident(camera: Camera, title: str) -> Incident:
    incident = Incident(
        camera=camera,
        title=title,
        incident_type=IncidentType.INTRUSION,
        severity=SeverityLevel.MEDIUM,
    )
    db.session.add(incident)
    return incident


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def test_surveillance_requires_login(client):
    for url in ("/surveillance/", "/surveillance/status", "/surveillance/feed/1"):
        response = client.get(url)
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]


def test_viewer_role_can_view_surveillance(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        _make_camera("Front Gate")
        db.session.commit()
    _login(client, "viewer1")
    assert client.get("/surveillance/").status_code == 200
    assert client.get("/surveillance/status").status_code == 200


# ---------------------------------------------------------------------------
# Grid page
# ---------------------------------------------------------------------------
def test_surveillance_renders_empty_state(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.get("/surveillance/")
    assert response.status_code == 200
    assert b"No active cameras" in response.data


def test_grid_shows_only_active_cameras(app, client):
    with app.app_context():
        _make_user()
        _make_camera("Front Gate", CameraStatus.ONLINE)
        _make_camera("Back Gate", CameraStatus.OFFLINE)
        _make_camera("Retired Cam", CameraStatus.ONLINE, is_active=False)
        db.session.commit()
    _login(client)
    response = client.get("/surveillance/")
    assert response.status_code == 200
    assert b"Front Gate" in response.data
    assert b"Back Gate" in response.data
    assert b"Retired Cam" not in response.data


def test_grid_shows_status_counts(app, client):
    with app.app_context():
        _make_user()
        _make_camera("A", CameraStatus.ONLINE)
        _make_camera("B", CameraStatus.ONLINE)
        _make_camera("C", CameraStatus.OFFLINE)
        _make_camera("D", CameraStatus.DISABLED)
        db.session.commit()
    _login(client)
    response = client.get("/surveillance/")
    assert response.status_code == 200
    assert b'id="countAll">4' in response.data
    assert b'id="countOnline">2' in response.data
    assert b'id="countOffline">1' in response.data
    assert b'id="countDisabled">1' in response.data


# ---------------------------------------------------------------------------
# Status polling endpoint
# ---------------------------------------------------------------------------
def test_status_returns_json_snapshot(app, client):
    with app.app_context():
        _make_user()
        _make_camera("Front Gate", CameraStatus.ONLINE)
        _make_camera("Back Gate", CameraStatus.DISABLED)
        _make_camera("Retired Cam", CameraStatus.ONLINE, is_active=False)
        db.session.commit()
    _login(client)
    response = client.get("/surveillance/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"cameras"}

    by_name = {cam["name"]: cam for cam in payload["cameras"]}
    assert set(by_name) == {"Front Gate", "Back Gate"}
    assert by_name["Front Gate"]["status"] == "online"
    assert by_name["Back Gate"]["status"] == "disabled"
    assert by_name["Front Gate"]["health"] is None
    assert by_name["Front Gate"]["last_seen"] is None


def test_status_snapshot_includes_health(app, client):
    with app.app_context():
        _make_user()
        camera = _make_camera("Lobby", CameraStatus.ONLINE)
        camera.health_score = 88.0
        db.session.commit()
    _login(client)
    payload = client.get("/surveillance/status").get_json()
    lobby = payload["cameras"][0]
    assert lobby["health"] == 88.0


# ---------------------------------------------------------------------------
# Single feed page
# ---------------------------------------------------------------------------
def test_feed_404_for_missing_camera(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    assert client.get("/surveillance/feed/9999").status_code == 404


def test_feed_renders_camera_and_incidents(app, client):
    with app.app_context():
        _make_user()
        camera = _make_camera("Lobby", CameraStatus.ONLINE)
        _make_incident(camera, "Suspicious package in lobby")
        db.session.commit()
        camera_id = camera.id
    _login(client)
    response = client.get(f"/surveillance/feed/{camera_id}")
    assert response.status_code == 200
    assert b"Lobby" in response.data
    assert b"Suspicious package in lobby" in response.data


def test_feed_renders_no_signal_placeholder_for_webcam(app, client):
    with app.app_context():
        _make_user()
        camera = _make_camera(
            "Local Webcam", CameraStatus.ONLINE, source_type=CameraSource.WEBCAM
        )
        db.session.commit()
        camera_id = camera.id
    _login(client)
    response = client.get(f"/surveillance/feed/{camera_id}")
    assert response.status_code == 200
    assert b"No signal" in response.data
