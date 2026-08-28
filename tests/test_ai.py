"""AI detection engine tests — registry, detectors, pipeline and routes."""

import pytest

from ai import detectors as detectors_module
from ai.base import BaseDetector, DetectionResult, Frame
from ai.frames import FrameSourceError, OpenCVFrameSource, SyntheticFrameSource
from ai.pipeline import DetectionEngine, process_detection
from ai.registry import (
    get_detector,
    get_detectors,
    register_detector,
    unregister_detector,
)
from ai.service import engine_status, run_detection
from app import create_app
from extensions import db
from models import Alert, AuditLog, Camera, Incident, Role, Setting, User
from models.enums import (
    AlertPriority,
    AlertStatus,
    AlertType,
    CameraStatus,
    CameraSource,
    IncidentStatus,
    IncidentType,
    RoleSlug,
    SeverityLevel,
)


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


def _make_user(role_slug=RoleSlug.OPERATOR.value, username="ai", email="ai@sentinel.local") -> User:
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


def _login(client, username="ai") -> None:
    client.post(
        "/auth/login",
        data={"identity": username, "password": "CorrectHorseBattery99!"},
    )


def _make_camera(
    name: str = "Camera One",
    source_type: CameraSource = CameraSource.WEBCAM,
    status: CameraStatus = CameraStatus.ONLINE,
    is_active: bool = True,
    ip_address: str | None = None,
    source_url: str | None = None,
) -> Camera:
    camera = Camera(
        name=name,
        source_type=source_type,
        status=status,
        is_active=is_active,
        ip_address=ip_address,
        source_url=source_url,
    )
    db.session.add(camera)
    db.session.flush()
    return camera


class _StubDetector(BaseDetector):
    """A named no-op detector used only to exercise the registry."""

    name = "stub"

    def detect(self, frame: Frame) -> list[DetectionResult]:
        return []


