"""Camera management tests — CRUD, encryption, access control and probes."""

import socket

import pytest

from app import create_app
from extensions import db
from models import AuditLog, Camera, Role, User
from models.enums import CameraStatus, RoleSlug
from services import camera_service, crypto_service


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
    username="camop",
    email="camop@sentinel.local",
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


def _login(client, username="camop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _create_camera(app, **overrides) -> int:
    with app.app_context():
        camera = camera_service.create_camera(
            name=overrides.get("name", "Front Gate"),
            location=overrides.get("location", "Main entrance"),
            source_type=overrides.get("source_type", "ip"),
            source_url=overrides.get("source_url"),
            ip_address=overrides.get("ip_address", "192.0.2.10"),
            port=overrides.get("port", 80),
            username=overrides.get("username", "admin"),
            password=overrides.get("password", "s3cret"),
            latitude=overrides.get("latitude"),
            longitude=overrides.get("longitude"),
        )
        return camera.id


def _form_data(**overrides) -> dict:
    data = {
        "name": "Back Gate",
        "location": "Rear parking",
        "source_type": "ip",
        "source_url": "",
        "ip_address": "192.0.2.20",
        "port": "554",
        "username": "root",
        "password": "pw123456",
        "latitude": "40.7128",
        "longitude": "-74.0060",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def test_list_requires_login(client):
    response = client.get("/cameras/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_viewer_can_view_list(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    response = client.get("/cameras/")
    assert response.status_code == 200
    assert b"No cameras registered yet" in response.data


def test_viewer_cannot_manage_cameras(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.post("/cameras/new", data=_form_data()).status_code == 403
    assert client.get("/cameras/new").status_code == 403


def test_anonymous_create_redirects_to_login(client):
    response = client.get("/cameras/new")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_operator_can_create_camera(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post("/cameras/new", data=_form_data())
    assert response.status_code == 302

    with app.app_context():
        camera = Camera.query.filter_by(name="Back Gate").first()
        assert camera is not None
        assert camera.source_type.value == "ip"
        assert camera.status == CameraStatus.OFFLINE
        assert camera.password_encrypted is not None
        assert camera.password_encrypted != "pw123456"
        assert crypto_service.decrypt_secret(camera.password_encrypted) == "pw123456"
        assert AuditLog.query.filter_by(action="camera.create").count() == 1


def test_create_rejects_duplicate_name(app, client):
    with app.app_context():
        _make_user()
        _create_camera(app, name="Front Gate")
    _login(client)
    response = client.post("/cameras/new", data=_form_data(name="Front Gate"))
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_create_requires_name(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post("/cameras/new", data=_form_data(name=""))
    assert response.status_code == 200
    assert b"This field is required" in response.data


def test_create_ip_camera_requires_endpoint(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post(
        "/cameras/new",
        data=_form_data(ip_address="", source_url=""),
    )
    assert response.status_code == 200
    assert b"Provide an IP address or stream URL" in response.data


def test_create_rejects_invalid_ip(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post("/cameras/new", data=_form_data(ip_address="999.1.1.1"))
    assert response.status_code == 200
    assert b"valid IP address" in response.data


def test_create_webcam_needs_no_endpoint(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post(
        "/cameras/new",
        data=_form_data(source_type="webcam", ip_address="", source_url="", port=""),
    )
    assert response.status_code == 302
    with app.app_context():
        assert Camera.query.filter_by(name="Back Gate").first().source_type.value == "webcam"


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
def test_edit_updates_and_keeps_password_when_blank(app, client):
    with app.app_context():
        _make_user()
        camera_id = _create_camera(app, name="Front Gate", password="oldpass")
    _login(client)

    response = client.post(
        f"/cameras/{camera_id}/edit",
        data=_form_data(name="Main Gate", password=""),
    )
    assert response.status_code == 302

    with app.app_context():
        camera = db.session.get(Camera, camera_id)
        assert camera.name == "Main Gate"
        assert crypto_service.decrypt_secret(camera.password_encrypted) == "oldpass"


def test_edit_replaces_password_when_provided(app, client):
    with app.app_context():
        _make_user()
        camera_id = _create_camera(app, name="Front Gate", password="oldpass")
    _login(client)

    response = client.post(
        f"/cameras/{camera_id}/edit",
        data=_form_data(name="Front Gate", password="newpass"),
    )
    assert response.status_code == 302

    with app.app_context():
        camera = db.session.get(Camera, camera_id)
        assert crypto_service.decrypt_secret(camera.password_encrypted) == "newpass"


# ---------------------------------------------------------------------------
# Status / delete
# ---------------------------------------------------------------------------
def test_set_status_updates_and_audits(app, client):
    with app.app_context():
        _make_user()
        camera_id = _create_camera(app)
    _login(client)

    response = client.post(
        f"/cameras/{camera_id}/status", data={"status": "offline"}
    )
    assert response.status_code == 302

    with app.app_context():
        camera = db.session.get(Camera, camera_id)
        assert camera.status == CameraStatus.OFFLINE
        assert AuditLog.query.filter_by(action="camera.status").count() == 1


def test_set_status_rejects_unknown_value(app, client):
    with app.app_context():
        _make_user()
        camera_id = _create_camera(app)
    _login(client)

    response = client.post(
        f"/cameras/{camera_id}/status", data={"status": "exploded"}
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Camera, camera_id).status == CameraStatus.OFFLINE


def test_delete_removes_camera(app, client):
    with app.app_context():
        _make_user()
        camera_id = _create_camera(app)
    _login(client)

    response = client.post(f"/cameras/{camera_id}/delete")
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(Camera, camera_id) is None
        assert AuditLog.query.filter_by(action="camera.delete").count() == 1


# ---------------------------------------------------------------------------
# Health probing
# ---------------------------------------------------------------------------
class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_probe_marks_camera_online(app, monkeypatch):
    monkeypatch.setattr(
        "services.camera_service.socket.create_connection",
        lambda *_a, **_k: _FakeConnection(),
    )
    with app.app_context():
        camera_id = _create_camera(app)

        camera = db.session.get(Camera, camera_id)
        assert camera_service.probe_connection(camera) is True
        assert camera.status == CameraStatus.ONLINE
        assert camera.health_score == 100.0
        assert camera.last_seen_at is not None
        assert AuditLog.query.filter_by(action="camera.check").count() == 1


def test_probe_marks_camera_offline(app, monkeypatch):
    def _refuse(*_a, **_k):
        raise OSError("connection refused")

    monkeypatch.setattr(
        "services.camera_service.socket.create_connection", _refuse
    )
    with app.app_context():
        camera_id = _create_camera(app)

        camera = db.session.get(Camera, camera_id)
        assert camera_service.probe_connection(camera) is False
        assert camera.status == CameraStatus.OFFLINE
        assert camera.health_score == 0.0


def test_probe_webcam_is_not_applicable(app):
    with app.app_context():
        camera_id = _create_camera(app, source_type="webcam", ip_address=None)
        camera = db.session.get(Camera, camera_id)
        assert camera_service.probe_connection(camera) is None
        assert camera.status == CameraStatus.OFFLINE


def test_crypto_roundtrip(app):
    with app.app_context():
        encrypted = crypto_service.encrypt_secret("top-secret-pass")
        assert encrypted != "top-secret-pass"
        assert crypto_service.decrypt_secret(encrypted) == "top-secret-pass"
        assert crypto_service.decrypt_secret(None) is None
        assert crypto_service.decrypt_secret("garbage") is None
