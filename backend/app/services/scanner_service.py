"""
app/services/scanner_service.py

Business logic for the Repository Scanner & File Processing module
(Step 4).

Responsibilities:
    - Recursively walk a locally-cloned repository, pruning ignored
      directories (.git, node_modules, venv, etc.) without descending
      into them at all (performance-critical for large repos)
    - Delegate per-file decisions to `file_loader.load_file`
    - Aggregate repository-wide statistics (language breakdown, LOC, size)
    - Cache the last scan result per repository in memory so
      GET /files and GET /statistics don't need to re-scan the filesystem
      on every call

Design notes:
    - `os.walk` is used (via `Path` wrappers) instead of `Path.rglob`
      because `os.walk` lets us mutate `dirnames` in-place to prevent
      descending into ignored directories — `rglob` has no such hook and
      would waste time walking huge trees like node_modules before
      filtering.
    - The whole synchronous walk runs inside `asyncio.to_thread` so the
      event loop stays responsive even scanning a large repository.
    - The scan cache is a **class-level** dict (shared by every
      `ScannerService` instance) so that despite FastAPI creating a new
      instance per request (via `Depends`), all requests see the same
      cached scans — no extra app.state wiring needed for this step.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from app.core.constants import REPOSITORIES_BASE_DIR
from app.core.exceptions import RepositoryPathNotFoundError, ScanFailedError, ScanNotPerformedError
from app.core.logging import get_logger
from app.schemas.scanner import ScannedFile, ScanStatistics
from app.services.file_loader import load_file
from app.utils.file_utils import should_ignore_directory
from app.utils.github_validator import is_safe_repository_name

logger = get_logger("services.scanner")


@dataclass
class ScanResult:
    """Internal container for one repository's cached scan result."""

    files: List[ScannedFile] = field(default_factory=list)
    statistics: Optional[ScanStatistics] = None


class ScannerService:
    """Scans locally-cloned repositories and produces file + statistics data."""

    # Shared across all instances/requests — see module docstring.
    _SCAN_CACHE: ClassVar[Dict[str, ScanResult]] = {}

    def __init__(self, base_dir: Path = REPOSITORIES_BASE_DIR) -> None:
        self.base_dir = base_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def scan_repository(self, repository_name: str) -> ScanStatistics:
        """
        Performs a full recursive scan of `repository_name` and caches the
        result. Returns the resulting statistics.

        Raises:
            RepositoryPathNotFoundError: if the repo isn't cloned locally, or if
                `repository_name` fails path-safety validation (Step 15 fix — this
                method previously built `base_dir / repository_name` directly from
                caller input with no validation, e.g. via a raw `POST
                /api/scanner/scan` call that never went through GitHubService's
                clone step; a `repository_name` like `"../../../etc"` could read
                outside `REPOSITORIES_BASE_DIR`. Same guard `GitHubService` already
                used, applied here too since this is an independent entry point).
            ScanFailedError: on unexpected filesystem/I-O errors.
        """
        if not is_safe_repository_name(repository_name):
            raise RepositoryPathNotFoundError(repository_name)

        repo_root = self.base_dir / repository_name
        if not repo_root.exists() or not repo_root.is_dir():
            raise RepositoryPathNotFoundError(repository_name)

        logger.info("Starting scan | repo=%s | path=%s", repository_name, repo_root)

        try:
            files, total_files, ignored_files = await asyncio.to_thread(
                self._walk_repository, repo_root, repository_name
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scan failed | repo=%s", repository_name)
            raise ScanFailedError(repository_name, reason=str(exc)) from exc

        statistics = self._build_statistics(
            repository_name=repository_name,
            files=files,
            total_files=total_files,
            ignored_files=ignored_files,
        )

        self._SCAN_CACHE[repository_name] = ScanResult(files=files, statistics=statistics)

        logger.info(
            "Scan complete | repo=%s | supported=%d | ignored=%d | languages=%s",
            repository_name,
            statistics.supported_files,
            statistics.ignored_files,
            ", ".join(statistics.programming_languages),
        )
        return statistics

    def get_cached_files(
        self, repository_name: str, language: Optional[str] = None
    ) -> List[ScannedFile]:
        """
        Returns the cached scan's file list, optionally filtered by
        language (case-insensitive exact match).

        Raises:
            ScanNotPerformedError: if `scan_repository` hasn't been run yet.
        """
        result = self._get_cached_result(repository_name)
        if language is None:
            return result.files
        return [f for f in result.files if f.language.lower() == language.lower()]

    def get_cached_statistics(self, repository_name: str) -> ScanStatistics:
        """
        Returns the cached scan's statistics.

        Raises:
            ScanNotPerformedError: if `scan_repository` hasn't been run yet.
        """
        result = self._get_cached_result(repository_name)
        assert result.statistics is not None  # invariant: always set together with files
        return result.statistics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_cached_result(self, repository_name: str) -> ScanResult:
        result = self._SCAN_CACHE.get(repository_name)
        if result is None:
            raise ScanNotPerformedError(repository_name)
        return result

    @staticmethod
    def _walk_repository(
        repo_root: Path, repository_name: str
    ) -> tuple[List[ScannedFile], int, int]:
        """
        Synchronous recursive walk (runs inside asyncio.to_thread).

        Uses `os.walk` so ignored directories can be pruned via in-place
        mutation of `dirnames` — this avoids ever descending into
        node_modules/.git/venv/etc., which is critical for scan speed on
        real-world repositories.
        """
        files: List[ScannedFile] = []
        total_files = 0

        for dirpath, dirnames, filenames in os.walk(repo_root):
            # Prune ignored directories in-place so os.walk never enters them.
            dirnames[:] = [d for d in dirnames if not should_ignore_directory(d)]

            current_dir = Path(dirpath)
            for filename in filenames:
                total_files += 1
                file_path = current_dir / filename
                scanned = load_file(file_path, repo_root, repository_name)
                if scanned is not None:
                    files.append(scanned)

        ignored_files = total_files - len(files)
        return files, total_files, ignored_files

    @staticmethod
    def _build_statistics(
        repository_name: str,
        files: List[ScannedFile],
        total_files: int,
        ignored_files: int,
    ) -> ScanStatistics:
        language_counts: Dict[str, int] = {}
        total_lines = 0
        total_size_bytes = 0

        for f in files:
            language_counts[f.language] = language_counts.get(f.language, 0) + 1
            total_lines += f.line_count
            total_size_bytes += f.size_bytes

        return ScanStatistics(
            repository_name=repository_name,
            total_files=total_files,
            supported_files=len(files),
            ignored_files=ignored_files,
            programming_languages=sorted(language_counts.keys()),
            language_counts=language_counts,
            total_lines_of_code=total_lines,
            repository_size_bytes=total_size_bytes,
            repository_size_mb=round(total_size_bytes / (1024 * 1024), 3),
            scanned_at=datetime.now(timezone.utc),
        )


def get_scanner_service() -> ScannerService:
    """FastAPI dependency provider — see app/api/scanner.py."""
    return ScannerService()
