"""
app/models/user.py

SQLAlchemy ORM model for the `users` table.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    """Application roles, used for Role-Based Access Control (RBAC)."""

    ADMIN = "admin"
    DEVELOPER = "developer"
    USER = "user"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered RepoGPT AI user/account."""

    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False, length=20),
        default=UserRole.USER,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    login_sessions: Mapped[List["LoginSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover — debugging aid only
        return f"<User id={self.id} username={self.username!r} role={self.role.value}>"


# NOTE: `RefreshToken` / `LoginSession` above are referenced only as string
# forward-refs ("RefreshToken", "LoginSession") to avoid a circular import
# with `app.models.session` (which itself references "User" back). Both
# model modules are imported together in `app/models/__init__.py`, which
# registers every class on `Base`'s mapper registry before any relationship
# is actually resolved (SQLAlchemy resolves string refs lazily, at first
# use — not at class-definition time).
