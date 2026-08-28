"""AuditLog model — an immutable trail of security-relevant actions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin, enum_type, utcnow
from models.enums import LogLevel

if TYPE_CHECKING:
    from models.user import User


class AuditLog(db.Model, TimestampMixin):
    """A single entry in the audit trail (who did what, when and from where)."""

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    action: Mapped[str] = mapped_column(
        db.String(100), nullable=False, index=True
    )
    module: Mapped[str | None] = mapped_column(db.String(50), index=True)
    level: Mapped[LogLevel] = mapped_column(
        enum_type(LogLevel), default=LogLevel.INFO, nullable=False
    )
    message: Mapped[str | None] = mapped_column(db.Text)
    ip_address: Mapped[str | None] = mapped_column(db.String(45))
    user_agent: Mapped[str | None] = mapped_column(db.String(255))
    details: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=utcnow, nullable=False, index=True
    )

    user: Mapped["User | None"] = relationship(back_populates="logs")

    @classmethod
    def record(
        cls,
        action: str,
        module: str | None = None,
        level: LogLevel = LogLevel.INFO,
        message: str = "",
        details: dict[str, Any] | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> "AuditLog":
        """Persist an audit entry."""
        entry = cls(
            action=action,
            module=module,
            level=level,
            message=message,
            details=details or {},
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    def __repr__(self) -> str:
        return f"<AuditLog {self.action}>"
