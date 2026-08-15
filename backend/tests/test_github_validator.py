"""
tests/test_github_validator.py

Pure unit tests for app/utils/github_validator.py — no network, no git,
no filesystem. These run instantly and should always pass regardless
of environment.
"""

import pytest

from app.core.exceptions import InvalidGitHubURLError
from app.utils.github_validator import (
    build_folder_name,
    is_safe_repository_name,
    validate_github_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/psf/requests",
        "https://github.com/psf/requests.git",
        "https://github.com/psf/requests/",
        "http://github.com/psf/requests",
        "https://www.github.com/psf/requests",
    ],
)
def test_valid_github_urls_parse_correctly(url: str) -> None:
    parsed = validate_github_url(url)
    assert parsed.owner == "psf"
    assert parsed.repo == "requests"
    assert parsed.clone_url == "https://github.com/psf/requests.git"
    assert parsed.folder_name == "psf__requests"


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "not-a-url",
        "https://gitlab.com/psf/requests",
        "git@github.com:psf/requests.git",
        "https://github.com/psf",
        "ftp://github.com/psf/requests",
    ],
)
def test_invalid_github_urls_raise(bad_url: str) -> None:
    with pytest.raises(InvalidGitHubURLError):
        validate_github_url(bad_url)


def test_build_folder_name_is_deterministic_and_safe() -> None:
    name1 = build_folder_name("torvalds", "linux")
    name2 = build_folder_name("torvalds", "linux")
    assert name1 == name2 == "torvalds__linux"


def test_is_safe_repository_name_rejects_path_traversal() -> None:
    assert is_safe_repository_name("owner__repo") is True
    assert is_safe_repository_name("../../etc/passwd") is False
    assert is_safe_repository_name("owner/repo") is False
    assert is_safe_repository_name("owner\\repo") is False
    assert is_safe_repository_name("") is False
