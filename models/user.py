"""User model — accounts, credentials and login state."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import bcrypt, db
from models.base import TimestampMixin, utcnow

if TYPE_CHECKING:
    from models.alert import Alert
    from models.audit_log import AuditLog
    from models.incident import Incident
    from models.notification import Notification
    from models.role import Role

DEFAULT_MAX_FAILED_LOGINS = 5
DEFAULT_LOCK_MINUTES = 15


class User(db.Model, TimestampMixin, UserMixin):
    """An application account with role, credentials and lockout state."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        db.String(64), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        db.String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(db.String(64))
    last_name: Mapped[str | None] = mapped_column(db.String(64))

    role_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("roles.id", ondelete="SET NULL"), index=True
    )

    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(db.DateTime)

    failed_login_attempts: Mapped[int] = mapped_column(
        db.Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(db.DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(db.DateTime)

    role: Mapped["Role | None"] = relationship(back_populates="users")
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="created_by_user"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    acknowledged_alerts: Mapped[list["Alert"]] = relationship(
        back_populates="acknowledged_by_user"
    )
    logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    @property
    def full_name(self) -> str:
        """Display name derived from first/last name, falling back to username."""
        parts = [part for part in (self.first_name, self.last_name) if part]
        return " ".join(parts).strip() or self.username

    def set_password(self, raw_password: str) -> None:
        """Hash and store a password using bcrypt."""
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode(
            "utf-8"
        )

    def check_password(self, raw_password: str) -> bool:
        """Return whether the supplied password matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    def has_role(self, *slugs: str) -> bool:
        """Return whether the user belongs to any of the given role slugs."""
        return self.role is not None and self.role.slug in slugs

    def is_locked(self) -> bool:
        """Return whether the account is currently locked out."""
        return self.locked_until is not None and self.locked_until > utcnow()

    def record_failed_login(self) -> None:
        """Increment the failure counter and lock the account at the threshold."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= DEFAULT_MAX_FAILED_LOGINS:
            self.locked_until = utcnow() + timedelta(minutes=DEFAULT_LOCK_MINUTES)

    def reset_failed_logins(self) -> None:
        """Clear the failure counter and any active lockout."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_login(self) -> None:
        """Update last login timestamp and clear the failure state."""
        self.last_login_at = utcnow()
        self.reset_failed_logins()

    def __repr__(self) -> str:
        return f"<User {self.username}>"
