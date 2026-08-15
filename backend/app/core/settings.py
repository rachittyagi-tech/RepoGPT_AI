"""
app/core/settings.py

Centralized application configuration using Pydantic v2 `BaseSettings`.

Design rationale (Clean Architecture / SOLID):
- Single Responsibility: this module's only job is to define & validate
  configuration. Nothing else reads os.environ directly anywhere else
  in the codebase — everyone imports `settings` from here.
- Dependency Inversion: services depend on the `Settings` abstraction
  (injected via `get_settings()`), not on raw environment variables.
- `lru_cache` ensures the .env file is parsed only once per process
  (settings are effectively a singleton, but still testable/overridable).
"""

from functools import lru_cache
from typing import List, Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Strongly-typed application settings, auto-loaded from environment
    variables / a `.env` file. Every field is validated at startup —
    if a required variable is missing or malformed, the app fails fast
    instead of crashing later at request time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- App Metadata ----------------
    APP_NAME: str = "RepoGPT AI"
    APP_VERSION: str = "0.2.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ---------------- Server ----------------
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ---------------- Security ----------------
    SECRET_KEY: str = Field(default="dev-secret-change-me")

    # ---------------- CORS ----------------
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ---------------- Logging ----------------
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_JSON: bool = False  # True in production for log-aggregator friendly output

    # ---------------- Database (placeholders — wired in a later step) ----------------
    DATABASE_URL: str = "postgresql+asyncpg://repogpt:change-me@localhost:5432/repogpt_db"

    # ---------------- Redis (placeholder — wired in a later step) ----------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---------------- Storage (Step 14) ----------------
    REPOSITORY_STORAGE_PATH: str = "data/repositories"
    """Directory cloned repositories are written to (Step 3's `REPOSITORIES_BASE_DIR`
    now reads this instead of a hardcoded path, so it's configurable/mountable as a
    Docker volume without touching code)."""

    # ---------------- Public URLs (Step 14 — CORS / links in emails, docs, etc.) ----------------
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_origins(cls, v: str) -> str:
        """Ensure the raw CSV string isn't empty; parsing happens in the property below."""
        if not v.strip():
            raise ValueError("ALLOWED_ORIGINS must not be empty")
        return v

    @property
    def cors_origins(self) -> List[str]:
        """Parsed list form of ALLOWED_ORIGINS, consumed by CORS middleware."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    Using a function (instead of a bare module-level `settings = Settings()`)
    allows FastAPI's dependency-injection system (`Depends(get_settings)`)
    to override settings cleanly in tests via `app.dependency_overrides`.
    """
    return Settings()


# Module-level convenience instance for non-DI contexts (e.g. logging setup
# at import time, before the app object exists).
settings = get_settings()
