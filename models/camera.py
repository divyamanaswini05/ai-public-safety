"""Camera model — every connected surveillance source."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin, enum_type
from models.enums import CameraSource, CameraStatus

if TYPE_CHECKING:
    from models.incident import Incident


class Camera(db.Model, TimestampMixin):
    """A webcam or network (IP/RTSP) camera that produces a video feed."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(db.String(255))
    source_type: Mapped[CameraSource] = mapped_column(
        enum_type(CameraSource), default=CameraSource.WEBCAM, nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(db.String(500))
    ip_address: Mapped[str | None] = mapped_column(db.String(64))
    port: Mapped[int | None] = mapped_column(db.Integer)
    username: Mapped[str | None] = mapped_column(db.String(128))
    # RTSP credentials must never be stored in plaintext. Module 5 encrypts
    # the value with Fernet before persisting here.
    password_encrypted: Mapped[str | None] = mapped_column(
        db.Text, comment="Fernet-encrypted RTSP credential"
    )
    latitude: Mapped[float | None] = mapped_column(db.Float)
    longitude: Mapped[float | None] = mapped_column(db.Float)

    status: Mapped[CameraStatus] = mapped_column(
        enum_type(CameraStatus), default=CameraStatus.OFFLINE, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    health_score: Mapped[float | None] = mapped_column(db.Float)
    last_seen_at: Mapped[datetime | None] = mapped_column(db.DateTime)

    incidents: Mapped[list["Incident"]] = relationship(back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera {self.name}>"
