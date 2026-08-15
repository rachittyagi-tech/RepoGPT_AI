"""
app/api/github.py

HTTP layer for the GitHub Repository Management module (Step 3).

This router is intentionally "thin" — every endpoint does three things:
    1. Receive/validate the request (via Pydantic schemas)
    2. Delegate to `GitHubService` (business logic lives there, not here)
    3. Shape the service's return value into a response schema

All error translation (invalid URL, already exists, not found, private
repo, network failure, git failures) happens via the domain exceptions
raised by the service + the global exception handlers registered in
`app.core.exceptions` — no try/except blocks are needed in these routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.schemas.github import (
    GitHubCloneRequest,
    GitHubOperationResponse,
    GitHubUpdateRequest,
    RepositoryDeleteResponse,
    RepositoryListResponse,
    RepositoryStatusResponse,
)
from app.services.github_service import GitHubService, get_github_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.github")

# Step 15: clone/update run `git clone`/`git pull` — real I/O and disk
# usage per call, worth throttling. List/get/delete are cheap reads but
# share the bucket for simplicity; the limit is generous enough (10/min/IP)
# not to bother normal use.
router = APIRouter(tags=["GitHub"], dependencies=[Depends(rate_limit("github", 10, 60))])


@router.post(
    "/clone",
    response_model=GitHubOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a public GitHub repository",
)
async def clone_repository(
    payload: GitHubCloneRequest,
    service: GitHubService = Depends(get_github_service),
) -> GitHubOperationResponse:
    """
    Clones the given public GitHub repository into `data/repositories/`.

    Returns 201 on success, 409 if the repository already exists (call
    `/update` instead), 403 if the repository is private/inaccessible,
    404 if GitHub reports the repo doesn't exist, and 502 for network
    or unclassified git failures.
    """
    logger.info("Received clone request | url=%s", payload.repo_url)
    info, operation = await service.clone_repository(payload.repo_url)
    return GitHubOperationResponse(
        operation=operation,
        message=f"Repository '{info.repository_name}' cloned successfully.",
        data=info,
    )


@router.post(
    "/update",
    response_model=GitHubOperationResponse,
    status_code=status.HTTP_200_OK,
    summary="Pull latest changes for an already-cloned repository",
)
async def update_repository(
    payload: GitHubUpdateRequest,
    service: GitHubService = Depends(get_github_service),
) -> GitHubOperationResponse:
    """
    Runs `git pull` on an existing local repository.

    Returns 404 if the repository was never cloned (call `/clone` first),
    403 if access was revoked/private, 502 for network/git failures.
    """
    logger.info("Received update request | url=%s", payload.repo_url)
    info, operation = await service.update_repository(payload.repo_url)
    message = (
        "Repository is already up to date."
        if operation.value == "already_up_to_date"
        else f"Repository '{info.repository_name}' updated successfully."
    )
    return GitHubOperationResponse(operation=operation, message=message, data=info)


@router.get(
    "/list",
    response_model=RepositoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all locally-stored repositories",
)
async def list_repositories(
    service: GitHubService = Depends(get_github_service),
) -> RepositoryListResponse:
    """Returns metadata for every repository currently stored under data/repositories/."""
    repositories = await service.list_repositories()
    return RepositoryListResponse(count=len(repositories), repositories=repositories)


@router.get(
    "/status/{repository_name}",
    response_model=RepositoryStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get metadata/status for one repository",
)
async def get_repository_status(
    repository_name: str,
    service: GitHubService = Depends(get_github_service),
) -> RepositoryStatusResponse:
    """Returns branch, latest commit, size, and timestamps for one repository."""
    info = await service.get_repository_status(repository_name)
    return RepositoryStatusResponse(data=info)


@router.delete(
    "/{repository_name}",
    response_model=RepositoryDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a locally-stored repository",
)
async def delete_repository(
    repository_name: str,
    service: GitHubService = Depends(get_github_service),
) -> RepositoryDeleteResponse:
    """Permanently removes the repository's local folder."""
    logger.info("Received delete request | repo=%s", repository_name)
    await service.delete_repository(repository_name)
    return RepositoryDeleteResponse(
        message=f"Repository '{repository_name}' deleted successfully.",
        repository_name=repository_name,
    )
