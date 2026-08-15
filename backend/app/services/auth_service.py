"""
app/services/auth_service.py

Business logic for the Authentication module (Step 11).

Design notes (Clean Architecture / SOLID):
    - Zero FastAPI/HTTP knowledge except for the two `Depends`-based
      dependency helpers at the bottom (`get_current_user`,
      `require_roles`), which are the sanctioned boundary where auth
      meets the HTTP layer (every other method takes/returns plain
      values + raises domain exceptions from `app.core.exceptions`).
    - `AuthService` never talks to the DB directly with raw SQL — it goes
      through SQLAlchemy's async ORM session, injected via `Depends(get_db)`.
    - Refresh tokens are persisted (hashed identity via `jti`, not the full
      token) so logout / revocation actually works — see `app/models/session.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_config import auth_settings
from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateUsernameError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
    UserNotFoundError,
)
from app.core.logging import get_logger
from app.core.security import (
    TokenType,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database.session import get_db
from app.models.session import RefreshToken
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, TokenResponse

logger = get_logger("services.auth")

# `tokenUrl` only affects the Swagger "Authorize" button's login form target;
# actual auth still goes through /api/auth/login (JSON body, not form-encoded).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


class AuthService:
    """Encapsulates registration, login, logout, refresh, and password-reset flows."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register(self, payload: RegisterRequest) -> User:
        existing_email = await self.db.execute(select(User).where(User.email == payload.email))
        if existing_email.scalar_one_or_none() is not None:
            raise DuplicateEmailError(payload.email)

        existing_username = await self.db.execute(select(User).where(User.username == payload.username))
        if existing_username.scalar_one_or_none() is not None:
            raise DuplicateUsernameError(payload.username)

        user = User(
            full_name=payload.full_name,
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=UserRole.USER,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info("New user registered | user_id=%s | username=%s", user.id, user.username)
        return user

    # ------------------------------------------------------------------
    # Login / Logout / Refresh
    # ------------------------------------------------------------------
    async def authenticate(self, identifier: str, password: str) -> User:
        """Verifies credentials (username OR email + password). Raises InvalidCredentialsError
        for ANY mismatch — deliberately not distinguishing "no such user" from "wrong password"
        to avoid user-enumeration."""
        result = await self.db.execute(
            select(User).where(or_(User.email == identifier, User.username == identifier))
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        return user

    async def issue_tokens(
        self,
        user: User,
        request: Optional[Request] = None,
    ) -> TokenResponse:
        """Issues a fresh access + refresh token pair, persisting the refresh token's `jti`."""
        access_token = create_access_token(user_id=str(user.id), role=user.role.value)
        refresh_token = create_refresh_token(user_id=str(user.id))
        claims = decode_token(refresh_token)

        record = RefreshToken(
            user_id=user.id,
            jti=claims["jti"],
            expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
            user_agent=request.headers.get("user-agent") if request else None,
            ip_address=request.client.host if request and request.client else None,
        )
        self.db.add(record)

        user.last_login = datetime.now(timezone.utc)

        await self.db.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def login(self, identifier: str, password: str, request: Optional[Request] = None) -> TokenResponse:
        user = await self.authenticate(identifier, password)
        logger.info("User logged in | user_id=%s", user.id)
        return await self.issue_tokens(user, request)

    async def logout(self, refresh_token: str) -> None:
        """Revokes a single refresh token (this device only). Invalid/expired/unknown
        tokens are treated as an already-effective logout — no error is raised, so
        clients can always safely call /logout."""
        try:
            claims = decode_token(refresh_token)
        except JWTError:
            return

        if claims.get("type") != TokenType.REFRESH.value:
            return

        result = await self.db.execute(select(RefreshToken).where(RefreshToken.jti == claims.get("jti")))
        record = result.scalar_one_or_none()
        if record and not record.revoked:
            record.revoked = True
            record.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()
            logger.info("Refresh token revoked | user_id=%s | jti=%s", record.user_id, record.jti)

    async def logout_all_devices(self, user_id: uuid.UUID) -> int:
        """Revokes every active refresh token for a user. Returns the count revoked."""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        )
        records = result.scalars().all()
        now = datetime.now(timezone.utc)
        for record in records:
            record.revoked = True
            record.revoked_at = now
        await self.db.flush()
        return len(records)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Validates a refresh token (signature, expiry, type, not-revoked) and issues a
        new access + refresh token pair (rotation — the old refresh token is revoked so
        it can't be replayed)."""
        claims = self._decode_or_raise(refresh_token, expected_type=TokenType.REFRESH)

        result = await self.db.execute(select(RefreshToken).where(RefreshToken.jti == claims["jti"]))
        record = result.scalar_one_or_none()
        if record is None:
            raise InvalidTokenError("This refresh token is not recognized.")
        if record.revoked:
            raise TokenRevokedError()

        user = await self.db.get(User, record.user_id)
        if user is None:
            raise UserNotFoundError(str(record.user_id))
        if not user.is_active:
            raise InactiveUserError()

        # Rotate: revoke the presented token, issue a brand-new pair.
        record.revoked = True
        record.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

        return await self.issue_tokens(user)

    # ------------------------------------------------------------------
    # Password reset / change
    # ------------------------------------------------------------------
    async def request_password_reset(self, email: str) -> Optional[str]:
        """Returns a signed reset token if the email exists, else None.

        The API layer MUST return the same generic response either way
        (see app/api/auth.py) to avoid leaking which emails are registered.
        In Step 12 this token gets emailed instead of returned to the caller.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return create_password_reset_token(str(user.id))

    async def reset_password(self, token: str, new_password: str) -> None:
        claims = self._decode_or_raise(token, expected_type=TokenType.PASSWORD_RESET)
        user = await self.db.get(User, uuid.UUID(claims["sub"]))
        if user is None:
            raise UserNotFoundError(claims["sub"])

        user.password_hash = hash_password(new_password)
        await self.logout_all_devices(user.id)  # force re-login everywhere after a reset
        await self.db.flush()
        logger.info("Password reset completed | user_id=%s", user.id)

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        from app.core.exceptions import IncorrectPasswordError

        if not verify_password(current_password, user.password_hash):
            raise IncorrectPasswordError()

        user.password_hash = hash_password(new_password)
        await self.db.flush()
        logger.info("Password changed | user_id=%s", user.id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _decode_or_raise(token: str, expected_type: TokenType) -> dict:
        try:
            claims = decode_token(token)
        except ExpiredSignatureError:
            raise TokenExpiredError(expected_type.value)
        except JWTError:
            raise InvalidTokenError()

        if claims.get("type") != expected_type.value:
            raise InvalidTokenError(f"Expected a {expected_type.value} token.")

        return claims


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """FastAPI dependency provider — see app/api/auth.py."""
    return AuthService(db)


# ---------------------------------------------------------------------------
# "Get current user" — the core protected-route dependency
# ---------------------------------------------------------------------------
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validates the `Authorization: Bearer <access_token>`
    header and returns the corresponding `User`. Use as:

        @router.get("/me")
        async def me(user: User = Depends(get_current_user)): ...

    Raises UnauthorizedError (401) if the header is missing, the token is
    malformed/expired/wrong-type, or the user no longer exists;
    InactiveUserError (403) if the account was deactivated.
    """
    if token is None:
        raise InvalidTokenError("Missing bearer token.")

    try:
        claims = decode_token(token)
    except ExpiredSignatureError:
        raise TokenExpiredError("access token")
    except JWTError:
        raise InvalidTokenError()

    if claims.get("type") != TokenType.ACCESS.value:
        raise InvalidTokenError("Expected an access token.")

    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise UserNotFoundError(claims["sub"])
    if not user.is_active:
        raise InactiveUserError()

    return user


def require_roles(*allowed_roles: UserRole):
    """
    RBAC dependency factory. Usage:

        @router.delete("/users/{id}", dependencies=[Depends(require_roles(UserRole.ADMIN))])

    Raises InsufficientRoleError (403) if the current user's role isn't in `allowed_roles`.
    """

    async def _check(user: User = Depends(get_current_user)) -> User:
        from app.core.exceptions import InsufficientRoleError

        if user.role not in allowed_roles:
            raise InsufficientRoleError([r.value for r in allowed_roles])
        return user

    return _check
