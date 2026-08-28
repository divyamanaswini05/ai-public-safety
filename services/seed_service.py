"""Database seeding — default roles, settings and the initial admin account."""

import os
import secrets
from typing import Any

from flask import Flask

from extensions import db
from models import Role, Setting, User
from models.enums import RoleSlug

ADMIN_EMAIL = "admin@sentinel.local"
ADMIN_USERNAME = "admin"

DEFAULT_ROLES: list[tuple[RoleSlug, str, str]] = [
    (RoleSlug.ADMIN, "Administrator", "Full system access including user management"),
    (RoleSlug.OPERATOR, "Operator", "Operates cameras, monitors feeds and manages alerts"),
    (RoleSlug.ANALYST, "Analyst", "Reviews incidents, evidence and analytics reports"),
    (RoleSlug.VIEWER, "Viewer", "Read-only access to dashboards and reports"),
]

DEFAULT_SETTINGS: list[tuple[str, str, str, str]] = [
    ("system.name", "SentinelAI", "system", "Display name of the platform"),
    ("system.theme", "dark", "system", "Default UI theme"),
    (
        "alerts.channels",
        '["dashboard", "email", "sms", "browser"]',
        "alerts",
        "Default notification channels",
    ),
    ("alerts.confidence", "0.45", "alerts", "Minimum detection confidence for alerts"),
    (
        "alerts.cooldown_seconds",
        "60",
        "alerts",
        "Minimum seconds between duplicate alerts",
    ),
    ("crowd.threshold", "50", "crowd", "People count that triggers a crowd alert"),
    (
        "surveillance.recording_duration",
        "30",
        "surveillance",
        "Seconds of video captured per incident",
    ),
    ("surveillance.fps", "15", "surveillance", "Target frames per second for detection"),
]


def seed_database(app: Flask) -> dict[str, Any]:
    """Create default roles, settings and the initial admin account.

    Idempotent — safe to run repeatedly. Returns a summary of the changes.
    """
    with app.app_context():
        result: dict[str, Any] = {
            "roles": 0,
            "settings": 0,
            "admin_created": False,
            "admin_password": None,
        }

        for slug, name, description in DEFAULT_ROLES:
            if Role.query.filter_by(slug=slug.value).first() is None:
                db.session.add(
                    Role(name=name, slug=slug.value, description=description)
                )
                result["roles"] += 1

        for key, value, group, description in DEFAULT_SETTINGS:
            if Setting.query.filter_by(key=key).first() is None:
                db.session.add(
                    Setting(key=key, value=value, group=group, description=description)
                )
                result["settings"] += 1

        admin_role = Role.query.filter_by(slug=RoleSlug.ADMIN.value).first()
        if admin_role is not None and User.query.filter_by(email=ADMIN_EMAIL).first() is None:
            password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
            admin = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                first_name="System",
                last_name="Administrator",
                role=admin_role,
                is_active=True,
                is_verified=True,
            )
            admin.set_password(password)
            db.session.add(admin)
            result["admin_created"] = True
            result["admin_password"] = password

        db.session.commit()
        return result
