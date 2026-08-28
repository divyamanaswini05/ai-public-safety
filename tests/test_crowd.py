"""Module 12 — crowd analysis: detector status, routes, access control."""

import pytest

from app import create_app
from extensions import db
from models import Camera, Incident, Role, User
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from ai.detectors_crowd import CrowdDetector, crowd_detector
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
    username="crowdop",
    email="crowdop@sentinel.local",
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


def _login(client, username="crowdop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_camera() -> int:
    return camera_service.create_camera(
        name="Crowd Cam", location="Plaza",
        source_type="ip", ip_address="192.0.2.70", port=80,
    ).id


def _make_incident(title: str = "Crowd surge") -> int:
    incident = Incident(
        title=title, incident_type=IncidentType.CROWD,
        severity=SeverityLevel.HIGH, status=IncidentStatus.OPEN, details={},
    )
    db.session.add(incident)
    db.session.commit()
    return incident.id


# --- Detector unit tests ---
def test_detector_name_and_type():
    det = CrowdDetector()
    assert det.name == "crowd"
    assert det.incident_type == IncidentType.CROWD


def test_detector_not_available_without_yolo(monkeypatch):
    det = CrowdDetector()
    monkeypatch.setattr("ai.detectors_crowd._yolo_available", lambda: False)
    assert det.available is False
    assert det.detect(type("F", (), {"image": b"", "metadata": {}})()) == []


def test_detector_weights_present_without_yolo(monkeypatch):
    det = CrowdDetector()
    monkeypatch.setattr("ai.detectors_crowd._yolo_available", lambda: True)
    monkeypatch.setattr("ai.detectors_crowd._model_path", lambda k: "/fake/crowd.pt")
    assert det.available is True


def test_severity_thresholds():
    det = CrowdDetector()
    assert det._severity(0.95).value == "critical"
    assert det._severity(0.75).value == "high"
    assert det._severity(0.60).value == "medium"
    assert det._severity(0.40).value == "low"


def test_registered_in_engine(app):
    from ai.registry import get_detector
    with app.app_context():
        assert get_detector("crowd") is crowd_detector


# --- Access control ---
def test_index_requires_login(client):
    assert client.get("/detection/crowd/").status_code == 302


def test_viewer_can_view_index(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.get("/detection/crowd/").status_code == 200


def test_viewer_cannot_run(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        camera_id = _make_camera()
    _login(client, "viewer1")
    assert client.post("/detection/crowd/run", data={"camera_id": camera_id}).status_code == 403


def test_run_requires_camera(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    assert client.post("/detection/crowd/run", data={}).status_code == 302


# --- Recent incidents panel ---
def test_index_shows_crowd_incidents(app, client):
    with app.app_context():
        _make_user()
        _make_incident("Crowd surge")
        _make_incident("Trampled person")  # same CROWD type
    _login(client)
    page = client.get("/detection/crowd/")
    assert b"Crowd surge" in page.data
    assert b"Trampled person" in page.data


def test_index_excludes_non_crowd_incidents(app, client):
    with app.app_context():
        _make_user()
        Incident.query.delete()
        fire = Incident(
            title="Kitchen fire", incident_type=IncidentType.FIRE,
            severity=SeverityLevel.LOW, status=IncidentStatus.OPEN, details={},
        )
        db.session.add(fire)
        db.session.commit()
    _login(client)
    page = client.get("/detection/crowd/")
    assert b"Kitchen fire" not in page.data
