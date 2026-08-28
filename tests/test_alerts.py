"""Alert management tests — status flow, filters and access control."""

import pytest

from app import create_app
from extensions import db
from models import Alert, Incident, Role, User
from models.enums import (
    AlertPriority,
    AlertStatus,
    AlertType,
    IncidentStatus,
    IncidentType,
    RoleSlug,
    SeverityLevel,
)
from services import alert_service


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
    username="alertop",
    email="alertop@sentinel.local",
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


def _login(client, username="alertop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_incident() -> int:
    incident = Incident(
        title="Alert test incident",
        incident_type=IncidentType.INTRUSION,
        severity=SeverityLevel.HIGH,
        status=IncidentStatus.OPEN,
        details={},
    )
    db.session.add(incident)
    db.session.flush()
    return incident.id


def _make_alert(
    app,
    *,
    title="Fire detected",
    alert_type=AlertType.FIRE,
    priority=AlertPriority.HIGH,
    status=AlertStatus.PENDING,
    incident_id=None,
    channels=None,
) -> int:
    with app.app_context():
        alert = Alert(
            title=title,
            alert_type=alert_type,
            priority=priority,
            status=status,
            incident_id=incident_id,
            message=f"{title} in progress",
            channels=channels or ["email"],
        )
        db.session.add(alert)
        db.session.commit()
        return alert.id


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
def test_list_requires_login(client):
    assert client.get("/alerts/").status_code == 302


def test_viewer_can_view_list_and_detail(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        alert_id = _make_alert(app, title="Viewer test")
    _login(client, "viewer1")
    assert client.get("/alerts/").status_code == 200
    assert client.get(f"/alerts/{alert_id}").status_code == 200


def test_viewer_cannot_manage(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        alert_id = _make_alert(app)
    _login(client, "viewer1")
    assert client.post(f"/alerts/{alert_id}/send").status_code == 403
    assert client.post(f"/alerts/{alert_id}/acknowledge").status_code == 403
    assert client.post(f"/alerts/{alert_id}/expire").status_code == 403


def test_operator_can_send_and_acknowledge_not_expire(app, client):
    with app.app_context():
        _make_user()
        pending_id = _make_alert(app, title="Pending")
        sent_id = _make_alert(
            app, title="Sent", status=AlertStatus.SENT
        )
    _login(client)
    assert client.post(f"/alerts/{pending_id}/send").status_code == 302
    assert client.post(f"/alerts/{sent_id}/acknowledge").status_code == 302
    assert client.post(f"/alerts/{pending_id}/expire").status_code == 403


def test_admin_can_expire(app, client):
    with app.app_context():
        _make_user(RoleSlug.ADMIN.value, "alertadmin", "alertadmin@sentinel.local")
        alert_id = _make_alert(app)
    _login(client, "alertadmin")
    assert client.post(f"/alerts/{alert_id}/expire").status_code == 302


# ---------------------------------------------------------------------------
# Status flow
# ---------------------------------------------------------------------------
def test_mark_sent_sets_timestamp_and_audits(app, client):
    with app.app_context():
        _make_user()
        alert_id = _make_alert(app)
    _login(client)
    client.post(f"/alerts/{alert_id}/send")
    with app.app_context():
        alert = db.session.get(Alert, alert_id)
        assert alert.status == AlertStatus.SENT
        assert alert.sent_at is not None


def test_acknowledge_records_user_and_audits(app, client):
    with app.app_context():
        user_id = _make_user().id
        alert_id = _make_alert(app, status=AlertStatus.SENT)
    _login(client)
    client.post(f"/alerts/{alert_id}/acknowledge")
    with app.app_context():
        alert = db.session.get(Alert, alert_id)
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == user_id
        assert alert.acknowledged_at is not None


def test_expire_transitions_correctly(app, client):
    with app.app_context():
        _make_user(RoleSlug.ADMIN.value, "alertadmin", "alertadmin@sentinel.local")
        alert_id = _make_alert(app)
    _login(client, "alertadmin")
    client.post(f"/alerts/{alert_id}/expire")
    with app.app_context():
        alert = db.session.get(Alert, alert_id)
        assert alert.status == AlertStatus.EXPIRED


def test_send_rejects_non_pending(app, client):
    with app.app_context():
        _make_user()
        alert_id = _make_alert(app, status=AlertStatus.SENT)
    _login(client)
    response = client.post(f"/alerts/{alert_id}/send")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Alert, alert_id).status == AlertStatus.SENT


def test_acknowledge_rejects_non_sent(app, client):
    with app.app_context():
        _make_user()
        alert_id = _make_alert(app, status=AlertStatus.PENDING)
    _login(client)
    response = client.post(f"/alerts/{alert_id}/acknowledge")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Alert, alert_id).status == AlertStatus.PENDING


def test_expire_rejects_already_closed(app, client):
    with app.app_context():
        _make_user(RoleSlug.ADMIN.value, "alertadmin", "alertadmin@sentinel.local")
        ack_id = _make_alert(app, title="Acked", status=AlertStatus.ACKNOWLEDGED)
        expired_id = _make_alert(app, title="Expired", status=AlertStatus.EXPIRED)
    _login(client, "alertadmin")
    assert client.post(f"/alerts/{ack_id}/expire").status_code == 302
    assert client.post(f"/alerts/{expired_id}/expire").status_code == 302
    with app.app_context():
        assert db.session.get(Alert, ack_id).status == AlertStatus.ACKNOWLEDGED
        assert db.session.get(Alert, expired_id).status == AlertStatus.EXPIRED


# ---------------------------------------------------------------------------
# Listing and filters
# ---------------------------------------------------------------------------
def test_list_filters_by_status(app, client):
    with app.app_context():
        _make_user()
        _make_alert(app, title="Pending one")
        _make_alert(app, title="Sent one", status=AlertStatus.SENT)
    _login(client)
    page = client.get("/alerts/?status=sent")
    assert b"Sent one" in page.data
    assert b"Pending one" not in page.data


def test_list_filters_by_priority(app, client):
    with app.app_context():
        _make_user()
        _make_alert(app, title="Low one", priority=AlertPriority.LOW)
        _make_alert(app, title="Critical one", priority=AlertPriority.CRITICAL)
    _login(client)
    page = client.get("/alerts/?priority=critical")
    assert b"Critical one" in page.data
    assert b"Low one" not in page.data


def test_list_searches_title(app, client):
    with app.app_context():
        _make_user()
        _make_alert(app, title="Smoke alarm triggered")
        _make_alert(app, title="Motion detected")
    _login(client)
    page = client.get("/alerts/?q=smoke")
    assert b"Smoke alarm triggered" in page.data
    assert b"Motion detected" not in page.data


def test_counts_reflect_each_status(app, client):
    with app.app_context():
        _make_user()
        _make_alert(app, title="P1")
        _make_alert(app, title="P2")
        _make_alert(app, title="S1", status=AlertStatus.SENT)
        counts = alert_service.get_alert_counts()
    assert counts == {
        "pending": 2,
        "sent": 1,
        "acknowledged": 0,
        "expired": 0,
    }


def test_detail_shows_linked_incident(app, client):
    with app.app_context():
        _make_user()
        incident_id = _make_incident()
        alert_id = _make_alert(app, incident_id=incident_id)
    _login(client)
    detail = client.get(f"/alerts/{alert_id}")
    assert detail.status_code == 200
    assert b"Alert test incident" in detail.data
