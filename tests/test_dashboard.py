"""Dashboard tests — access control, KPIs, chart series and activity feeds."""

from datetime import timedelta

import pytest

from app import create_app
from extensions import db
from models import Alert, AuditLog, Camera, Incident, Role, User
from models.base import utcnow
from models.enums import (
    AlertPriority,
    AlertStatus,
    AlertType,
    CameraStatus,
    IncidentStatus,
    IncidentType,
    RoleSlug,
    SeverityLevel,
)
from services import dashboard_service


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


def _make_user(role_slug=RoleSlug.OPERATOR.value, username="dash", email="dash@sentinel.local") -> User:
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


def _login(client) -> None:
    client.post(
        "/auth/login",
        data={"identity": "dash", "password": "CorrectHorseBattery99!"},
    )


def _make_camera(name: str, status: CameraStatus) -> Camera:
    camera = Camera(name=name, status=status)
    db.session.add(camera)
    return camera


def _make_incident(
    title: str,
    incident_type: IncidentType = IncidentType.INTRUSION,
    severity: SeverityLevel = SeverityLevel.MEDIUM,
    status: IncidentStatus = IncidentStatus.OPEN,
    detected_at=None,
) -> Incident:
    incident = Incident(
        title=title,
        incident_type=incident_type,
        severity=severity,
        status=status,
        detected_at=detected_at or utcnow(),
    )
    db.session.add(incident)
    return incident


def _make_alert(
    title: str,
    priority: AlertPriority = AlertPriority.MEDIUM,
    status: AlertStatus = AlertStatus.PENDING,
) -> Alert:
    alert = Alert(
        title=title,
        alert_type=AlertType.SYSTEM,
        priority=priority,
        status=status,
    )
    db.session.add(alert)
    return alert


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def test_dashboard_requires_login(client):
    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_dashboard_renders_for_authenticated_user(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert b"Cameras Online" in response.data
    assert b"Active Incidents" in response.data
    assert b"Unhandled Alerts" in response.data
    assert b"Verified Users" in response.data


def test_dashboard_renders_empty_state(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert b"No incidents yet" in response.data
    assert b"No alerts yet" in response.data
    assert b"window.SENTINEL_DASHBOARD" in response.data


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
def test_kpis_reflect_database(app, client):
    with app.app_context():
        _make_user()
        _make_camera("Front Gate", CameraStatus.ONLINE)
        _make_camera("Back Gate", CameraStatus.ONLINE)
        _make_camera("Lobby", CameraStatus.OFFLINE)
        _make_camera("Storage", CameraStatus.DISABLED)
        _make_incident("Fire in kitchen", status=IncidentStatus.OPEN, severity=SeverityLevel.CRITICAL)
        _make_incident("Person in restricted zone", status=IncidentStatus.INVESTIGATING)
        _make_incident("Old resolved event", status=IncidentStatus.RESOLVED)
        _make_incident("Closed review", status=IncidentStatus.CLOSED)
        _make_alert("Critical fire alert", priority=AlertPriority.CRITICAL)
        _make_alert("Sent alert", status=AlertStatus.SENT)
        _make_alert("Acknowledged alert", status=AlertStatus.ACKNOWLEDGED)
        db.session.commit()

        kpis = dashboard_service.get_kpis()

        assert kpis["cameras"]["total"] == 4
        assert kpis["cameras"]["online"] == 2
        assert kpis["cameras"]["offline"] == 1
        assert kpis["cameras"]["disabled"] == 1

        assert kpis["incidents"]["active"] == 2
        assert kpis["incidents"]["open"] == 1
        assert kpis["incidents"]["resolved"] == 1
        assert kpis["incidents"]["total"] == 4

        assert kpis["alerts"]["unhandled"] == 2
        assert kpis["alerts"]["critical"] == 1
        assert kpis["alerts"]["acknowledged"] == 1
        assert kpis["alerts"]["total"] == 3

        assert kpis["users"]["total"] == 1
        assert kpis["users"]["verified"] == 1

    # Rendered KPI card shows "2 / 4" for cameras online / total.
    _login(client)
    page = client.get("/dashboard/")
    assert page.status_code == 200
    assert b"2<small> / 4</small>" in page.data


# ---------------------------------------------------------------------------
# Chart series
# ---------------------------------------------------------------------------
def test_incident_trend_returns_daily_series(app):
    with app.app_context():
        today = utcnow()
        yesterday = today - timedelta(days=1)
        _make_incident("Today event", detected_at=today)
        _make_incident("Yesterday event", detected_at=yesterday)
        db.session.commit()

        trend = dashboard_service.get_incident_trend(days=14)
    assert len(trend["labels"]) == 14
    assert len(trend["values"]) == 14
    assert trend["values"][-1] == 1
    assert trend["values"][-2] == 1
    assert sum(trend["values"]) == 2


def test_alert_trend_returns_daily_series(app):
    with app.app_context():
        _make_alert("Today alert")
        db.session.commit()

        trend = dashboard_service.get_alert_trend(days=14)
    assert len(trend["labels"]) == 14
    assert trend["values"][-1] == 1


def test_incidents_by_type_counts(app):
    with app.app_context():
        _make_incident("Kitchen fire", incident_type=IncidentType.FIRE)
        _make_incident("Hallway fire", incident_type=IncidentType.FIRE)
        _make_incident("Suspicious weapon", incident_type=IncidentType.WEAPON)
        db.session.commit()

        by_type = dashboard_service.get_incidents_by_type()
    assert by_type["labels"] == ["Fire", "Weapon"]
    assert by_type["values"] == [2, 1]


def test_incidents_by_severity_ordered(app):
    with app.app_context():
        _make_incident("Medium", severity=SeverityLevel.MEDIUM)
        _make_incident("Low", severity=SeverityLevel.LOW)
        _make_incident("Critical", severity=SeverityLevel.CRITICAL)
        db.session.commit()

        by_severity = dashboard_service.get_incidents_by_severity()
    assert by_severity["labels"] == ["Low", "Medium", "Critical"]
    assert by_severity["values"] == [1, 1, 1]


def test_camera_status_split_includes_all_states(app):
    with app.app_context():
        _make_camera("A", CameraStatus.ONLINE)
        _make_camera("B", CameraStatus.ONLINE)
        _make_camera("C", CameraStatus.OFFLINE)
        db.session.commit()

        split = dashboard_service.get_camera_status_split()
    assert split["labels"] == ["Online", "Offline", "Disabled"]
    assert split["values"] == [2, 1, 0]


# ---------------------------------------------------------------------------
# Activity feeds
# ---------------------------------------------------------------------------
def test_recent_incidents_and_alerts_ordered(app):
    with app.app_context():
        _make_incident("Newest", detected_at=utcnow())
        _make_incident("Older", detected_at=utcnow() - timedelta(hours=2))
        _make_alert("Newest alert")
        _make_alert("Older alert", status=AlertStatus.SENT)
        db.session.commit()

        incidents = dashboard_service.get_recent_incidents(5)
        alerts = dashboard_service.get_recent_alerts(5)
    assert [incident.title for incident in incidents] == ["Newest", "Older"]
    assert [alert.title for alert in alerts] == ["Newest alert", "Older alert"]


def test_recent_activity_from_audit_log(app, client):
    with app.app_context():
        user = _make_user()
        AuditLog.record(action="auth.login", module="auth", user_id=user.id)

        activity = dashboard_service.get_recent_activity(8)
        assert len(activity) == 1
        assert activity[0].action == "auth.login"
        assert activity[0].user.username == "dash"
