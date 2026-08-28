"""Authentication tests — register, login, lockout, verify, reset, RBAC."""

import re

import pytest
from flask import Blueprint

from app import create_app
from extensions import db
from models import AuditLog, Role, User
from models.enums import RoleSlug
from services import auth_service
from utils.decorators import role_required


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
    username="operator1",
    email="operator1@sentinel.local",
    password="CorrectHorseBattery99!",
    role_slug=RoleSlug.OPERATOR.value,
    verified=False,
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
        is_verified=verified,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _register(client, **overrides):
    data = {
        "username": "newuser",
        "email": "newuser@sentinel.local",
        "password": "Str0ngPass1!",
        "confirm_password": "Str0ngPass1!",
        "first_name": "New",
        "last_name": "User",
    }
    data.update(overrides)
    return client.post("/auth/register", data=data)


def _login(client, identity, password):
    return client.post(
        "/auth/login",
        data={"identity": identity, "password": password},
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def test_register_page_loads(client):
    response = client.get("/auth/register")
    assert response.status_code == 200
    assert b"Create Your Account" in response.data


def test_register_success(client, app):
    response = _register(client)
    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(email="newuser@sentinel.local").first()
        assert user is not None
        assert user.is_verified is False
        assert user.check_password("Str0ngPass1!")
        assert user.role.slug == RoleSlug.VIEWER.value
        assert AuditLog.query.filter_by(action="auth.register").count() == 1


def test_register_rejects_duplicate_email(client, app):
    _register(client)
    client.post("/auth/logout")
    response = _register(client)
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_register_rejects_weak_password(client, app):
    response = _register(client, password="short", confirm_password="short")
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data
    with app.app_context():
        assert User.query.count() == 0


def test_register_requires_matching_passwords(client, app):
    response = _register(client, confirm_password="Different1!")
    assert response.status_code == 200
    assert b"Passwords must match" in response.data


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
def test_login_success_sets_session(client, app):
    with app.app_context():
        _make_user()
    response = _login(client, "operator1@sentinel.local", "CorrectHorseBattery99!")
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "_user_id" in session


def test_login_accepts_username(client, app):
    with app.app_context():
        _make_user()
    response = _login(client, "operator1", "CorrectHorseBattery99!")
    assert response.status_code == 302


def test_login_rejects_wrong_password(client, app):
    with app.app_context():
        _make_user()
    response = _login(client, "operator1", "WrongPass1!")
    assert response.status_code == 200
    assert b"Invalid email/username or password" in response.data


def test_login_locks_account_after_five_failures(client, app):
    with app.app_context():
        _make_user()

    for _ in range(5):
        _login(client, "operator1", "WrongPass1!")

    with app.app_context():
        assert User.query.filter_by(username="operator1").first().is_locked() is True

    response = _login(client, "operator1", "CorrectHorseBattery99!")
    assert response.status_code == 200
    assert b"locked" in response.data


def test_login_redirects_authenticated_users(client, app):
    with app.app_context():
        _make_user()
    _login(client, "operator1", "CorrectHorseBattery99!")
    response = client.get("/auth/login")
    assert response.status_code == 302
    assert "/" in response.headers["Location"]


def test_logout_clears_session(client, app):
    with app.app_context():
        _make_user()
    _login(client, "operator1", "CorrectHorseBattery99!")
    response = client.post("/auth/logout")
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_logout_requires_post(client):
    response = client.get("/auth/logout")
    assert response.status_code == 405


def test_remember_me_sets_cookie(client, app):
    with app.app_context():
        _make_user()
    response = client.post(
        "/auth/login",
        data={
            "identity": "operator1",
            "password": "CorrectHorseBattery99!",
            "remember": "y",
        },
    )
    assert "remember_token" in response.headers.get("Set-Cookie", "")


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
def test_verify_email_flow(client, app):
    with app.app_context():
        user = _make_user(verified=False)
        token = auth_service.verification_token_for(user)

    response = client.get(f"/auth/verify-email/{token}")
    assert response.status_code == 200
    assert b"Email Verified" in response.data

    with app.app_context():
        refreshed = db.session.get(User, user.id)
        assert refreshed.is_verified is True
        assert refreshed.email_verified_at is not None


def test_verify_email_rejects_invalid_token(client, app):
    with app.app_context():
        _make_user(verified=False)
    response = client.get("/auth/verify-email/not-a-valid-token")
    assert response.status_code == 200
    assert b"Verification Failed" in response.data


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def test_forgot_password_prevents_enumeration(client):
    response = client.post(
        "/auth/forgot-password",
        data={"email": "nobody@nowhere.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"reset link has been sent" in response.data


def test_password_reset_flow(client, app):
    with app.app_context():
        user = _make_user()
        token = auth_service.reset_token_for(user)

    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "BrandNewPass1!", "confirm_password": "BrandNewPass1!"},
    )
    assert response.status_code == 302

    with app.app_context():
        refreshed = db.session.get(User, user.id)
        assert refreshed.check_password("BrandNewPass1!") is True

    response = _login(client, "operator1", "BrandNewPass1!")
    assert response.status_code == 302


def test_password_reset_rejects_bad_token(client):
    response = client.get("/auth/reset-password/not-a-valid-token")
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------
def test_csrf_protection_blocks_tokenceless_posts(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/auth/login").get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    assert match is not None
    token = match.group(1)

    # Missing token -> rejected.
    response = client.post(
        "/auth/login", data={"identity": "x", "password": "y"}
    )
    assert response.status_code == 400

    # Valid token -> request is processed (unknown user -> login page).
    response = client.post(
        "/auth/login",
        data={
            "csrf_token": token,
            "identity": "x",
            "password": "y",
        },
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Role based access control
# ---------------------------------------------------------------------------
def test_role_required_enforces_access(app, client):
    with app.app_context():
        admin = _make_user(username="admin1", email="admin1@sentinel.local", role_slug=RoleSlug.ADMIN.value)
        operator = _make_user(username="op1", email="op1@sentinel.local", role_slug=RoleSlug.OPERATOR.value)

        test_bp = Blueprint("test_rbac", __name__)

        @test_bp.get("/admin-only")
        @role_required(RoleSlug.ADMIN.value)
        def admin_only():
            return "admin ok"

        @test_bp.get("/operator-only")
        @role_required(RoleSlug.OPERATOR.value, RoleSlug.ADMIN.value)
        def operator_only():
            return "operator ok"

        app.register_blueprint(test_bp)

    # Operator cannot access admin-only resource.
    _login(client, "op1", "CorrectHorseBattery99!")
    assert client.get("/admin-only").status_code == 403
    assert client.get("/operator-only").status_code == 200

    # Admin can access both.
    client.post("/auth/logout")
    _login(client, "admin1", "CorrectHorseBattery99!")
    assert client.get("/admin-only").status_code == 200
    assert client.get("/operator-only").status_code == 200

    # Anonymous users are redirected to login.
    client.post("/auth/logout")
    response = client.get("/operator-only")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
