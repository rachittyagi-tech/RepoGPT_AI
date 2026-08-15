"""
app/schemas/user.py

Pydantic v2 request/response DTOs for the User Management module (Step 11).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserResponse(BaseModel):
    """Public-safe representation of a user — NEVER includes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    username: str
    email: EmailStr
    avatar: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserUpdateRequest(BaseModel):
    """All fields optional — PUT /api/users/me only updates what's provided."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    avatar: Optional[str] = Field(default=None, max_length=500)


class DeactivateAccountRequest(BaseModel):
    password: str = Field(..., description="Current password, required to confirm deactivation.")


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., description="Current password, required to confirm permanent deletion.")
