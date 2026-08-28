"""Model tests — schema, relationships, cascade rules and password hashing."""

import pytest

from app import create_app
from extensions import db
from models import (
    Alert,
    AuditLog,
    Camera,
    Evidence,
    Incident,
    Notification,
    Role,
    Setting,
    User,
)
from models.enums import (
    AlertPriority,
    AlertStatus,
    AlertType,
    CameraSource,
    CameraStatus,
    EvidenceType,
    IncidentStatus,
    IncidentType,
    LogLevel,
    RoleSlug,
    SeverityLevel,
)
from services.seed_service import seed_database


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


def _make_operator() -> Role:
    role = Role(name="Operator", slug=RoleSlug.OPERATOR.value, description="ops")
    db.session.add(role)
    return role


def test_seed_creates_roles_settings_and_admin(app):
    """Seed is idempotent and creates roles, settings and an admin."""
    with app.app_context():
        first = seed_database(app)
        assert first["roles"] == 4
        assert first["settings"] == 8
        assert first["admin_created"] is True

        admin = User.query.filter_by(email="admin@sentinel.local").first()
        assert admin is not None
        assert admin.has_role(RoleSlug.ADMIN.value)
        assert admin.check_password(first["admin_password"])

        second = seed_database(app)
        assert second["roles"] == 0
        assert second["settings"] == 0
        assert second["admin_created"] is False


def test_password_hashing_roundtrip_and_lockout(app):
    """Bcrypt hashing, failed-login lockout and reset behave correctly."""
    with app.app_context():
        role = _make_operator()
        user = User(
            username="operator1",
            email="operator1@sentinel.local",
            first_name="Jane",
            last_name="Doe",
            role=role,
        )
        user.set_password("CorrectHorseBattery99!")
        db.session.add(user)
        db.session.commit()

        assert user.check_password("CorrectHorseBattery99!") is True
        assert user.check_password("wrong-password") is False
        assert user.full_name == "Jane Doe"
        assert user.has_role(RoleSlug.OPERATOR.value) is True
        assert user.has_role(RoleSlug.ADMIN.value) is False

        for _ in range(5):
            user.record_failed_login()
        assert user.is_locked() is True

        user.reset_failed_logins()
        assert user.is_locked() is False
        assert user.failed_login_attempts == 0


def test_camera_incident_evidence_alert_relationship(app):
    """Incident chains cascade to evidence and alerts on delete."""
    with app.app_context():
        camera = Camera(
            name="Gate A",
            location="Main Gate",
            source_type=CameraSource.WEBCAM,
            status=CameraStatus.ONLINE,
        )
        db.session.add(camera)
        db.session.flush()

        incident = Incident(
            camera=camera,
            incident_type=IncidentType.INTRUSION,
            title="Unauthorized entry detected",
            severity=SeverityLevel.HIGH,
            status=IncidentStatus.OPEN,
            confidence=0.87,
            details={"zone": "perimeter-a", "polygon": [[0, 0], [10, 0], [10, 10]]},
        )
        evidence = Evidence(
            incident=incident,
            evidence_type=EvidenceType.IMAGE,
            file_name="gate-a-20260813-1045.png",
            file_path="uploads/evidence/gate-a-20260813-1045.png",
            mime_type="image/png",
            file_size=184320,
        )
        alert = Alert(
            incident=incident,
            alert_type=AlertType.INTRUSION,
            priority=AlertPriority.CRITICAL,
            title="Intruder at Main Gate",
            message="Person entered restricted zone perimeter-a",
            channels=["dashboard", "email"],
        )
        db.session.add_all([incident, evidence, alert])
        db.session.commit()

        assert camera.incidents[0].id == incident.id
        assert incident.camera.name == "Gate A"
        assert incident.evidence[0].id == evidence.id
        assert incident.alerts[0].priority == AlertPriority.CRITICAL
        assert incident.details["zone"] == "perimeter-a"

        db.session.delete(incident)
        db.session.commit()

        assert Evidence.query.count() == 0
        assert Alert.query.count() == 0
        assert Camera.query.count() == 1


def test_settings_get_set_roundtrip(app):
    """Settings can be read, written and fall back to defaults."""
    with app.app_context():
        Setting.set("alerts.confidence", "0.55", group="alerts")
        db.session.commit()

        assert Setting.get("alerts.confidence") == "0.55"
        assert Setting.get("missing.key", "fallback") == "fallback"


def test_notification_read_state(app):
    """Notifications track read state and unread counts."""
    with app.app_context():
        role = _make_operator()
        user = User(username="analyst1", email="analyst1@sentinel.local", role=role)
        user.set_password("TempPass123!")
        db.session.add(user)
        db.session.flush()

        notification = Notification(
            user=user,
            title="High priority alert",
            message="Weapon detected at Camera 3",
        )
        db.session.add(notification)
        db.session.commit()

        assert Notification.unread_count(user.id) == 1
        notification.mark_read()
        db.session.commit()
        assert Notification.unread_count(user.id) == 0
        assert notification.read_at is not None


def test_audit_log_recording(app):
    """Audit entries persist action and metadata."""
    with app.app_context():
        entry = AuditLog.record(
            action="login.success",
            module="auth",
            level=LogLevel.INFO,
            message="Administrator signed in",
            details={"method": "password"},
        )
        assert entry.id is not None
        assert AuditLog.query.count() == 1
        assert AuditLog.query.filter_by(action="login.success").first() is not None
