"""Alert model — prioritized alerts raised from incidents."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin, enum_type, utcnow
from models.enums import AlertPriority, AlertStatus, AlertType

if TYPE_CHECKING:
    from models.incident import Incident
    from models.notification import Notification
    from models.user import User


class Alert(db.Model, TimestampMixin):
    """A prioritized alert raised from an incident that fans out via channels."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    acknowledged_by: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id", ondelete="SET NULL")
    )

    alert_type: Mapped[AlertType] = mapped_column(
        enum_type(AlertType), nullable=False, index=True
    )
    priority: Mapped[AlertPriority] = mapped_column(
        enum_type(AlertPriority), default=AlertPriority.MEDIUM, nullable=False, index=True
    )
    status: Mapped[AlertStatus] = mapped_column(
        enum_type(AlertStatus), default=AlertStatus.PENDING, nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(db.Text)
    channels: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)

    sent_at: Mapped[datetime | None] = mapped_column(db.DateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(db.DateTime)

    incident: Mapped["Incident | None"] = relationship(back_populates="alerts")
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )
    acknowledged_by_user: Mapped["User | None"] = relationship(
        back_populates="acknowledged_alerts"
    )

    def mark_sent(self) -> None:
        """Record dispatch completion."""
        self.status = AlertStatus.SENT
        self.sent_at = utcnow()

    def acknowledge(self) -> None:
        """Mark the alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = utcnow()

    def __repr__(self) -> str:
        return f"<Alert {self.id} {self.priority.value}>"
