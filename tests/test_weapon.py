"""Module 11 — weapon detection: detector status, routes, access control."""

import pytest

from app import create_app
from extensions import db
from models import Camera, Incident, Role, User
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from ai.detectors_weapon import WeaponDetector, weapon_detector
from services import camera_service


@pytest.fixture()
def app():
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


def _make_user(
    role_slug=RoleSlug.OPERATOR.value,
    username="wop",
    email="wop@sentinel.local",
) -> User:
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


def _login(client, username="wop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_camera() -> int:
    camera = camera_service.create_camera(
        name="Weapon Cam",
        location="Lobby",
        source_type="ip",
        ip_address="192.0.2.60",
        port=80,
    )
    return camera.id


def _make_incident(
    incident_type: IncidentType = IncidentType.WEAPON,
    title: str = "Weapon incident",
) -> int:
    incident = Incident(
        title=title,
        incident_type=incident_type,
        severity=SeverityLevel.CRITICAL,
        status=IncidentStatus.OPEN,
        details={},
    )
    db.session.add(incident)
    db.session.commit()
    return incident.id


# ---------------------------------------------------------------------------
# Detector unit tests
# ---------------------------------------------------------------------------
def test_detector_name_and_type():
    det = WeaponDetector()
    assert det.name == "weapon"
    assert det.incident_type == IncidentType.WEAPON


def test_detector_not_available_without_yolo(monkeypatch):
    det = WeaponDetector()
    monkeypatch.setattr("ai.detectors_weapon._yolo_available", lambda: False)
    assert det.available is False
    assert det.detect(type("F", (), {"image": b"", "metadata": {}})()) == []


def test_detector_weights_present_without_yolo(monkeypatch):
    det = WeaponDetector()
    monkeypatch.setattr("ai.detectors_weapon._yolo_available", lambda: True)
    monkeypatch.setattr("ai.detectors_weapon._model_path", lambda k: "/fake/weapon.pt")
    assert det.available is True
    assert det.yolo_installed is True
    assert det.weights_present is True


def test_severity_thresholds():
    det = WeaponDetector()
    assert det._severity(0.95).value == "critical"
    assert det._severity(0.75).value == "high"
    assert det._severity(0.60).value == "medium"
    assert det._severity(0.40).value == "low"


def test_registered_in_engine(app):
    from ai.registry import get_detector
    with app.app_context():
        det = get_detector("weapon")
    assert det is weapon_detector


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def test_index_requires_login(client):
    assert client.get("/detection/weapon/").status_code == 302
    assert "/auth/login" in client.get("/detection/weapon/").headers["Location"]


def test_viewer_can_view_index(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    response = client.get("/detection/weapon/")
    assert response.status_code == 200
    assert b"Detector status" in response.data


def test_viewer_cannot_run(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        camera_id = _make_camera()
    _login(client, "viewer1")
    assert client.post(
        "/detection/weapon/run", data={"camera_id": camera_id}
    ).status_code == 403


def test_run_requires_camera(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post("/detection/weapon/run", data={})
    assert response.status_code == 302
    with app.app_context():
        assert Incident.query.count() == 0


def test_run_detector_unavailable_shows_flash(app, client):
    with app.app_context():
        _make_user()
        camera_id = _make_camera()
    _login(client)
    response = client.post("/detection/weapon/run", data={"camera_id": camera_id})
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Recent incidents panel
# ---------------------------------------------------------------------------
def test_index_shows_weapon_incidents(app, client):
    with app.app_context():
        _make_user()
        _make_incident(IncidentType.WEAPON, "Knife detected")
        _make_incident(IncidentType.FIRE, "Should not appear")
    _login(client)
    page = client.get("/detection/weapon/")
    assert page.status_code == 200
    assert b"Knife detected" in page.data
    assert b"Should not appear" not in page.data
