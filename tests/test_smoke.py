"""Smoke tests — verify the application boots and core routes respond."""

import pytest

from app import create_app


@pytest.fixture()
def app():
    """A testing-configured application instance."""
    application = create_app("testing")
    yield application


@pytest.fixture()
def client(app):
    """A test client bound to the testing application."""
    return app.test_client()


def test_app_imports_and_factory_builds():
    """The application factory produces a configured Flask app."""
    application = create_app("testing")
    assert application.config["TESTING"] is True
    assert application.config["APP_NAME"] == "SentinelAI"


def test_unknown_config_falls_back_to_development():
    """An invalid config name must not crash the factory."""
    application = create_app("does-not-exist")
    assert application.config["DEBUG"] is True


def test_home_page_returns_ok(client):
    """The landing page responds with HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"SentinelAI" in response.data


def test_health_endpoint_reports_ok(client):
    """The /health probe returns a JSON ok payload."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "SentinelAI"


def test_unknown_route_renders_404_page(client):
    """Unknown URLs return the themed 404 page."""
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    assert b"Signal Lost" in response.data


def test_session_cookie_security_config(app):
    """Session cookie security flags are enabled by configuration."""
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["REMEMBER_COOKIE_HTTPONLY"] is True
