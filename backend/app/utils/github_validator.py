"""
app/utils/github_validator.py

Pure, framework-free validation/parsing helpers for GitHub repository URLs.

Kept separate from the service layer (Single Responsibility): this module
only knows about *string parsing rules*, never about the filesystem, git
operations, or HTTP. That makes it trivially unit-testable and reusable
(e.g. the same validator could back a CLI tool later).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import (
    GITHUB_URL_PATTERN,
    MAX_REPO_FOLDER_NAME_LENGTH,
    UNSAFE_FOLDER_NAME_CHARS,
)
from app.core.exceptions import InvalidGitHubURLError


@dataclass(frozen=True)
class ParsedGitHubRepo:
    """Structured result of a validated GitHub repository URL."""

    owner: str
    repo: str
    clone_url: str          # normalized https://github.com/owner/repo.git
    folder_name: str        # filesystem-safe unique name, e.g. "owner__repo"


def validate_github_url(url: str) -> ParsedGitHubRepo:
    """
    Validates that `url` is a well-formed public GitHub HTTPS repository URL
    and returns a `ParsedGitHubRepo` with normalized fields.

    Raises:
        InvalidGitHubURLError: if the URL doesn't match the expected
        `https://github.com/<owner>/<repo>` pattern.
    """
    if not url or not isinstance(url, str):
        raise InvalidGitHubURLError(url=str(url), reason="URL must be a non-empty string.")

    match = GITHUB_URL_PATTERN.match(url.strip())
    if not match:
        raise InvalidGitHubURLError(
            url=url,
            reason=(
                "URL must look like 'https://github.com/<owner>/<repo>' "
                "(SSH URLs and private hosts are not supported)."
            ),
        )

    owner = match.group("owner")
    repo = match.group("repo")

    if repo.endswith(".git"):
        repo = repo[: -len(".git")]

    clone_url = f"https://github.com/{owner}/{repo}.git"
    folder_name = build_folder_name(owner, repo)

    return ParsedGitHubRepo(owner=owner, repo=repo, clone_url=clone_url, folder_name=folder_name)


def build_folder_name(owner: str, repo: str) -> str:
    """
    Derives a filesystem-safe, collision-resistant folder name from an
    owner/repo pair, e.g. ("torvalds", "linux") -> "torvalds__linux".

    Using "owner__repo" (rather than just "repo") avoids collisions between
    different owners' repos that share the same repo name.
    """
    raw = f"{owner}__{repo}"
    safe = UNSAFE_FOLDER_NAME_CHARS.sub("_", raw)
    return safe[:MAX_REPO_FOLDER_NAME_LENGTH]


def is_safe_repository_name(name: str) -> bool:
    """
    Guards against path traversal when a repository_name is taken directly
    from a URL path parameter (e.g. DELETE /api/github/{repository_name}).
    Only allows the same charset produced by `build_folder_name`.
    """
    if not name or ".." in name or "/" in name or "\\" in name:
        return False
    return bool(UNSAFE_FOLDER_NAME_CHARS.sub("", name) == name)
