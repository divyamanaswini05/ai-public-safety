"""Incident model — automatically detected or manually reported events."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin, enum_type, utcnow
from models.enums import IncidentStatus, IncidentType, SeverityLevel

if TYPE_CHECKING:
    from models.alert import Alert
    from models.camera import Camera
    from models.evidence import Evidence
    from models.user import User


class Incident(db.Model, TimestampMixin):
    """A single detected or reported event that requires attention."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("cameras.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[int | None] = mapped_column(
        db.ForeignKey("users.id", ondelete="SET NULL")
    )

    incident_type: Mapped[IncidentType] = mapped_column(
        enum_type(IncidentType), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text)
    severity: Mapped[SeverityLevel] = mapped_column(
        enum_type(SeverityLevel), default=SeverityLevel.MEDIUM, nullable=False, index=True
    )
    status: Mapped[IncidentStatus] = mapped_column(
        enum_type(IncidentStatus), default=IncidentStatus.OPEN, nullable=False, index=True
    )
    confidence: Mapped[float | None] = mapped_column(db.Float)
    details: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict, nullable=False)

    detected_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=utcnow, nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(db.DateTime)

    camera: Mapped["Camera | None"] = relationship(back_populates="incidents")
    created_by_user: Mapped["User | None"] = relationship(back_populates="incidents")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Incident {self.id} {self.incident_type.value} {self.status.value}>"
