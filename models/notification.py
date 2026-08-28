"""Notification model — per-user messages in the notification tray."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin, utcnow

if TYPE_CHECKING:
    from models.alert import Alert
    from models.user import User


class Notification(db.Model, TimestampMixin):
    """A message delivered to a specific user's notification tray."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    alert_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(db.Text)

    is_read: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(db.DateTime)

    user: Mapped["User"] = relationship(back_populates="notifications")
    alert: Mapped["Alert | None"] = relationship(back_populates="notifications")

    def mark_read(self) -> None:
        """Flag the notification as read with a timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = utcnow()

    @classmethod
    def unread_count(cls, user_id: int) -> int:
        """Count unread notifications for a user."""
        return cls.query.filter_by(user_id=user_id, is_read=False).count()

    def __repr__(self) -> str:
        return f"<Notification {self.id}>"
