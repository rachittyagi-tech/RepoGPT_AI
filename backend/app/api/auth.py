"""
app/api/auth.py

HTTP layer for the Authentication module (Step 11).

Thin routers only — validation via Pydantic schemas, delegate to
`AuthService`, shape the response. All error translation happens via the
domain exceptions in `app.core.exceptions` + the global handlers
registered in `main.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.core.logging import get_logger
from app.core.settings import settings
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.middleware.rate_limit import rate_limit
from app.services.auth_service import AuthService, get_auth_service, get_current_user

logger = get_logger("api.auth")

# Step 15: brute-force / abuse protection. One shared bucket across every
# auth route is deliberately generous (10/min/IP) — token refresh happens
# routinely for an active session and shouldn't trip this, while still
# meaningfully slowing down a credential-stuffing attempt against /login
# or /register.
router = APIRouter(tags=["Auth"], dependencies=[Depends(rate_limit("auth", 10, 60))])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Creates a new account. Returns 409 if the email or username is already taken."""
    user = await service.register(payload)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in with username/email + password",
)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Returns an access + refresh token pair. Returns 401 for invalid credentials,
    403 if the account has been deactivated."""
    return await service.login(payload.identifier, payload.password, request)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out (revoke a refresh token)",
)
async def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Revokes the given refresh token. Always returns 200, even if the token was
    already invalid/expired/unknown — logout is idempotent by design."""
    await service.logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange a refresh token for a new access + refresh token pair",
)
async def refresh(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Rotates the refresh token (old one is revoked). Returns 401 if the token is
    invalid, expired, or has already been revoked/used."""
    return await service.refresh_access_token(payload.refresh_token)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a password reset token",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """
    Always returns a generic 200 message — whether or not the email is
    registered — to prevent user enumeration. No email-delivery integration
    exists yet, so there is currently no channel to hand the reset token to
    the user at all in production; it is logged ONLY outside production, for
    local development/testing of the reset flow.

    Step 15 security fix: this previously logged the raw reset token at
    INFO level unconditionally. That token is a bearer credential — anyone
    who reads it can reset that account's password without knowing the old
    one — so logging it in production (where `LOG_JSON=true` ships these
    logs to an aggregator, per Step 14) was a real account-takeover vector.
    """
    reset_token = await service.request_password_reset(payload.email)
    if reset_token and not settings.is_production:
        logger.info("Password reset token issued (dev-mode log only): %s", reset_token)
    return MessageResponse(
        message="If an account with that email exists, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password using a reset token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Returns 401 if the token is invalid/expired/wrong-type. On success, all
    existing sessions are revoked (user must log in again everywhere)."""
    await service.reset_password(payload.token, payload.new_password)
    return MessageResponse(message="Password has been reset successfully. Please log in again.")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password (requires current password)",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Protected route. Returns 401 if `current_password` doesn't match."""
    await service.change_password(current_user, payload.current_password, payload.new_password)
    return MessageResponse(message="Password changed successfully.")
