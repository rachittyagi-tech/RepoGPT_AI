"""
app/core/security.py

Low-level security primitives — password hashing and JWT encode/decode.

This is the ONLY module that imports `passlib` / `jose` directly
(Dependency Inversion: services depend on these functions, never on the
crypto libraries themselves). Keeping this isolated also makes it trivial
to swap the hashing scheme or JWT library later without touching any
business logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.auth_config import auth_settings
from app.core.logging import get_logger

logger = get_logger("core.security")

# ---------------------------------------------------------------------------
# Password hashing (bcrypt via passlib)
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=auth_settings.BCRYPT_ROUNDS)


def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password with bcrypt. Never store/log the plaintext."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time comparison of a plaintext password against its bcrypt hash."""
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except (ValueError, TypeError):
        # Malformed hash in DB — treat as verification failure, never raise to caller.
        logger.warning("Password verification received a malformed hash.")
        return False


# ---------------------------------------------------------------------------
# JWT token types
# ---------------------------------------------------------------------------
class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Builds and signs a JWT.

    Standard claims:
        sub  — subject (user id, as string)
        type — token type (access/refresh/password_reset/email_verification),
               so a refresh token can never be used where an access token
               is expected, and vice versa.
        jti  — unique token id, so refresh tokens can be individually
               revoked (stored in the `refresh_tokens` table).
        iat  — issued-at
        exp  — expiry
    """
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, auth_settings.JWT_SECRET_KEY, algorithm=auth_settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    claims = {"role": role}
    if extra_claims:
        claims.update(extra_claims)
    return _create_token(
        subject=user_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims=claims,
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=auth_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_password_reset_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=TokenType.PASSWORD_RESET,
        expires_delta=timedelta(minutes=auth_settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )


def create_email_verification_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=TokenType.EMAIL_VERIFICATION,
        expires_delta=timedelta(hours=auth_settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes + verifies a JWT's signature and expiry.

    Raises `jose.JWTError` (translated to domain exceptions by the caller —
    see `app.services.auth_service`) on an invalid signature, malformed
    token, or expired token.
    """
    return jwt.decode(token, auth_settings.JWT_SECRET_KEY, algorithms=[auth_settings.JWT_ALGORITHM])


__all__ = [
    "TokenType",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "create_password_reset_token",
    "create_email_verification_token",
    "decode_token",
    "JWTError",
]
