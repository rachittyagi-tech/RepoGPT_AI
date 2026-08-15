"""
app/models/session.py

SQLAlchemy ORM models for `refresh_tokens` and `login_sessions`.

Why store refresh tokens in the DB at all (instead of just trusting the
JWT signature)?
    - Logout must actually invalidate a refresh token — a stateless JWT
      can't be "un-issued" once signed, so we track a `revoked` flag here
      and check it on every /refresh call.
    - Enables "log out of all devices" and session listing/management.

`login_sessions` is a lighter-weight audit trail of login events
(IP / user agent / timestamps) — useful for the RBAC/security review in
Step 8 of the quality checklist and for suspicious-login handling later.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks issued refresh tokens so they can be revoked (logout, rotation)."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # `jti` (JWT ID) claim from the token itself — lets us revoke a specific
    # token without storing the full (sensitive) token string in the DB.
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.revoked}>"


class LoginSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit record of a single login event, for session history / security review."""

    __tablename__ = "login_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    logged_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="login_sessions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LoginSession id={self.id} user_id={self.user_id} active={self.is_active}>"


# NOTE: "User" above is a string forward-ref — see the matching note at the
# bottom of `app/models/user.py`. Both modules are imported together in
# `app/models/__init__.py`.
