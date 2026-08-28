"""Setting model — key/value application configuration stored in the database."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from extensions import db
from models.base import utcnow


class Setting(db.Model):
    """A single configurable application setting (e.g. alert thresholds)."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(
        db.String(150), unique=True, nullable=False, index=True
    )
    value: Mapped[str | None] = mapped_column(db.Text)
    group: Mapped[str] = mapped_column(db.String(50), default="general", nullable=False)
    description: Mapped[str | None] = mapped_column(db.String(255))
    is_public: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Read a setting value or return the supplied default."""
        record = cls.query.filter_by(key=key).first()
        return record.value if record is not None else default

    @classmethod
    def set(
        cls,
        key: str,
        value: str,
        group: str = "general",
        description: str | None = None,
    ) -> "Setting":
        """Insert or update a setting (idempotent)."""
        record = cls.query.filter_by(key=key).first()
        if record is None:
            record = cls(key=key, group=group, description=description)
            db.session.add(record)
        record.value = value
        if group:
            record.group = group
        return record

    def __repr__(self) -> str:
        return f"<Setting {self.key}>"