def _frame(index: int, camera_id: int | None = 1) -> Frame:
    return Frame(
        image=b"",
        camera_id=camera_id,
        metadata={"source": "synthetic", "seed": 0, "index": index},
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_registry_roundtrip():
    detector = _StubDetector()
    register_detector(detector)
    try:
        assert get_detector("stub") is detector
        assert detector in get_detectors()
    finally:
        unregister_detector("stub")
    assert get_detector("stub") is None


def test_registry_rejects_duplicate():
    register_detector(_StubDetector())
    try:
        with pytest.raises(ValueError):
            register_detector(_StubDetector())
    finally:
        unregister_detector("stub")


def test_registry_rejects_non_detector():
    with pytest.raises(TypeError):
        register_detector(object())  # type: ignore[arg-type]


def test_base_detector_is_abstract():
    with pytest.raises(TypeError):
        BaseDetector()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Simulation detector
# ---------------------------------------------------------------------------
def test_simulation_detector_schedule():
    detector = detectors_module.SimulationDetector(emit_every=3)
    assert detector.detect(_frame(0))[0].incident_type == IncidentType.FIRE
    assert detector.detect(_frame(0))[0].confidence == 0.5
    assert detector.detect(_frame(1)) == []
    assert detector.detect(_frame(3))[0].incident_type == IncidentType.CROWD
    assert detector.detect(_frame(3))[0].confidence == 0.71
    assert detector.detect(_frame(6))[0].severity == SeverityLevel.CRITICAL


def test_simulation_detector_is_deterministic():
    detector = detectors_module.SimulationDetector()
    first = detector.detect(_frame(6))
    second = detector.detect(_frame(6))
    assert first[0].confidence == second[0].confidence
    assert first[0].incident_type == second[0].incident_type


# ---------------------------------------------------------------------------
# Frame sources
# ---------------------------------------------------------------------------
def test_synthetic_source_streams_limited_frames():
    source = SyntheticFrameSource(camera_id=7, frame_count=10, seed=3)
    frames = list(source.stream())
    assert len(frames) == 10
    assert all(frame.camera_id == 7 for frame in frames)
    assert frames[0].metadata["seed"] == 3
    assert frames[5].metadata["index"] == 5


def test_synthetic_source_respects_stream_limit():
    source = SyntheticFrameSource(camera_id=1, frame_count=20, seed=0)
    frames = list(source.stream(limit=5))
    assert len(frames) == 5


def test_opencv_source_requires_opencv(monkeypatch):
    monkeypatch.setattr("ai.frames._OPENCV_AVAILABLE", False)
    with pytest.raises(FrameSourceError):
        OpenCVFrameSource(0)


# ---------------------------------------------------------------------------
# process_detection
# ---------------------------------------------------------------------------
def test_detection_below_confidence_ignored(app):
    with app.app_context():
        camera = _make_camera()
        db.session.commit()
        result = DetectionResult(
            detector="simulation",
            incident_type=IncidentType.FIRE,
            label="Low confidence fire",
            confidence=0.1,
            camera_id=camera.id,
        )
        assert process_detection(result) is None
        assert Incident.query.count() == 0


def test_detection_without_camera_ignored(app):
    with app.app_context():
        result = DetectionResult(
            detector="simulation",
            incident_type=IncidentType.FIRE,
            label="Orphan detection",
            confidence=0.9,
        )
        assert process_detection(result) is None


def test_detection_on_disabled_camera_ignored(app):
    with app.app_context():
        camera = _make_camera(is_active=False)
        db.session.commit()
        result = DetectionResult(
            detector="simulation",
            incident_type=IncidentType.FIRE,
            label="Ignored fire",
            confidence=0.9,
            camera_id=camera.id,
        )
        assert process_detection(result) is None


def test_detection_creates_incident_and_alert(app):
    with app.app_context():
        camera = _make_camera()
        db.session.commit()
        result = DetectionResult(
            detector="simulation",
            incident_type=IncidentType.FIRE,
            label="Fire detected",
            confidence=0.92,
            severity=SeverityLevel.CRITICAL,
            camera_id=camera.id,
        )
        incident = process_detection(result)
        assert incident is not None
        assert incident.status == IncidentStatus.OPEN
        assert incident.confidence == 0.92
        assert incident.severity == SeverityLevel.CRITICAL
        assert incident.details["detector"] == "simulation"

        alert = Alert.query.filter_by(incident_id=incident.id).first()
        assert alert is not None
        assert alert.priority == AlertPriority.CRITICAL
        assert alert.alert_type == AlertType.FIRE
        assert alert.status == AlertStatus.PENDING
        assert "dashboard" in alert.channels

        assert AuditLog.query.filter_by(action="ai.detection").count() == 1


def test_detection_deduplicates_within_cooldown(app):
    with app.app_context():
        camera = _make_camera()
        db.session.commit()

        def make():
            return DetectionResult(
                detector="simulation",
                incident_type=IncidentType.WEAPON,
                label="Weapon",
                confidence=0.8,
                camera_id=camera.id,
            )

        assert process_detection(make()) is not None
        assert process_detection(make()) is None
        assert Incident.query.count() == 1
        assert Alert.query.count() == 1


def test_confidence_threshold_setting_takes_effect(app):
    with app.app_context():
        camera = _make_camera()
        Setting.set("alerts.confidence", "0.99", group="alerts")
        db.session.commit()
        result = DetectionResult(
            detector="simulation",
            incident_type=IncidentType.FIRE,
            label="Below tuned threshold",
            confidence=0.5,
            camera_id=camera.id,
        )
        assert process_detection(result) is None


# ---------------------------------------------------------------------------
# DetectionEngine
# ---------------------------------------------------------------------------
def test_engine_analyzes_frames_and_persists(app):
    with app.app_context():
        camera = _make_camera()
        db.session.commit()
        source = SyntheticFrameSource(camera_id=camera.id, frame_count=10, seed=1)
        engine = DetectionEngine(
            detectors=[detectors_module.SimulationDetector(emit_every=3)]
        )
        detections, created, frames = engine.analyze_frames(source, save=True)
        assert frames == 10
        assert len(detections) == 4
        assert len(created) == 4
        assert Incident.query.count() == 4
        assert Alert.query.count() == 4


def test_engine_can_run_without_saving(app):
    with app.app_context():
        camera = _make_camera()
        db.session.commit()
        source = SyntheticFrameSource(camera_id=camera.id, frame_count=6, seed=1)
        engine = DetectionEngine(
            detectors=[detectors_module.SimulationDetector(emit_every=3)]
        )
        detections, created, frames = engine.analyze_frames(source, save=False)
        assert frames == 6
        assert len(detections) == 2
        assert created == []
        assert Incident.query.count() == 0


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
def test_run_detection_rejects_unknown_detector(app):
    with app.app_context():
        camera = _make_camera()
        db.session.commit()
        result = run_detection(camera, detector_name="nonexistent")
        assert result["status"] == "unknown_detector"


def test_run_detection_webcam_uses_synthetic_source(app):
    with app.app_context():
        camera = _make_camera(source_type=CameraSource.WEBCAM)
        db.session.commit()
        result = run_detection(camera, detector_name="simulation")
        assert result["status"] == "ok"
        assert result["source"] == "synthetic"
        assert result["detections"] == 4
        assert result["incidents_created"] == 4
        assert len(result["incident_ids"]) == 4


def test_run_detection_without_endpoint_uses_synthetic(app):
    # In the testing config real capture is forced off (FORCE_SYNTHETIC_SOURCE),
    # so even an IP camera with no endpoint falls back to a working synthetic
    # source rather than failing to capture.
    with app.app_context():
        camera = _make_camera(
            source_type=CameraSource.IP, ip_address=None, source_url=None
        )
        db.session.commit()
        result = run_detection(camera, detector_name="simulation")
    assert result["status"] == "ok"
    assert result["source"] == "synthetic"


def test_engine_status_lists_detectors(app):
    with app.app_context():
        status = engine_status()
    assert isinstance(status["detectors"], list)
    assert "simulation" in status["detectors"]
    assert isinstance(status["opencv"], bool)
    assert isinstance(status["yolo"], bool)


# ---------------------------------------------------------------------------
# Weights management
# ---------------------------------------------------------------------------
def test_weights_helpers(app, monkeypatch, tmp_path):
    from ai import weights as weights_module

    monkeypatch.setattr(weights_module, "_WEIGHTS_DIR", str(tmp_path))

    assert weights_module.weights_dir() == str(tmp_path)
    assert weights_module.model_filename("fire") == "fire-smoke.pt"
    assert weights_module.model_filename("nope") is None
    assert weights_module.model_path("fire") is None

    with pytest.raises(FileNotFoundError):
        weights_module.require_model("fire")

    model_file = tmp_path / "fire-smoke.pt"
    model_file.write_bytes(b"fake-yolo-weights")
    assert weights_module.model_path("fire") == str(model_file)
    assert weights_module.require_model("fire") == str(model_file)

    models = weights_module.list_models()
    assert set(models) == {"fire", "weapon", "crowd", "intrusion", "face", "person"}
    assert models["fire"]["available"] is True
    assert models["weapon"]["available"] is False


def test_ai_page_shows_model_availability(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.get("/ai/")
    assert response.status_code == 200
    assert b"Trained models" in response.data
    assert b"fire-smoke.pt" in response.data
    assert b"Missing" in response.data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def test_ai_index_requires_login(client):
    response = client.get("/ai/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_ai_index_renders_for_any_role(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
    _login(client, "viewer1")
    response = client.get("/ai/")
    assert response.status_code == 200
    assert b"Registered Detectors" in response.data
    assert b"simulation" in response.data
    assert b"Confidence threshold" in response.data


def test_run_requires_admin_or_operator(app, client):
    with app.app_context():
        _make_user(RoleSlug.VIEWER.value, "viewer1", "viewer1@sentinel.local")
        camera = _make_camera()
        db.session.commit()
        camera_id = camera.id
    _login(client, "viewer1")
    response = client.post("/ai/run", data={"camera_id": camera_id})
    assert response.status_code == 403


def test_run_creates_incidents(app, client):
    with app.app_context():
        _make_user()
        camera = _make_camera()
        db.session.commit()
        camera_id = camera.id
    _login(client)
    response = client.post(
        "/ai/run", data={"camera_id": camera_id, "detector": "simulation"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ai/")
    with app.app_context():
        assert Incident.query.count() == 4


def test_run_404_for_missing_camera(app, client):
    with app.app_context():
        _make_user()
    _login(client)
    response = client.post("/ai/run", data={"camera_id": 9999})
    assert response.status_code == 404


def test_run_flashes_warning_for_unknown_detector(app, client):
    with app.app_context():
        _make_user()
        camera = _make_camera()
        db.session.commit()
        camera_id = camera.id
    _login(client)
    response = client.post(
        "/ai/run", data={"camera_id": camera_id, "detector": "nope"}
    )
    assert response.status_code == 302
