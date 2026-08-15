"""
app/schemas/auth.py

Pydantic v2 request/response DTOs for the Authentication module (Step 11).
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.auth_config import auth_settings

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")


def _validate_password_strength(v: str) -> str:
    if len(v) < auth_settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {auth_settings.PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit.")
    return v


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("Username may only contain letters, digits, and underscores (3-50 chars).")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    # Accepts either username or email in the same field, resolved by the service.
    identifier: str = Field(..., description="Username or email address.", examples=["jane@example.com"])
    password: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class EmailVerificationRequest(BaseModel):
    """Structure ready for Step 12 (actual email delivery) — validates the token today."""

    token: str


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime, in seconds.")


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
