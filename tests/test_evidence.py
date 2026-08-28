"""Module 15 — evidence management: upload, listing, detail, delete, access control."""

import io

import pytest

from app import create_app
from extensions import db
from models import Evidence, Incident, Role, User
from models.enums import EvidenceType, IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from services import evidence_service


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
    username="evop",
    email="evop@sentinel.local",
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


def _login(client, username="evop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_incident(title: str = "Fire in lobby") -> int:
    inc = Incident(
        title=title, incident_type=IncidentType.FIRE,
        severity=SeverityLevel.HIGH, status=IncidentStatus.OPEN, details={},
    )
    db.session.add(inc)
    db.session.commit()
    return inc.id


def _make_evidence(app, incident_id: int, file_name: str = "snap.jpg") -> int:
    with app.app_context():
        ev = evidence_service.create_evidence(
            incident_id=incident_id,
            evidence_type=EvidenceType.IMAGE,
            file_name=file_name,
            file_content=b"\x89PNG\r\n fake",
            mime_type="image/png",
        )
        return ev.id


# --- Access control ---
def test_list_requires_login(client):
    assert client.get("/evidence/").status_code == 302


def test_viewer_can_view_list_and_detail(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        inc_id = _make_incident()
        ev_id = _make_evidence(app, inc_id)
    _login(client, "viewer1")
    assert client.get("/evidence/").status_code == 200
    assert client.get(f"/evidence/{ev_id}").status_code == 200


def test_viewer_cannot_upload_or_delete(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        inc_id = _make_incident()
        ev_id = _make_evidence(app, inc_id)
    _login(client, "viewer1")
    assert client.get("/evidence/upload").status_code == 403
    assert client.post(f"/evidence/{ev_id}/delete").status_code == 403


def test_operator_can_upload_not_delete(app, client):
    with app.app_context():
        _make_user()
        inc_id = _make_incident()
        ev_id = _make_evidence(app, inc_id)
    _login(client)
    assert client.get("/evidence/upload").status_code == 200
    assert client.post(f"/evidence/{ev_id}/delete").status_code == 403


def test_admin_can_delete(app, client):
    with app.app_context():
        _make_user(RoleSlug.ADMIN.value, "evadmin", "evadmin@sentinel.local")
        inc_id = _make_incident()
        ev_id = _make_evidence(app, inc_id)
    _login(client, "evadmin")
    assert client.post(f"/evidence/{ev_id}/delete").status_code == 302


# --- Upload flow ---
def test_upload_creates_evidence(app, client):
    with app.app_context():
        _make_user()
        inc_id = _make_incident()
    _login(client)
    data = {
        "incident_id": str(inc_id),
        "evidence_type": "image",
        "file": (io.BytesIO(b"\x89PNG\r\n test"), "test.png"),
    }
    response = client.post(
        "/evidence/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        ev = Evidence.query.filter_by(file_name="test.png").first()
        assert ev is not None
        assert ev.incident_id == inc_id
        assert ev.file_size == 11


def test_upload_requires_file(app, client):
    with app.app_context():
        _make_user()
        inc_id = _make_incident()
    _login(client)
    response = client.post(
        "/evidence/upload",
        data={"incident_id": str(inc_id), "evidence_type": "image"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200


# --- Listing filters ---
def test_list_filters_by_type(app, client):
    with app.app_context():
        _make_user()
        inc_id = _make_incident()
        _make_evidence(app, inc_id, "photo.jpg")
    _login(client)
    page = client.get("/evidence/?type=image")
    assert b"photo.jpg" in page.data


def test_list_filters_by_incident(app, client):
    with app.app_context():
        _make_user()
        inc1 = _make_incident("Incident A")
        inc2 = _make_incident("Incident B")
        _make_evidence(app, inc1, "a.jpg")
        _make_evidence(app, inc2, "b.jpg")
    _login(client)
    page = client.get(f"/evidence/?incident_id={inc1}")
    assert b"a.jpg" in page.data
    assert b"b.jpg" not in page.data
