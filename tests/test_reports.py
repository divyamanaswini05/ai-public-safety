"""Module 17 — reports: PDF/Excel generation, access control."""

import pytest

from app import create_app
from extensions import db
from models import Incident, Role, User
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from services import report_service


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
    username="repop",
    email="repop@sentinel.local",
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


def _login(client, username="repop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _seed(app):
    with app.app_context():
        for i in range(5):
            inc = Incident(
                title=f"Incident {i}", incident_type=IncidentType.FIRE,
                severity=SeverityLevel.HIGH, status=IncidentStatus.OPEN, details={},
            )
            db.session.add(inc)
        db.session.commit()


# --- Access control ---
def test_index_requires_login(client):
    assert client.get("/reports/").status_code == 302


def test_pdf_requires_login(client):
    assert client.get("/reports/incidents.pdf").status_code == 302


def test_excel_requires_login(client):
    assert client.get("/reports/incidents.xlsx").status_code == 302


def test_viewer_can_view_and_download(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.get("/reports/").status_code == 200
    assert client.get("/reports/incidents.pdf").status_code == 200
    assert client.get("/reports/incidents.xlsx").status_code == 200
    assert client.get("/reports/cameras.pdf").status_code == 200


# --- PDF generation ---
def test_incident_pdf_contains_data(app, client):
    with app.app_context():
        _make_user()
        _seed(app)
    _login(client)
    resp = client.get("/reports/incidents.pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert b"%PDF" in resp.data[:10]


def test_incident_pdf_with_filters(app, client):
    with app.app_context():
        _make_user()
        _seed(app)
    _login(client)
    resp = client.get("/reports/incidents.pdf?status=open&type=fire")
    assert resp.status_code == 200
    assert b"%PDF" in resp.data[:10]


# --- Excel generation ---
def test_incident_excel_contains_data(app, client):
    with app.app_context():
        _make_user()
        _seed(app)
    _login(client)
    resp = client.get("/reports/incidents.xlsx")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.content_type


# --- Service functions ---
def test_service_pdf_returns_bytes(app):
    with app.app_context():
        _seed(app)
        pdf = report_service.incident_pdf()
    assert isinstance(pdf, bytes)
    assert b"%PDF" in pdf[:10]


def test_service_excel_returns_bytes(app):
    with app.app_context():
        _seed(app)
        xlsx = report_service.incident_excel()
    assert isinstance(xlsx, bytes)


def test_camera_report_pdf(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    resp = client.get("/reports/cameras.pdf")
    assert resp.status_code == 200
    assert b"%PDF" in resp.data[:10]
