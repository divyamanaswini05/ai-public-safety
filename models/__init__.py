"""Database models.

Importing this package registers every table with the ORM so that
Flask-Migrate can autogenerate migrations.
"""

from models.alert import Alert
from models.audit_log import AuditLog
from models.base import TimestampMixin, enum_type, utcnow
from models.camera import Camera
from models.evidence import Evidence
from models.incident import Incident
from models.notification import Notification
from models.role import Role
from models.setting import Setting
from models.user import User

__all__ = [
    "Alert",
    "AuditLog",
    "Camera",
    "Evidence",
    "Incident",
    "Notification",
    "Role",
    "Setting",
    "TimestampMixin",
    "User",
    "enum_type",
    "utcnow",
]
