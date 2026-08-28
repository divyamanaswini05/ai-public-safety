"""Incident management tests — CRUD, status flow, filters and access control."""

import pytest

from app import create_app
from extensions import db
from models import AuditLog, Camera, Incident, Role, User
from models.enums import IncidentStatus, RoleSlug
from services import camera_service, incident_service


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


def _make_user(
    role_slug=RoleSlug.OPERATOR.value,
    username="incop",
    email="incop@sentinel.local",
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


def _login(client, username="incop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_camera() -> int:
    camera = camera_service.create_camera(
        name="Incident Cam",
        location="Lot B",
        source_type="ip",
        ip_address="192.0.2.30",
        port=80,
    )
    return camera.id


def _create_incident(
    app,
    *,
    title="Suspicious package",
    incident_type="intrusion",
    severity="medium",
    camera_id=None,
    created_by=None,
) -> int:
    with app.app_context():
        incident = incident_service.create_incident(
            title=title,
            incident_type=incident_type,
            severity=severity,
            camera_id=camera_id,
            description="Seen near the north door.",
            created_by=created_by,
        )
        return incident.id


def _form_data(**overrides) -> dict:
    data = {
        "title": "Unattended vehicle",
        "incident_type": "intrusion",
        "severity": "high",
        "camera_id": "0",
        "description": "Car parked with engine running after hours.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def test_list_requires_login(client):
    response = client.get("/incidents/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_viewer_can_view_list_and_detail(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        incident_id = _create_incident(app)
    _login(client, "viewer1")
    response = client.get("/incidents/")
    assert response.status_code == 200
    assert b"Suspicious package" in response.data
    detail = client.get(f"/incidents/{incident_id}")
    assert detail.status_code == 200
    assert b"Seen near the north door." in detail.data


def test_viewer_cannot_manage_incidents(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        incident_id = _create_incident(app)
    _login(client, "viewer1")
    assert client.get("/incidents/new").status_code == 403
    assert client.post("/incidents/new", data=_form_data()).status_code == 403
    assert client.get(f"/incidents/{incident_id}/edit").status_code == 403
    assert client.post(
        f"/incidents/{incident_id}/status", data={"status": "resolved"}
    ).status_code == 403
    assert client.post(f"/incidents/{incident_id}/delete").status_code == 403


def test_anonymous_new_redirects_to_login(client):
    response = client.get("/incidents/new")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_operator_and_analyst_can_manage(app, client):
    for slug, username, email in [
        (RoleSlug.OPERATOR.value, "incop", "incop@sentinel.local"),
        (RoleSlug.ANALYST.value, "incan", "incan@sentinel.local"),
    ]:
        with app.app_context():
            _make_user(slug, username, email)
            incident_id = _create_incident(app)
        _login(client, username)
        assert client.get("/incidents/new").status_code == 200
        created = client.post(
            "/incidents/new", data=_form_data(title=f"Reported by {username}")
        )
        assert created.status_code == 302
        assert client.post(
            f"/incidents/{incident_id}/status", data={"status": "resolved"}
        ).status_code == 302
        assert client.get(f"/incidents/{incident_id}/edit").status_code == 200
        assert client.post(f"/incidents/{incident_id}/delete").status_code == 403


def test_operator_cannot_delete_but_admin_can(app, client):
    with app.app_context():
        _make_user(RoleSlug.OPERATOR.value, "incop", "incop@sentinel.local")
        _make_user(RoleSlug.ADMIN.value, "incadmin", "incadmin@sentinel.local")
        incident_id = _create_incident(app)
    _login(client, "incop")
    assert client.post(f"/incidents/{incident_id}/delete").status_code == 403
    client.post("/auth/logout")
    _login(client, "incadmin")
    response = client.post(f"/incidents/{incident_id}/delete")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Incident, incident_id) is None


# ---------------------------------------------------------------------------
# Creating and editing
# ---------------------------------------------------------------------------
def test_create_requires_title(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post("/incidents/new", data=_form_data(title=""))
    assert response.status_code == 200
    assert b"required" in response.data.lower()


def test_create_incident_sets_open_status_and_audits(app, client):
    with app.app_context():
        user_id = _make_user().id
    _login(client)
    response = client.post("/incidents/new", data=_form_data(camera_id="0"))
    assert response.status_code == 302
    with app.app_context():
        incident = Incident.query.filter_by(title="Unattended vehicle").first()
        assert incident is not None
        assert incident.status == IncidentStatus.OPEN
        assert incident.created_by == user_id
        assert incident.confidence is None
        log = AuditLog.query.filter_by(action="incident.create").first()
        assert log is not None
        assert log.details.get("incident_id") == incident.id


def test_edit_incident_updates_and_audits(app, client):
    with app.app_context():
        _make_user()
        incident_id = _create_incident(app)
    _login(client)
    response = client.post(
        f"/incidents/{incident_id}/edit",
        data=_form_data(title="Amended report", severity="critical"),
    )
    assert response.status_code == 302
    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident.title == "Amended report"
        assert incident.severity.value == "critical"
        assert AuditLog.query.filter_by(action="incident.update").count() == 1


def test_camera_filter_accepts_valid_camera(app, client):
    with app.app_context():
        _make_user()
        camera_id = _make_camera()
    _login(client)
    response = client.post("/incidents/new", data=_form_data(camera_id=str(camera_id)))
    assert response.status_code == 302
    with app.app_context():
        incident = Incident.query.filter_by(title="Unattended vehicle").first()
        assert incident.camera_id == camera_id


# ---------------------------------------------------------------------------
# Status flow
# ---------------------------------------------------------------------------
def test_status_transition_sets_and_clears_resolved_at(app, client):
    with app.app_context():
        _make_user()
        incident_id = _create_incident(app)
    _login(client)
    client.post(
        f"/incidents/{incident_id}/status", data={"status": "investigating"}
    )
    client.post(f"/incidents/{incident_id}/status", data={"status": "resolved"})
    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None
    client.post(f"/incidents/{incident_id}/status", data={"status": "open"})
    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident.status == IncidentStatus.OPEN
        assert incident.resolved_at is None


def test_invalid_status_rejected(app, client):
    with app.app_context():
        _make_user()
        incident_id = _create_incident(app)
    _login(client)
    response = client.post(f"/incidents/{incident_id}/status", data={"status": "nope"})
    assert response.status_code == 302
    with app.app_context():
        incident = db.session.get(Incident, incident_id)
        assert incident.status == IncidentStatus.OPEN


# ---------------------------------------------------------------------------
# Listing and filters
# ---------------------------------------------------------------------------
def test_list_filters_by_status(app, client):
    with app.app_context():
        _make_user()
        _create_incident(app, title="Open one")
        _create_incident(app, title="Resolved one")
        incident_service.set_status(
            Incident.query.filter_by(title="Resolved one").first(),
            IncidentStatus.RESOLVED,
        )
    _login(client)
    page = client.get("/incidents/?status=resolved")
    assert b"Resolved one" in page.data
    assert b"Open one" not in page.data


def test_list_searches_title(app, client):
    with app.app_context():
        _make_user()
        _create_incident(app, title="Parking dispute")
        _create_incident(app, title="Loud argument")
    _login(client)
    page = client.get("/incidents/?q=parking")
    assert b"Parking dispute" in page.data
    assert b"Loud argument" not in page.data


def test_counts_reflect_each_status(app, client):
    with app.app_context():
        _make_user()
        _create_incident(app, title="First")
        incident_id = _create_incident(app, title="Second")
        incident_service.set_status(
            db.session.get(Incident, incident_id), IncidentStatus.RESOLVED
        )
        counts = incident_service.get_incident_counts()
    assert counts == {
        "open": 1,
        "investigating": 0,
        "resolved": 1,
        "closed": 0,
    }


def test_delete_removes_and_audits(app, client):
    with app.app_context():
        _make_user(RoleSlug.ADMIN.value, "incadmin", "incadmin@sentinel.local")
        incident_id = _create_incident(app)
    _login(client, "incadmin")
    response = client.post(f"/incidents/{incident_id}/delete")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Incident, incident_id) is None
        assert AuditLog.query.filter_by(action="incident.delete").count() == 1
