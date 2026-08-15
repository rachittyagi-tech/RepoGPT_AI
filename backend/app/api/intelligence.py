"""
app/api/intelligence.py

HTTP layer for the AI Code Intelligence Engine (Step 13). Thin router
only — every endpoint delegates entirely to its service. POST endpoints
call Gemini (grounded in RAG context, Step 8) and can take a few seconds;
GET /quality is LLM-free and fast by design (see `quality_score_service.py`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.schemas.intelligence import (
    ArchitectureRequest,
    ArchitectureResponse,
    BugDetectionRequest,
    BugDetectionResponse,
    CodeReviewRequest,
    CodeReviewResponse,
    DocumentationRequest,
    DocumentationResponse,
    PerformanceAnalysisRequest,
    PerformanceAnalysisResponse,
    QualityScoreResponse,
    ReadmeGenerationRequest,
    ReadmeGenerationResponse,
    SecurityAnalysisRequest,
    SecurityAnalysisResponse,
)
from app.services.architecture_service import ArchitectureService, get_architecture_service
from app.services.bug_detection_service import BugDetectionService, get_bug_detection_service
from app.services.code_review_service import CodeReviewService, get_code_review_service
from app.services.documentation_service import DocumentationService, get_documentation_service
from app.services.performance_service import PerformanceService, get_performance_service
from app.services.quality_score_service import QualityScoreService, get_quality_score_service
from app.services.readme_generator import ReadmeGeneratorService, get_readme_generator_service
from app.services.security_service import SecurityService, get_security_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.intelligence")

# Step 15: every POST endpoint here calls Gemini at least once (some —
# bugs/security/performance — call it plus run heuristics); GET /quality
# is LLM-free by design (see quality_score_service.py) but shares the
# bucket for simplicity, since it's cheap enough not to matter.
router = APIRouter(tags=["Intelligence"], dependencies=[Depends(rate_limit("intelligence", 10, 60))])


@router.post(
    "/review",
    response_model=CodeReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="AI code review — bug risks, code smells, clean-code, and best-practice findings",
)
async def code_review(
    request: CodeReviewRequest,
    service: CodeReviewService = Depends(get_code_review_service),
) -> CodeReviewResponse:
    return await service.review(request)


@router.post(
    "/bugs",
    response_model=BugDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Bug detection — static analysis + AI reasoning over RAG context",
)
async def bug_detection(
    request: BugDetectionRequest,
    service: BugDetectionService = Depends(get_bug_detection_service),
) -> BugDetectionResponse:
    return await service.detect(request)


@router.post(
    "/security",
    response_model=SecurityAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Security vulnerability detection — secrets/keys, SQLi/XSS/CSRF/auth, dependencies",
)
async def security_analysis(
    request: SecurityAnalysisRequest,
    service: SecurityService = Depends(get_security_service),
) -> SecurityAnalysisResponse:
    return await service.analyze(request)


@router.post(
    "/performance",
    response_model=PerformanceAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Performance analysis — large files, nested loops, N+1 queries, and AI-detected inefficiencies",
)
async def performance_analysis(
    request: PerformanceAnalysisRequest,
    service: PerformanceService = Depends(get_performance_service),
) -> PerformanceAnalysisResponse:
    return await service.analyze(request)


@router.post(
    "/readme",
    response_model=ReadmeGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a complete README.md for the repository",
)
async def generate_readme(
    request: ReadmeGenerationRequest,
    service: ReadmeGeneratorService = Depends(get_readme_generator_service),
) -> ReadmeGenerationResponse:
    return await service.generate(request)


@router.post(
    "/documentation",
    response_model=DocumentationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate API docs, explain a function/class/file, or a coding standards report",
)
async def generate_documentation(
    request: DocumentationRequest,
    service: DocumentationService = Depends(get_documentation_service),
) -> DocumentationResponse:
    """`mode=explain_function|explain_class|explain_file` requires `target` to be set
    (function/class name, or file path for explain_file) — returns 400 otherwise."""
    return await service.generate(request)


@router.post(
    "/architecture",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_200_OK,
    summary="Explain the repository's architecture and generate a repository summary",
)
async def architecture_explanation(
    request: ArchitectureRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    return await service.explain(request)


@router.get(
    "/quality/{repository}",
    response_model=QualityScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Repository quality score (structure/docs/complexity/security/performance/maintainability/tests)",
)
async def quality_score(
    repository: str,
    service: QualityScoreService = Depends(get_quality_score_service),
) -> QualityScoreResponse:
    """LLM-free and fast by design — safe to poll/refresh often (e.g. from a dashboard card)."""
    return await service.calculate(repository)
