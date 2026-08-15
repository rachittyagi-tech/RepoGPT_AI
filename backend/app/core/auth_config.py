"""
app/core/auth_config.py

Auth & JWT specific configuration (Step 11).

Kept separate from `app/core/settings.py` for Single Responsibility —
`settings.py` holds general app config; this module holds everything
specific to the Authentication & User Management module (token expiry,
algorithm, cookie names, password policy). Both are still populated
from the same `.env` file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Strongly-typed settings for JWT auth, tokens, and password policy."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- JWT ----------------
    JWT_SECRET_KEY: str = "change-this-too"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------------- Password Reset ----------------
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # ---------------- Email Verification (structure ready — Step 12+) ----------------
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24

    # ---------------- Password Policy ----------------
    PASSWORD_MIN_LENGTH: int = 8

    # ---------------- Bcrypt ----------------
    BCRYPT_ROUNDS: int = 12


@lru_cache
def get_auth_settings() -> AuthSettings:
    """Cached singleton accessor, DI-overridable in tests via Depends()."""
    return AuthSettings()


auth_settings = get_auth_settings()
