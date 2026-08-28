"""Module 16 — analytics: overview stats, chart data, access control."""

import json

import pytest

from app import create_app
from extensions import db
from models import Alert, Camera, Evidence, Incident, Role, User
from models.enums import (
    AlertPriority,
    AlertStatus,
    AlertType,
    IncidentStatus,
    IncidentType,
    RoleSlug,
    SeverityLevel,
)
from services import analytics_service


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
    username="anop",
    email="anop@sentinel.local",
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


def _login(client, username="anop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _seed(app):
    with app.app_context():
        from services import camera_service
        camera_service.create_camera(name="Cam1", source_type="ip", ip_address="10.0.0.1", port=80)
        inc = Incident(title="Fire", incident_type=IncidentType.FIRE, severity=SeverityLevel.HIGH,
                        status=IncidentStatus.OPEN, details={})
        db.session.add(inc)
        db.session.flush()
        alert = Alert(title="Alert!", alert_type=AlertType.INCIDENT, priority=AlertPriority.HIGH,
                       status=AlertStatus.PENDING, incident_id=inc.id, channels=["email"])
        db.session.add(alert)
        db.session.commit()


# --- Access control ---
def test_index_requires_login(client):
    assert client.get("/analytics/").status_code == 302


def test_data_requires_login(client):
    assert client.get("/analytics/data.json").status_code == 302


def test_viewer_can_view(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.get("/analytics/").status_code == 200
    assert client.get("/analytics/data.json").status_code == 200


# --- Data endpoint ---
def test_data_returns_json(app, client):
    with app.app_context():
        _make_user()
        _seed(app)
    _login(client)
    resp = client.get("/analytics/data.json")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "overview" in data
    assert data["overview"]["cameras"] == 1
    assert data["overview"]["incidents"] == 1
    assert data["overview"]["alerts"] == 1
    assert "incidents_by_type" in data
    assert data["incidents_by_type"].get("fire", 0) == 1


# --- Service functions ---
def test_overview_counts(app):
    with app.app_context():
        _seed(app)
        result = analytics_service.overview()
    assert result["cameras"] == 1
    assert result["incidents"] == 1
    assert result["alerts"] == 1


def test_incidents_by_type(app):
    with app.app_context():
        _seed(app)
        result = analytics_service.incidents_by_type()
    assert result.get("fire") == 1


def test_incidents_by_severity(app):
    with app.app_context():
        _seed(app)
        result = analytics_service.incidents_by_severity()
    assert result.get("high") == 1


def test_incidents_by_status(app):
    with app.app_context():
        _seed(app)
        result = analytics_service.incidents_by_status()
    assert result.get("open") == 1


def test_alerts_by_priority(app):
    with app.app_context():
        _seed(app)
        result = analytics_service.alerts_by_priority()
    assert result.get("high") == 1


def test_incidents_last_7_days(app):
    with app.app_context():
        _seed(app)
        result = analytics_service.incidents_last_7_days()
    assert len(result) == 7
    assert sum(result.values()) == 1
