"""Evidence model — images and clips captured for an incident."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin, enum_type, utcnow
from models.enums import EvidenceType

if TYPE_CHECKING:
    from models.incident import Incident


class Evidence(db.Model, TimestampMixin):
    """A stored screenshot or recorded video belonging to an incident."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        db.ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )

    evidence_type: Mapped[EvidenceType] = mapped_column(
        enum_type(EvidenceType), nullable=False
    )
    file_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(db.String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(db.String(100))
    file_size: Mapped[int | None] = mapped_column(db.Integer)
    duration: Mapped[float | None] = mapped_column(db.Float)
    captured_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=utcnow, nullable=False, index=True
    )

    incident: Mapped["Incident"] = relationship(back_populates="evidence")

    def __repr__(self) -> str:
        return f"<Evidence {self.id} {self.evidence_type.value}>"
