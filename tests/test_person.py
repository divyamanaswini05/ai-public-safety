"""Person detection — real-time YOLO person detector, routes, access control.

Person detection uses Ultralytics' default COCO-pretrained model, so it is
the one detector that is genuinely functional as soon as ``ultralytics`` is
installed (weights auto-download on first use).
"""

import pytest

from app import create_app
from extensions import db
from models import Camera, Incident, Role, User
from models.enums import IncidentStatus, IncidentType, RoleSlug, SeverityLevel
from ai.detectors_person import PersonDetector, person_detector
from services import camera_service


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
    username="personop",
    email="personop@sentinel.local",
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


def _login(client, username="personop", password="CorrectHorseBattery99!") -> None:
    client.post("/auth/login", data={"identity": username, "password": password})


def _make_camera() -> int:
    return camera_service.create_camera(
        name="Person Cam", location="Lobby",
        source_type="ip", ip_address="192.0.2.91", port=80,
    ).id


def _make_person_incident(title: str = "person detected") -> int:
    incident = Incident(
        title=title, incident_type=IncidentType.PERSON,
        severity=SeverityLevel.MEDIUM, status=IncidentStatus.OPEN, details={},
    )
    db.session.add(incident)
    db.session.commit()
    return incident.id


# --- Detector unit tests (fast, mocked) ---
def test_detector_name_and_type():
    det = PersonDetector()
    assert det.name == "person"
    assert det.incident_type == IncidentType.PERSON


def test_detector_not_available_without_yolo(monkeypatch):
    det = PersonDetector()
    monkeypatch.setattr("ai.detectors_person._yolo_available", lambda: False)
    assert det.available is False
    assert det.detect(type("F", (), {"image": b"data", "metadata": {}})()) == []


def test_detector_available_with_yolo(monkeypatch):
    det = PersonDetector()
    monkeypatch.setattr("ai.detectors_person._yolo_available", lambda: True)
    assert det.available is True
    assert det.weights_present is True


def test_empty_image_returns_no_detections(app):
    det = PersonDetector()
    assert det.detect(type("F", (), {"image": b"", "metadata": {}})()) == []


def test_severity_thresholds():
    det = PersonDetector()
    assert det._severity(0.95).value == "high"
    assert det._severity(0.75).value == "medium"
    assert det._severity(0.40).value == "low"


def test_filters_non_person_classes(monkeypatch):
    det = PersonDetector(confidence_threshold=0.0)
    from ai.base import BoundingBox, DetectionResult

    def fake_boxes():
        class Coord:
            def __init__(self, coords):
                self.coords = coords
            def tolist(self):
                return list(self.coords)
        class B:
            def __init__(self, cls, conf, coords):
                self.cls = [cls]
                self.conf = [conf]
                self.xyxy = [Coord(coords)]
        return [B(0, 0.9, [0, 0, 100, 100]), B(1, 0.95, [0, 0, 50, 50])]

    class FakeResult:
        names = {0: "person", 1: "bus"}
        boxes = fake_boxes()

    class FakeModel:
        def __call__(self, img, verbose=False):
            return [FakeResult()]

    monkeypatch.setattr(det, "_load_model", lambda: FakeModel())
    monkeypatch.setattr("ai.detectors_person._OPENCV_AVAILABLE", False)
    monkeypatch.setattr("ai.detectors_person._yolo_available", lambda: True)
    results = det.detect(type("F", (), {"image": b"junk", "metadata": {}})())
    assert len(results) == 1
    assert results[0].incident_type == IncidentType.PERSON


def test_registered_in_engine(app):
    from ai.registry import get_detector
    with app.app_context():
        assert get_detector("person") is person_detector


def test_available_in_list_models(app):
    from ai.weights import list_models
    with app.app_context():
        models = list_models()
        assert "person" in models


# --- Access control ---
def test_index_requires_login(client):
    assert client.get("/ai/").status_code == 302


def test_viewer_can_view_index(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    assert client.get("/ai/").status_code == 200


def test_viewer_cannot_run(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        camera_id = _make_camera()
    _login(client, "viewer1")
    assert client.post("/ai/run", data={"camera_id": camera_id, "detector": "person"}).status_code == 403


def test_index_shows_person_model_available(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    page = client.get("/ai/")
    assert b"person" in page.data
