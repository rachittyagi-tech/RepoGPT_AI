"""
app/services/repository_health_service.py

Computes a heuristic 0-100 "Repository Health Score" (Step 12) from data
the Scanner module (Step 4) already cached — no re-scanning, no new
filesystem reads beyond what `ScannerService.get_cached_files()` already
holds in memory.

IMPORTANT — this is a heuristic, not a static-analysis tool:
    - "Comments" density is estimated with a small set of common
      single-line comment markers per language family (not a real
      per-language parser/tokenizer — multi-line comments, strings that
      contain marker characters, etc. are not accounted for).
    - "Complexity" is approximated from average file length (lines of
      code per file) as a proxy — genuinely measuring cyclomatic
      complexity would require a real AST parser per language, out of
      scope for Step 12.
    - "Test coverage" is a presence/ratio signal (does a tests/ directory
      exist, what fraction of files look test-related), NOT a real
      coverage percentage from a coverage tool.
Each score element is documented as such in `HealthScoreResponse` so the
frontend can present it as "estimated" rather than authoritative.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from fastapi import Depends

from app.core.exceptions import ScanNotPerformedError
from app.core.logging import get_logger
from app.schemas.analytics import HealthGrade, HealthScoreBreakdown, HealthScoreResponse
from app.schemas.scanner import ScannedFile
from app.services.scanner_service import ScannerService, get_scanner_service

logger = get_logger("services.repository_health")

# Single-line comment markers per broad language family. Deliberately
# small/approximate — see module docstring.
_COMMENT_MARKERS_BY_LANGUAGE: Dict[str, str] = {
    "Python": "#",
    "Ruby": "#",
    "Shell": "#",
    "YAML": "#",
    "Dockerfile": "#",
    "JavaScript": "//",
    "TypeScript": "//",
    "Java": "//",
    "C": "//",
    "C++": "//",
    "C#": "//",
    "Go": "//",
    "Rust": "//",
    "Kotlin": "//",
    "Swift": "//",
    "PHP": "//",
    "SQL": "--",
    "Lua": "--",
}

_README_NAMES = {"readme.md", "readme.rst", "readme.txt", "readme"}
_DOC_DIR_MARKERS = {"docs", "documentation"}
_TEST_MARKERS = {"test", "tests", "__tests__", "spec", "specs"}
_STANDARD_SOURCE_DIRS = {"src", "app", "lib", "pkg", "cmd", "internal"}


class RepositoryHealthService:
    """Derives a heuristic health score from already-scanned repository file data."""

    def __init__(self, scanner_service: ScannerService) -> None:
        self.scanner_service = scanner_service

    async def calculate_health_score(self, repository_name: str) -> HealthScoreResponse:
        try:
            files: List[ScannedFile] = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            files = []

        documentation_score = self._score_documentation(files)
        structure_score = self._score_structure(files)
        comments_score = self._score_comments(files)
        complexity_score = self._score_complexity(files)
        test_coverage_score = self._score_test_coverage(files)

        overall = round(
            (documentation_score * 0.20)
            + (structure_score * 0.20)
            + (comments_score * 0.20)
            + (complexity_score * 0.20)
            + (test_coverage_score * 0.20),
            1,
        )

        breakdown = HealthScoreBreakdown(
            documentation_score=documentation_score,
            structure_score=structure_score,
            comments_score=comments_score,
            complexity_score=complexity_score,
            test_coverage_score=test_coverage_score,
        )

        return HealthScoreResponse(
            repository_name=repository_name,
            overall_score=overall,
            grade=self._grade_for(overall),
            breakdown=breakdown,
            recommendations=self._build_recommendations(breakdown),
            calculated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Individual score components (each 0-100)
    # ------------------------------------------------------------------
    @staticmethod
    def _score_documentation(files: List[ScannedFile]) -> float:
        if not files:
            return 0.0

        has_readme = any(f.relative_path.split("/")[-1].lower() in _README_NAMES for f in files)
        has_docs_dir = any(
            part.lower() in _DOC_DIR_MARKERS for f in files for part in f.relative_path.split("/")[:-1]
        )
        markdown_files = sum(1 for f in files if f.extension.lower() in (".md", ".rst"))
        markdown_ratio = min(markdown_files / max(len(files), 1) * 20, 1.0)  # small bonus, capped

        score = 0.0
        score += 55.0 if has_readme else 0.0
        score += 25.0 if has_docs_dir else 0.0
        score += 20.0 * markdown_ratio
        return round(min(score, 100.0), 1)

    @staticmethod
    def _score_structure(files: List[ScannedFile]) -> float:
        if not files:
            return 0.0

        top_level_dirs = {
            f.relative_path.split("/")[0] for f in files if "/" in f.relative_path
        }
        has_standard_layout = bool(top_level_dirs & _STANDARD_SOURCE_DIRS)

        # Penalize a "flat" repo (everything dumped at the root) and reward
        # a moderate depth (2-4 levels) — very deep nesting is penalized too.
        depths = [f.relative_path.count("/") for f in files]
        avg_depth = sum(depths) / len(depths) if depths else 0

        depth_score = 100.0 if 1 <= avg_depth <= 4 else max(0.0, 100.0 - abs(avg_depth - 2.5) * 15)
        layout_bonus = 15.0 if has_standard_layout else 0.0

        return round(min(depth_score * 0.85 + layout_bonus, 100.0), 1)

    @staticmethod
    def _score_comments(files: List[ScannedFile]) -> float:
        commentable = [f for f in files if f.language in _COMMENT_MARKERS_BY_LANGUAGE]
        if not commentable:
            return 50.0  # neutral score — nothing we know how to measure comments in

        ratios: List[float] = []
        for f in commentable:
            marker = _COMMENT_MARKERS_BY_LANGUAGE[f.language]
            lines = f.content.splitlines() if f.content else []
            if not lines:
                continue
            comment_lines = sum(1 for line in lines if line.strip().startswith(marker))
            ratios.append(comment_lines / len(lines))

        if not ratios:
            return 50.0

        avg_ratio = sum(ratios) / len(ratios)
        # A healthy comment ratio is roughly 8-20% of lines; below or well
        # above that band scores lower (too little context, or noisy/dead code).
        if 0.08 <= avg_ratio <= 0.20:
            return 100.0
        if avg_ratio < 0.08:
            return round(max(0.0, (avg_ratio / 0.08) * 100.0), 1)
        return round(max(30.0, 100.0 - (avg_ratio - 0.20) * 200), 1)

    @staticmethod
    def _score_complexity(files: List[ScannedFile]) -> float:
        """Proxy metric: average lines-of-code per file. Smaller, focused files
        score higher than very large files (a rough proxy for complexity, not a
        real cyclomatic-complexity measurement)."""
        if not files:
            return 0.0

        avg_lines = sum(f.line_count for f in files) / len(files)
        if avg_lines <= 150:
            return 100.0
        if avg_lines >= 600:
            return 20.0
        # Linear falloff between 150 and 600 lines/file.
        return round(100.0 - ((avg_lines - 150) / (600 - 150)) * 80.0, 1)

    @staticmethod
    def _score_test_coverage(files: List[ScannedFile]) -> float:
        if not files:
            return 0.0

        def _looks_like_test(f: ScannedFile) -> bool:
            parts = [p.lower() for p in f.relative_path.split("/")]
            name = parts[-1]
            return (
                any(p in _TEST_MARKERS for p in parts[:-1])
                or name.startswith("test_")
                or name.endswith("_test.py")
                or ".test." in name
                or ".spec." in name
            )

        test_files = sum(1 for f in files if _looks_like_test(f))
        if test_files == 0:
            return 0.0

        ratio = test_files / len(files)
        # ~15%+ of files being test files is treated as solid coverage signal.
        return round(min(100.0, (ratio / 0.15) * 100.0), 1)

    @staticmethod
    def _grade_for(score: float) -> HealthGrade:
        if score >= 90:
            return HealthGrade.A
        if score >= 75:
            return HealthGrade.B
        if score >= 60:
            return HealthGrade.C
        if score >= 40:
            return HealthGrade.D
        return HealthGrade.F

    @staticmethod
    def _build_recommendations(breakdown: HealthScoreBreakdown) -> List[str]:
        recs: List[str] = []
        if breakdown.documentation_score < 60:
            recs.append("Add or expand a README with setup, usage, and architecture notes.")
        if breakdown.structure_score < 60:
            recs.append("Organize code into standard directories (e.g. src/, tests/) for clearer structure.")
        if breakdown.comments_score < 60:
            recs.append("Increase inline documentation/comments, especially for complex logic.")
        if breakdown.complexity_score < 60:
            recs.append("Consider breaking up large files into smaller, more focused modules.")
        if breakdown.test_coverage_score < 60:
            recs.append("Add automated tests — no substantial test files were detected.")
        if not recs:
            recs.append("This repository is in good shape across all measured dimensions.")
        return recs


def get_repository_health_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
) -> RepositoryHealthService:
    """FastAPI dependency provider — see app/api/analytics.py."""
    return RepositoryHealthService(scanner_service=scanner_service)
