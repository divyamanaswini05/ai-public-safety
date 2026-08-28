"""Module 13 — intrusion detection: detector status, routes, access control."""

import pytest

from app import create_app
from extensions import db
from models import Camera, Incident, Role, User
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from ai.detectors_intrusion import IntrusionDetector, intrusion_detector
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
    username="intop",
    email="intop@sentinel.local",
) -> User:
    role = Role.query.filter_by(slug=role_slug).first()
    if role is None:
        role = Role(name=role_slug.title(), slug=role_slug, description="test role")
        db.session.add(role)
        db.session.flush()
    user = User(username=username, email=email, role=role, is_active=True, is_verified=True)
    user.set_password("CorrectHorseBattery99!")
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username="intop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_camera() -> int:
    return camera_service.create_camera(
        name="Intrusion Cam", location="Back door",
        source_type="ip", ip_address="192.0.2.80", port=80,
    ).id


def _make_incident(title: str = "Perimeter breach") -> int:
    incident = Incident(
        title=title, incident_type=IncidentType.INTRUSION,
        severity=SeverityLevel.CRITICAL, status=IncidentStatus.OPEN, details={},
    )
    db.session.add(incident)
    db.session.commit()
    return incident.id


# --- Detector unit tests ---
def test_detector_name_and_type():
    det = IntrusionDetector()
    assert det.name == "intrusion"
    assert det.incident_type == IncidentType.INTRUSION


def test_detector_not_available_without_yolo(monkeypatch):
    det = IntrusionDetector()
    monkeypatch.setattr("ai.detectors_intrusion._yolo_available", lambda: False)
    assert det.available is False
    assert det.detect(type("F", (), {"image": b"", "metadata": {}})()) == []


def test_detector_weights_present_without_yolo(monkeypatch):
    det = IntrusionDetector()
    monkeypatch.setattr("ai.detectors_intrusion._yolo_available", lambda: True)
    monkeypatch.setattr("ai.detectors_intrusion._model_path", lambda k: "/fake/intrusion.pt")
    assert det.available is True


def test_severity_thresholds():
    det = IntrusionDetector()
    assert det._severity(0.95).value == "critical"
    assert det._severity(0.75).value == "high"
    assert det._severity(0.60).value == "medium"
    assert det._severity(0.40).value == "low"


def test_registered_in_engine(app):
    from ai.registry import get_detector
    with app.app_context():
        assert get_detector("intrusion") is intrusion_detector


# --- Access control ---
def test_index_requires_login(client):
    assert client.get("/detection/intrusion/").status_code == 302


def test_viewer_can_view_index(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.get("/detection/intrusion/").status_code == 200


def test_viewer_cannot_run(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        camera_id = _make_camera()
    _login(client, "viewer1")
    assert client.post("/detection/intrusion/run", data={"camera_id": camera_id}).status_code == 403


def test_run_requires_camera(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    assert client.post("/detection/intrusion/run", data={}).status_code == 302


# --- Recent incidents panel ---
def test_index_shows_intrusion_incidents(app, client):
    with app.app_context():
        _make_user()
        _make_incident("Perimeter breach")
        _make_incident("Gate forced open")
    _login(client)
    page = client.get("/detection/intrusion/")
    assert b"Perimeter breach" in page.data
    assert b"Gate forced open" in page.data


def test_index_excludes_non_intrusion_incidents(app, client):
    with app.app_context():
        _make_user()
        Incident.query.delete()
        db.session.add(Incident(
            title="Kitchen fire", incident_type=IncidentType.FIRE,
            severity=SeverityLevel.LOW, status=IncidentStatus.OPEN, details={},
        ))
        db.session.commit()
    _login(client)
    assert b"Kitchen fire" not in client.get("/detection/intrusion/").data
