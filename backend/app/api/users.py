"""
app/api/users.py

HTTP layer for the User Management module (Step 11) — the current user's
own profile (`/api/users/me`). All three routes are protected by
`Depends(get_current_user)`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import DeactivateAccountRequest, DeleteAccountRequest, UserResponse, UserUpdateRequest
from app.services.auth_service import get_current_user
from app.services.user_service import UserService, get_user_service

logger = get_logger("api.users")

router = APIRouter(tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the current authenticated user's profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update the current user's profile (full name, avatar)",
)
async def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    updated = await service.update_profile(current_user, payload)
    return UserResponse.model_validate(updated)


@router.post(
    "/me/deactivate",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate (soft-disable) the current account",
)
async def deactivate_me(
    payload: DeactivateAccountRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """Requires password confirmation. Revokes all sessions; reversible only by an admin."""
    await service.deactivate_account(current_user, payload.password)
    return MessageResponse(message="Account deactivated.")


@router.delete(
    "/me",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Permanently delete the current account",
)
async def delete_me(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """Requires password confirmation. Irreversible — cascades to all refresh
    tokens and login sessions."""
    await service.delete_account(current_user, payload.password)
    return MessageResponse(message="Account permanently deleted.")
