"""Shared model building blocks: enums, a UTC clock and column helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from extensions import db


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (DB-compatible)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enum_type(enum_class: type[Enum]) -> SqlEnum:
    """Return a portable SQLAlchemy Enum that stores enum *values* as text.

    Using ``native_enum=False`` keeps the schema compatible across SQLite
    and MySQL while ``values_callable`` persists the human-readable values
    (e.g. ``"critical"``) instead of Python member names (``"CRITICAL"``).
    """
    return db.Enum(
        enum_class,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns managed by the ORM."""

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
