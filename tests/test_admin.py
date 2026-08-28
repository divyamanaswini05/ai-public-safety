"""Module 18 — admin panel: user CRUD, settings, audit log, access control."""

import pytest

from app import create_app
from extensions import db
from models import AuditLog, Role, Setting, User
from models.enums import LogLevel, RoleSlug
from services.audit_service import audit


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
    role_slug=RoleSlug.ADMIN.value,
    username="adm",
    email="adm@sentinel.local",
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


def _login(client, username="adm", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _seed_settings(app):
    with app.app_context():
        Setting.set("alert.email.enabled", "true", group="alerts")
        Setting.set("alert.sms.enabled", "false", group="alerts")
        db.session.commit()


def _seed_logs(app):
    with app.app_context():
        audit(action="test.action", module="test", message="seeded log")
        db.session.commit()


# --- Access control (non-admin rejected) ---
def test_index_requires_login(client):
    assert client.get("/admin/").status_code == 302


def test_viewer_denied(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.get("/admin/").status_code == 403


# --- Admin dashboard ---
def test_admin_dashboard(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"Admin Panel" in resp.data


# --- User management ---
def test_user_list(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    resp = client.get("/admin/users/")
    assert resp.status_code == 200
    assert b"adm" in resp.data


def test_user_new_form(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    resp = client.get("/admin/users/new")
    assert resp.status_code == 200


def test_user_create(app, client):
    with app.app_context():
        _make_user()
        viewer_role = Role(slug=RoleSlug.VIEWER.value, name="Viewer", description="v")
        db.session.add(viewer_role)
        db.session.commit()
        vr_id = viewer_role.id
    _login(client)
    resp = client.post(
        "/admin/users/new",
        data={"username": "newguy", "email": "new@sentinel.local", "password": "StrongPass99!",
              "role_id": vr_id},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        u = User.query.filter_by(username="newguy").first()
        assert u is not None
        assert u.role.slug == RoleSlug.VIEWER.value


def test_user_edit_form(app, client):
    with app.app_context():
        admin = _make_user()
        user_id = admin.id
    _login(client)
    resp = client.get(f"/admin/users/{user_id}/edit")
    assert resp.status_code == 200


def test_user_edit_update(app, client):
    with app.app_context():
        admin = _make_user()
        user_id = admin.id
        role_id = admin.role.id
    _login(client)
    resp = client.post(
        f"/admin/users/{user_id}/edit",
        data={"first_name": "Admin", "last_name": "User", "role_id": role_id,
              "is_active": "on", "is_verified": "on"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        u = db.session.get(User, user_id)
        assert u.first_name == "Admin"


def test_delete_non_admin_user(app, client):
    with app.app_context():
        _make_user()
        _make_user(RoleSlug.VIEWER.value, "v1", "v1@sentinel.local")
        v1 = User.query.filter_by(username="v1").first()
        vid = v1.id
    _login(client)
    resp = client.post(f"/admin/users/{vid}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(User, vid) is None


def test_delete_admin_blocked(app, client):
    with app.app_context():
        admin = _make_user()
        admin_id = admin.id
    _login(client)
    resp = client.post(f"/admin/users/{admin_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(User, admin_id) is not None


# --- Settings ---
def test_settings_list(app, client):
    with app.app_context():
        _make_user()
        _seed_settings(app)
    _login(client)
    resp = client.get("/admin/settings/")
    assert resp.status_code == 200
    assert b"alert.email.enabled" in resp.data


def test_setting_edit_form(app, client):
    with app.app_context():
        _make_user()
        _seed_settings(app)
        s = Setting.query.filter_by(key="alert.email.enabled").first()
        sid = s.id
    _login(client)
    resp = client.get(f"/admin/settings/{sid}/edit")
    assert resp.status_code == 200


def test_setting_edit_save(app, client):
    with app.app_context():
        _make_user()
        _seed_settings(app)
        s = Setting.query.filter_by(key="alert.email.enabled").first()
        sid = s.id
    _login(client)
    resp = client.post(
        f"/admin/settings/{sid}/edit",
        data={"value": "false", "description": "Disabled email alerts"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        s = Setting.query.get(sid)
        assert s.value == "false"
        assert s.description == "Disabled email alerts"


# --- Audit log ---
def test_audit_log(app, client):
    with app.app_context():
        _make_user()
        _seed_logs(app)
    _login(client)
    resp = client.get("/admin/audit/")
    assert resp.status_code == 200
    assert b"test.action" in resp.data


def test_audit_log_filter(app, client):
    with app.app_context():
        _make_user()
        _seed_logs(app)
    _login(client)
    resp = client.get("/admin/audit/?module=test")
    assert resp.status_code == 200
    assert b"test.action" in resp.data

    resp2 = client.get("/admin/audit/?module=nonexistent")
    assert resp2.status_code == 200
    assert b"test.action" not in resp2.data
