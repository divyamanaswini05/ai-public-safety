"""Application configuration.

Settings are loaded from environment variables (optionally via a ``.env``
file) with secure, development-friendly defaults. Production secrets must be
provided through the environment and must never be committed to the repo.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from a local `.env` file if present.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

TRUE_VALUES = {"1", "true", "yes", "on"}


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    """Parse an environment value into a boolean."""
    if isinstance(value, bool):
        return value
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in TRUE_VALUES


def _as_int(value: str | None, default: int) -> int:
    """Parse an environment value into an integer, falling back on error."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class BaseConfig:
    """Shared configuration for every environment."""

    # Flask ----------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-in-production")

    # Database --------------------------------------------------------------
    # SQLite by default (instance/database.db). Point DATABASE_URL at MySQL
    # or PostgreSQL when deploying; the application is DB-agnostic.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'instance' / 'database.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Flask-Mail -------------------------------------------------------------
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = _as_int(os.getenv("MAIL_PORT"), 587)
    MAIL_USE_TLS = _as_bool(os.getenv("MAIL_USE_TLS"), True)
    MAIL_USE_SSL = _as_bool(os.getenv("MAIL_USE_SSL"), False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@sentinel.local")

    # Sessions & cookies -----------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), False)
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=_as_int(os.getenv("SESSION_TIMEOUT_MINUTES"), 30)
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # CSRF (Flask-WTF) --------------------------------------------------------
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = False

    # Camera credential encryption (Module 5) ----------------------------------
    # Fernet key for RTSP/IP stream passwords. When empty, a key is derived
    # from SECRET_KEY; production deployments should set FERNET_KEY explicitly.
    FERNET_KEY = os.getenv("FERNET_KEY", "")

    # Uploads ----------------------------------------------------------------
    # 250 MB allows multi-second incident recordings as well as screenshots.
    MAX_CONTENT_LENGTH = 250 * 1024 * 1024

    # Application paths --------------------------------------------------------
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    EVIDENCE_FOLDER = BASE_DIR / "uploads" / "evidence"
    ALERT_FOLDER = BASE_DIR / "uploads" / "alerts"
    WEIGHTS_FOLDER = BASE_DIR / "ai" / "weights"

    # AI / surveillance defaults (tuned in Modules 7-13) -----------------------
    DEFAULT_CONFIDENCE = 0.45
    CROWD_THRESHOLD = 50
    RECORDING_DURATION = 30
    FPS_TARGET = 15
    # When True, always use the deterministic synthetic frame source instead of
    # real OpenCV capture. Enabled in testing so detector tests never try to
    # open a physical/network camera.
    FORCE_SYNTHETIC_SOURCE = False

    # Pagination ----------------------------------------------------------------
    ITEMS_PER_PAGE = 10

    # Rate limiting (enforced from Module 19 onwards) ---------------------------
    RATE_LIMIT_LOGIN = "5 per minute"
    RATE_LIMIT_REGISTER = "3 per hour"


class DevelopmentConfig(BaseConfig):
    """Local development with full error traces."""

    DEBUG = True


class ProductionConfig(BaseConfig):
    """Hardened settings for a live deployment."""

    DEBUG = False
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), True)
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")


class TestingConfig(BaseConfig):
    """Isolated, fast configuration used by the test suite."""

    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    FORCE_SYNTHETIC_SOURCE = True


# Registry used by the application factory.
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
