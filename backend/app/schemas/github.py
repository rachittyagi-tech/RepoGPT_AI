"""
app/schemas/github.py

Pydantic v2 request/response DTOs for the GitHub Repository Management
module. Kept separate from `app/models/` (which will hold SQLAlchemy ORM
models once persistence is added) — Step 3 is filesystem-backed only,
no database yet.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class RepositoryOperation(str, Enum):
    CLONED = "cloned"
    UPDATED = "updated"
    ALREADY_UP_TO_DATE = "already_up_to_date"
    DELETED = "deleted"


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class GitHubCloneRequest(BaseModel):
    """Body for POST /api/github/clone"""

    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL, e.g. https://github.com/owner/repo",
        examples=["https://github.com/psf/requests"],
    )

    @field_validator("repo_url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()


class GitHubUpdateRequest(BaseModel):
    """Body for POST /api/github/update"""

    repo_url: str = Field(
        ...,
        description="Same GitHub repository URL used to clone it originally.",
        examples=["https://github.com/psf/requests"],
    )

    @field_validator("repo_url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()


# ---------------------------------------------------------------------------
# Data objects
# ---------------------------------------------------------------------------
class RepositoryInfo(BaseModel):
    """Metadata describing one locally-stored repository."""

    repository_name: str = Field(..., description="Filesystem-safe folder name (owner__repo)")
    owner: str
    repo: str
    clone_url: str
    local_path: str
    current_branch: Optional[str] = None
    latest_commit_hash: Optional[str] = None
    latest_commit_message: Optional[str] = None
    size_mb: Optional[float] = None
    cloned_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Responses — consistent envelope: { success, message, data }
# ---------------------------------------------------------------------------
class GitHubOperationResponse(BaseModel):
    success: bool = True
    operation: RepositoryOperation
    message: str
    data: RepositoryInfo


class RepositoryListResponse(BaseModel):
    success: bool = True
    count: int
    repositories: List[RepositoryInfo]


class RepositoryStatusResponse(BaseModel):
    success: bool = True
    data: RepositoryInfo


class RepositoryDeleteResponse(BaseModel):
    success: bool = True
    message: str
    repository_name: str
