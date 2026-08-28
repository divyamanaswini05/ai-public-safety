"""Role model — access-control groups assigned to users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db
from models.base import TimestampMixin

if TYPE_CHECKING:
    from models.user import User


class Role(db.Model, TimestampMixin):
    """A named access level that can be assigned to many users."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(
        db.String(50), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(db.String(255))

    users: Mapped[list["User"]] = relationship(back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.slug}>"
