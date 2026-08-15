"""
app/services/dependency_service.py

Dependency Analysis (Step 13) — parses dependency manifest files directly
from the repository's local clone (same `REPOSITORIES_BASE_DIR /
repository_name` path `GitHubService` itself reads from, Step 3) and
flags unpinned versions + a small set of known-risky packages.

IMPORTANT — this is NOT a live vulnerability feed. This environment has
no network access to a CVE/advisory database, so "unsafe dependency"
detection here is limited to:
    (a) missing version pins (a real, general best-practice signal), and
    (b) a small, explicitly-hardcoded list of packages with well-known,
        long-publicized historical CVEs, purely as an illustrative
        starting point.
This is surfaced as `risk_notes` (plural, advisory) rather than a
pass/fail verdict, and every response using it should say so.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from fastapi import Depends

from app.core.constants import REPOSITORIES_BASE_DIR
from app.core.exceptions import RepositoryNotFoundError
from app.core.logging import get_logger
from app.schemas.intelligence import DependencyAnalysis, DependencyInfo
from app.utils.github_validator import is_safe_repository_name

logger = get_logger("services.dependency")

# Small, explicitly-illustrative list — NOT a live advisory feed. Package
# names are lowercased for matching.
_KNOWN_RISK_NOTES = {
    "pyyaml": "Versions before 5.4 allow arbitrary code execution via yaml.load() on untrusted input.",
    "flask": "Ensure DEBUG mode is disabled in production — the Werkzeug debugger allows code execution.",
    "django": "Confirm the pinned version is not affected by a known Django security advisory before deploying.",
    "requests": "Versions before 2.31 have a proxy-related credential leak in specific redirect scenarios.",
    "lodash": "Versions before 4.17.21 have prototype-pollution vulnerabilities in several utility functions.",
    "minimist": "Versions before 1.2.6 have a prototype-pollution vulnerability.",
    "express": "Ensure body-parser and other middleware are on patched versions; check for known CVEs.",
    "log4j": "The Log4Shell family of vulnerabilities affects versions before 2.17.1 — verify the pinned version.",
}

_PIP_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)\s*(==|>=|<=|~=|!=|>|<)?\s*([A-Za-z0-9_.\-]*)\s*(?:;.*)?$"
)


class DependencyService:
    """Parses dependency manifests found in a repository's local clone."""

    def __init__(self, base_dir: Path = REPOSITORIES_BASE_DIR) -> None:
        self.base_dir = base_dir

    def analyze(self, repository_name: str) -> DependencyAnalysis:
        # Step 15 fix: `repository_name` reaches this method directly from an
        # API request body (POST /api/intelligence/security) and was
        # previously used to build a filesystem path with no validation —
        # a path-traversal read risk (e.g. "../../../etc"). Same guard
        # `GitHubService` already applies to its own inputs.
        if not is_safe_repository_name(repository_name):
            raise RepositoryNotFoundError(repository_name)

        local_path = self.base_dir / repository_name
        if not local_path.exists():
            raise RepositoryNotFoundError(repository_name)

        manifests_found: List[str] = []
        dependencies: List[DependencyInfo] = []

        requirements_txt = local_path / "requirements.txt"
        if requirements_txt.exists():
            manifests_found.append("requirements.txt")
            dependencies.extend(self._parse_requirements_txt(requirements_txt))

        package_json = local_path / "package.json"
        if package_json.exists():
            manifests_found.append("package.json")
            dependencies.extend(self._parse_package_json(package_json))

        unpinned_count = sum(1 for d in dependencies if not d.is_pinned)
        flagged_count = sum(1 for d in dependencies if d.risk_notes)

        logger.info(
            "Dependency analysis complete | repo=%s | manifests=%s | deps=%d | unpinned=%d | flagged=%d",
            repository_name,
            manifests_found,
            len(dependencies),
            unpinned_count,
            flagged_count,
        )

        return DependencyAnalysis(
            repository_name=repository_name,
            manifests_found=manifests_found,
            dependencies=dependencies,
            unpinned_count=unpinned_count,
            flagged_count=flagged_count,
        )

    # ------------------------------------------------------------------
    # Manifest parsers
    # ------------------------------------------------------------------
    def _parse_requirements_txt(self, path: Path) -> List[DependencyInfo]:
        deps: List[DependencyInfo] = []
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return deps

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = _PIP_LINE_RE.match(line)
            if not match:
                continue
            name, operator, version = match.groups()
            is_pinned = operator == "==" and bool(version)
            deps.append(
                DependencyInfo(
                    name=name,
                    version=version or None,
                    ecosystem="pip",
                    manifest_file="requirements.txt",
                    is_pinned=is_pinned,
                    risk_notes=self._risk_notes_for(name),
                )
            )
        return deps

    def _parse_package_json(self, path: Path) -> List[DependencyInfo]:
        deps: List[DependencyInfo] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not parse %s: %s", path, exc)
            return deps

        for section in ("dependencies", "devDependencies"):
            for name, version_range in (data.get(section) or {}).items():
                version_range = str(version_range)
                is_pinned = bool(re.match(r"^\d", version_range)) and not any(
                    c in version_range for c in ("^", "~", "*", "x", ">", "<")
                )
                deps.append(
                    DependencyInfo(
                        name=name,
                        version=version_range,
                        ecosystem="npm",
                        manifest_file="package.json",
                        is_pinned=is_pinned,
                        risk_notes=self._risk_notes_for(name),
                    )
                )
        return deps

    @staticmethod
    def _risk_notes_for(name: str) -> List[str]:
        note = _KNOWN_RISK_NOTES.get(name.lower())
        return [note] if note else []


def get_dependency_service() -> DependencyService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return DependencyService()
