"""Enumerated values shared across the data model."""

from enum import Enum


class RoleSlug(str, Enum):
    """System roles controlling access levels."""

    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"


class CameraSource(str, Enum):
    """How a camera delivers its video stream."""

    WEBCAM = "webcam"
    IP = "ip"
    RTSP = "rtsp"


class CameraStatus(str, Enum):
    """Current operational state of a camera."""

    ONLINE = "online"
    OFFLINE = "offline"
    DISABLED = "disabled"


class IncidentType(str, Enum):
    """Categories of events the detection suite can raise."""

    FIRE = "fire"
    SMOKE = "smoke"
    WEAPON = "weapon"
    INTRUSION = "intrusion"
    CROWD = "crowd"
    PERSON = "person"
    UNKNOWN = "unknown"


class SeverityLevel(str, Enum):
    """Impact of an incident."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Lifecycle state of an incident."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EvidenceType(str, Enum):
    """Kind of stored evidence."""

    IMAGE = "image"
    VIDEO = "video"


class AlertType(str, Enum):
    """Source category of an alert."""

    INCIDENT = "incident"
    INTRUSION = "intrusion"
    FIRE = "fire"
    WEAPON = "weapon"
    CROWD = "crowd"
    SYSTEM = "system"


class AlertPriority(str, Enum):
    """Urgency of an alert."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Lifecycle state of an alert."""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"


class LogLevel(str, Enum):
    """Severity of an audit log entry."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
