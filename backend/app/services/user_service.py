"""
app/services/user_service.py

Business logic for the User Management module (Step 11) — operations a
user performs on their OWN account (`/api/users/me`). Admin-scoped user
management (list/ban other users, etc.) is intentionally out of scope for
Step 11 and will land in a later step behind `require_roles(UserRole.ADMIN)`.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IncorrectPasswordError
from app.core.logging import get_logger
from app.core.security import verify_password
from app.database.session import get_db
from app.models.user import User
from app.schemas.user import UserUpdateRequest
from app.services.auth_service import AuthService

logger = get_logger("services.user")


class UserService:
    """Encapsulates read/update/deactivate/delete operations on the current user's own account."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_profile(self, user: User, payload: UserUpdateRequest) -> User:
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.avatar is not None:
            user.avatar = payload.avatar

        await self.db.flush()
        await self.db.refresh(user)
        logger.info("Profile updated | user_id=%s", user.id)
        return user

    async def deactivate_account(self, user: User, password: str) -> None:
        """Soft-disable: sets is_active=False and revokes all sessions. Reversible by an admin."""
        if not verify_password(password, user.password_hash):
            raise IncorrectPasswordError()

        user.is_active = False
        await AuthService(self.db).logout_all_devices(user.id)
        await self.db.flush()
        logger.info("Account deactivated | user_id=%s", user.id)

    async def delete_account(self, user: User, password: str) -> None:
        """Hard delete. Cascades to refresh_tokens/login_sessions via FK ondelete=CASCADE."""
        if not verify_password(password, user.password_hash):
            raise IncorrectPasswordError()

        logger.info("Account permanently deleted | user_id=%s", user.id)
        await self.db.delete(user)
        await self.db.flush()


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """FastAPI dependency provider — see app/api/users.py."""
    return UserService(db)
