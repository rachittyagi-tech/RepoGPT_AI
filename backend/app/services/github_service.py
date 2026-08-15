"""
app/services/github_service.py

Business logic for the GitHub Repository Management module (Step 3).

Responsibilities:
    - Clone a public GitHub repository to disk (or detect it already
      exists and delegate to update instead)
    - Pull latest changes for an existing local repository
    - List all locally-stored repositories with metadata
    - Return status/metadata for one repository
    - Delete a locally-stored repository

Design notes (Clean Architecture / SOLID):
    - This service has ZERO knowledge of FastAPI, HTTP, or Pydantic request
      objects — it takes/returns plain Python values and dataclasses/schemas,
      and raises domain exceptions from `app.core.exceptions`. The API layer
      (`app/api/github.py`) is the only place that talks HTTP.
    - GitPython's `git.Repo` operations are blocking/synchronous; every
      public method wraps its git call with `asyncio.to_thread` so the
      FastAPI event loop is never blocked by a slow clone/pull.
    - Low-level `GitCommandError` messages are classified into meaningful
      domain exceptions (auth failure -> private repo, DNS/connection
      failure -> network error, etc.) using marker strings from
      `app.core.constants` — callers/API layer never need to parse git
      stderr themselves.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from git import GitCommandError, Repo

from app.core.constants import (
    GIT_AUTH_FAILURE_MARKERS,
    GIT_CLONE_DEPTH,
    GIT_NETWORK_FAILURE_MARKERS,
    GIT_NOT_FOUND_MARKERS,
    REPOSITORIES_BASE_DIR,
)
from app.core.exceptions import (
    GitCloneError,
    GitNetworkError,
    GitPullError,
    PrivateRepositoryAccessError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
)
from app.core.logging import get_logger
from app.schemas.github import RepositoryInfo, RepositoryOperation
from app.utils.github_validator import ParsedGitHubRepo, is_safe_repository_name, validate_github_url

logger = get_logger("services.github")


class GitHubService:
    """Encapsulates all filesystem + git operations for managed repositories."""

    def __init__(self, base_dir: Path = REPOSITORIES_BASE_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("GitHubService initialized | base_dir=%s", self.base_dir.resolve())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def clone_repository(self, repo_url: str) -> Tuple[RepositoryInfo, RepositoryOperation]:
        """
        Clones a public GitHub repository.

        If the repository already exists locally, raises
        `RepositoryAlreadyExistsError` (client should call /update instead) —
        this keeps /clone and /update semantically distinct per the spec.
        """
        parsed = validate_github_url(repo_url)
        local_path = self.base_dir / parsed.folder_name

        if local_path.exists():
            logger.warning("Clone rejected — already exists | repo=%s", parsed.folder_name)
            raise RepositoryAlreadyExistsError(parsed.folder_name)

        logger.info("Cloning repository | url=%s -> %s", parsed.clone_url, local_path)

        try:
            await asyncio.to_thread(self._clone_sync, parsed, local_path)
        except GitCommandError as exc:
            self._cleanup_partial_clone(local_path)
            raise self._classify_git_error(exc, parsed.folder_name, operation="clone") from exc
        except Exception as exc:  # noqa: BLE001 - convert unexpected errors to domain error
            self._cleanup_partial_clone(local_path)
            logger.exception("Unexpected error while cloning %s", parsed.folder_name)
            raise GitCloneError(parsed.folder_name, reason=str(exc)) from exc

        logger.info("Clone successful | repo=%s", parsed.folder_name)
        info = self._build_repository_info(parsed.folder_name, parsed)
        return info, RepositoryOperation.CLONED

    async def update_repository(self, repo_url: str) -> Tuple[RepositoryInfo, RepositoryOperation]:
        """
        Pulls the latest changes for an already-cloned repository.

        If the repository does not exist locally yet, raises
        `RepositoryNotFoundError` (client should call /clone first).
        """
        parsed = validate_github_url(repo_url)
        local_path = self.base_dir / parsed.folder_name

        if not local_path.exists():
            logger.warning("Update rejected — not found | repo=%s", parsed.folder_name)
            raise RepositoryNotFoundError(parsed.folder_name)

        logger.info("Pulling latest changes | repo=%s", parsed.folder_name)

        try:
            commits_before, commits_after = await asyncio.to_thread(
                self._pull_sync, local_path
            )
        except GitCommandError as exc:
            raise self._classify_git_error(exc, parsed.folder_name, operation="pull") from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error while updating %s", parsed.folder_name)
            raise GitPullError(parsed.folder_name, reason=str(exc)) from exc

        operation = (
            RepositoryOperation.ALREADY_UP_TO_DATE
            if commits_before == commits_after
            else RepositoryOperation.UPDATED
        )
        logger.info(
            "Update complete | repo=%s | operation=%s", parsed.folder_name, operation.value
        )
        info = self._build_repository_info(parsed.folder_name, parsed)
        return info, operation

    async def list_repositories(self) -> List[RepositoryInfo]:
        """Returns metadata for every repository currently stored locally."""
        if not self.base_dir.exists():
            return []

        repositories: List[RepositoryInfo] = []
        for entry in sorted(self.base_dir.iterdir()):
            if entry.is_dir() and (entry / ".git").exists():
                try:
                    repositories.append(await asyncio.to_thread(self._read_repo_info, entry))
                except Exception:  # noqa: BLE001
                    logger.warning("Skipping unreadable repository folder: %s", entry.name)
        logger.info("Listed repositories | count=%d", len(repositories))
        return repositories

    async def get_repository_status(self, repository_name: str) -> RepositoryInfo:
        """Returns metadata for a single repository by its folder name."""
        self._validate_repository_name(repository_name)
        local_path = self.base_dir / repository_name

        if not local_path.exists() or not (local_path / ".git").exists():
            raise RepositoryNotFoundError(repository_name)

        return await asyncio.to_thread(self._read_repo_info, local_path)

    async def delete_repository(self, repository_name: str) -> None:
        """Permanently deletes a locally-stored repository folder."""
        self._validate_repository_name(repository_name)
        local_path = self.base_dir / repository_name

        if not local_path.exists():
            raise RepositoryNotFoundError(repository_name)

        logger.info("Deleting repository | repo=%s", repository_name)
        await asyncio.to_thread(shutil.rmtree, local_path, True)
        logger.info("Repository deleted | repo=%s", repository_name)

    # ------------------------------------------------------------------
    # Internal helpers (run inside asyncio.to_thread — synchronous code)
    # ------------------------------------------------------------------
    @staticmethod
    def _clone_sync(parsed: ParsedGitHubRepo, local_path: Path) -> None:
        Repo.clone_from(
            parsed.clone_url,
            local_path,
            depth=GIT_CLONE_DEPTH,
            env={"GIT_TERMINAL_PROMPT": "0"},  # never hang waiting for credentials
        )

    @staticmethod
    def _pull_sync(local_path: Path) -> Tuple[str, str]:
        repo = Repo(local_path)
        before = repo.head.commit.hexsha
        origin = repo.remotes.origin
        origin.fetch(env={"GIT_TERMINAL_PROMPT": "0"})
        origin.pull(env={"GIT_TERMINAL_PROMPT": "0"})
        after = repo.head.commit.hexsha
        return before, after

    def _read_repo_info(self, local_path: Path) -> RepositoryInfo:
        repo = Repo(local_path)
        folder_name = local_path.name
        owner, _, name = folder_name.partition("__")

        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = None  # detached HEAD (can happen with shallow clones)

        commit = repo.head.commit
        stat = local_path.stat()

        return RepositoryInfo(
            repository_name=folder_name,
            owner=owner or "unknown",
            repo=name or folder_name,
            clone_url=next(iter(repo.remotes.origin.urls), ""),
            local_path=str(local_path.resolve()),
            current_branch=branch,
            latest_commit_hash=commit.hexsha,
            latest_commit_message=commit.message.strip().splitlines()[0] if commit.message else None,
            size_mb=round(self._directory_size_bytes(local_path) / (1024 * 1024), 3),
            cloned_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
            last_updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )

    def _build_repository_info(self, folder_name: str, parsed: ParsedGitHubRepo) -> RepositoryInfo:
        local_path = self.base_dir / folder_name
        return self._read_repo_info(local_path)

    @staticmethod
    def _directory_size_bytes(path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    @staticmethod
    def _cleanup_partial_clone(local_path: Path) -> None:
        """Removes a half-cloned directory left behind after a failed clone attempt."""
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)

    @staticmethod
    def _validate_repository_name(repository_name: str) -> None:
        if not is_safe_repository_name(repository_name):
            raise RepositoryNotFoundError(repository_name)

    @staticmethod
    def _classify_git_error(
        exc: GitCommandError, repository_name: str, operation: str
    ) -> Exception:
        """
        Inspects a GitCommandError's message and maps it to the most specific
        domain exception available, so the API layer always returns a
        meaningful, correctly-coded response instead of a generic 502.
        """
        raw_message = str(exc).lower()

        if any(marker in raw_message for marker in GIT_AUTH_FAILURE_MARKERS):
            logger.warning("Git auth failure classified as private repo | repo=%s", repository_name)
            return PrivateRepositoryAccessError(repository_name)

        if any(marker in raw_message for marker in GIT_NOT_FOUND_MARKERS):
            logger.warning("Git reported repository not found | repo=%s", repository_name)
            return RepositoryNotFoundError(repository_name)

        if any(marker in raw_message for marker in GIT_NETWORK_FAILURE_MARKERS):
            logger.warning("Git network failure | repo=%s", repository_name)
            return GitNetworkError(
                f"Network error while accessing GitHub for repository '{repository_name}'."
            )

        logger.error("Unclassified git error | repo=%s | error=%s", repository_name, raw_message)
        if operation == "pull":
            return GitPullError(repository_name, reason=str(exc))
        return GitCloneError(repository_name, reason=str(exc))


def get_github_service() -> GitHubService:
    """FastAPI dependency provider — see app/api/github.py."""
    return GitHubService()
