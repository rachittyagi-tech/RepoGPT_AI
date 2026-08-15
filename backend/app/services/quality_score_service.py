"""
app/services/quality_score_service.py

Repository Quality Score (Step 13) — GET /api/intelligence/quality/{repository}.

Deliberately makes ZERO Gemini calls: this is a GET endpoint meant to be
fast and cheap enough to poll/refresh often (e.g. on a dashboard card),
so every dimension is either reused from `RepositoryHealthService`
(Step 12's own heuristic health score) or computed from a fast,
deterministic heuristic scan (`SecurityService.scan_for_secrets`,
`PerformanceService.run_heuristics` — both already LLM-free by design).

Composes 7 dimensions:
    structure, documentation, complexity, test_coverage  <- Step 12's RepositoryHealthService
    security, performance                                <- Step 13's own heuristic scanners
    maintainability                                       <- derived (average of the other 6)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from fastapi import Depends

from app.core.logging import get_logger
from app.schemas.analytics import HealthScoreResponse
from app.schemas.intelligence import QualityGrade, QualityScoreBreakdown, QualityScoreResponse, Severity
from app.services.performance_service import PerformanceService, get_performance_service
from app.services.repository_health_service import RepositoryHealthService, get_repository_health_service
from app.services.security_service import SecurityService, get_security_service

logger = get_logger("services.quality_score")

_SEVERITY_PENALTY = {
    Severity.CRITICAL: 30,
    Severity.HIGH: 18,
    Severity.MEDIUM: 10,
    Severity.LOW: 4,
    Severity.INFO: 1,
}


class QualityScoreService:
    def __init__(
        self,
        health_service: RepositoryHealthService,
        security_service: SecurityService,
        performance_service: PerformanceService,
    ) -> None:
        self.health_service = health_service
        self.security_service = security_service
        self.performance_service = performance_service

    async def calculate(self, repository_name: str) -> QualityScoreResponse:
        health: HealthScoreResponse = await self.health_service.calculate_health_score(repository_name)

        security_findings = self.security_service.scan_for_secrets(repository_name, focus_path=None)
        performance_findings = self.performance_service.run_heuristics(repository_name, focus_path=None)

        security_score = self._score_from_penalties(f.severity for f in security_findings)
        performance_score = self._score_from_penalties(f.severity for f in performance_findings)

        breakdown = QualityScoreBreakdown(
            structure_score=health.breakdown.structure_score,
            documentation_score=health.breakdown.documentation_score,
            complexity_score=health.breakdown.complexity_score,
            security_score=security_score,
            performance_score=performance_score,
            maintainability_score=round(
                (
                    health.breakdown.structure_score
                    + health.breakdown.documentation_score
                    + health.breakdown.complexity_score
                    + security_score
                    + performance_score
                )
                / 5,
                1,
            ),
            test_coverage_score=health.breakdown.test_coverage_score,
        )

        overall = round(
            (breakdown.structure_score * 0.15)
            + (breakdown.documentation_score * 0.15)
            + (breakdown.complexity_score * 0.15)
            + (breakdown.security_score * 0.20)
            + (breakdown.performance_score * 0.15)
            + (breakdown.maintainability_score * 0.10)
            + (breakdown.test_coverage_score * 0.10),
            1,
        )

        highlights, concerns = self._build_notes(breakdown, len(security_findings), len(performance_findings))

        logger.info(
            "Quality score calculated | repo=%s | overall=%.1f | grade=%s",
            repository_name,
            overall,
            self._grade_for(overall).value,
        )

        return QualityScoreResponse(
            repository_name=repository_name,
            overall_score=overall,
            grade=self._grade_for(overall),
            breakdown=breakdown,
            highlights=highlights,
            concerns=concerns,
            calculated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _score_from_penalties(severities: Iterable[Severity]) -> float:
        score = 100.0
        for severity in severities:
            score -= _SEVERITY_PENALTY.get(severity, 5)
        return round(max(score, 0.0), 1)

    @staticmethod
    def _grade_for(score: float) -> QualityGrade:
        if score >= 90:
            return QualityGrade.A
        if score >= 75:
            return QualityGrade.B
        if score >= 60:
            return QualityGrade.C
        if score >= 40:
            return QualityGrade.D
        return QualityGrade.F

    @staticmethod
    def _build_notes(
        breakdown: QualityScoreBreakdown, security_count: int, performance_count: int
    ) -> tuple[List[str], List[str]]:
        highlights: List[str] = []
        concerns: List[str] = []

        dimensions = [
            ("Documentation", breakdown.documentation_score),
            ("Code structure", breakdown.structure_score),
            ("Complexity", breakdown.complexity_score),
            ("Test coverage", breakdown.test_coverage_score),
        ]
        for label, score in dimensions:
            if score >= 80:
                highlights.append(f"{label} is in good shape ({score:.0f}/100).")
            elif score < 50:
                concerns.append(f"{label} needs attention ({score:.0f}/100).")

        if security_count:
            concerns.append(f"{security_count} potential hardcoded secret(s)/unsafe dependenc(y/ies) detected.")
        else:
            highlights.append("No hardcoded secrets or flagged dependencies detected by static scanning.")

        if performance_count:
            concerns.append(f"{performance_count} potential performance issue(s) detected (large files/nested loops/in-loop queries).")
        else:
            highlights.append("No large files, nested loops, or in-loop queries detected by static scanning.")

        return highlights, concerns


def get_quality_score_service(
    health_service: RepositoryHealthService = Depends(get_repository_health_service),
    security_service: SecurityService = Depends(get_security_service),
    performance_service: PerformanceService = Depends(get_performance_service),
) -> QualityScoreService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return QualityScoreService(
        health_service=health_service, security_service=security_service, performance_service=performance_service
    )
