"""
app/schemas/intelligence.py

Pydantic v2 request/response DTOs for the AI Code Intelligence Engine
(Step 13) — AI Code Review, Bug Detection, Security Analysis,
Performance Analysis, README/Documentation/Architecture generation, and
the Repository Quality Score.

Shared conventions across every response in this module:
    - `sources: List[SourceReference]` — every AI-generated response
      carries back the exact chunks it was grounded in (Step 8's
      `SourceReference`), so nothing is presented without a citable origin.
    - `detection_method` on findings — `"heuristic"` (deterministic
      regex/static-analysis, zero hallucination risk) vs `"ai"` (Gemini
      reasoning over RAG context) — the frontend/consumer can weight or
      filter findings by how they were produced.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.rag import SourceReference


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DetectionMethod(str, Enum):
    HEURISTIC = "heuristic"
    AI = "ai"


class ReviewCategory(str, Enum):
    BUG_RISK = "bug_risk"
    CODE_SMELL = "code_smell"
    CLEAN_CODE = "clean_code"
    BEST_PRACTICE = "best_practice"
    MAINTAINABILITY = "maintainability"


class BugCategory(str, Enum):
    POSSIBLE_BUG = "possible_bug"
    NULL_POINTER_RISK = "null_pointer_risk"
    UNUSED_VARIABLE = "unused_variable"
    DEAD_CODE = "dead_code"
    DUPLICATE_CODE = "duplicate_code"
    MEMORY_LEAK = "memory_leak"
    EXCEPTION_HANDLING = "exception_handling"


class SecurityCategory(str, Enum):
    HARDCODED_SECRET = "hardcoded_secret"
    API_KEY = "api_key"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    WEAK_AUTHENTICATION = "weak_authentication"
    UNSAFE_FILE_ACCESS = "unsafe_file_access"
    UNSAFE_DEPENDENCY = "unsafe_dependency"


class PerformanceCategory(str, Enum):
    LARGE_FILE = "large_file"
    EXPENSIVE_LOOP = "expensive_loop"
    REPEATED_COMPUTATION = "repeated_computation"
    INEFFICIENT_ALGORITHM = "inefficient_algorithm"
    SLOW_QUERY = "slow_query"
    UNOPTIMIZED_CODE = "unoptimized_code"


class DocumentationMode(str, Enum):
    API_DOCS = "api_docs"
    EXPLAIN_FUNCTION = "explain_function"
    EXPLAIN_CLASS = "explain_class"
    EXPLAIN_FILE = "explain_file"
    CODING_STANDARDS = "coding_standards"


class QualityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


# ---------------------------------------------------------------------------
# Shared request base
# ---------------------------------------------------------------------------
class IntelligenceRequestBase(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])
    focus_path: Optional[str] = Field(
        default=None, description="Limit analysis to one file (relative path), if provided."
    )
    language: Optional[str] = Field(default=None, description="Filter retrieval to one programming language.")
    max_findings: int = Field(default=15, ge=1, le=50)


# ---------------------------------------------------------------------------
# POST /api/intelligence/review
# ---------------------------------------------------------------------------
class CodeReviewRequest(IntelligenceRequestBase):
    pass


class ReviewFinding(BaseModel):
    category: ReviewCategory
    severity: Severity
    file_path: Optional[str] = None
    title: str
    description: str
    suggestion: str


class CodeReviewResponse(BaseModel):
    success: bool = True
    repository_name: str
    summary: str
    findings: List[ReviewFinding]
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# POST /api/intelligence/bugs
# ---------------------------------------------------------------------------
class BugDetectionRequest(IntelligenceRequestBase):
    pass


class BugFinding(BaseModel):
    category: BugCategory
    severity: Severity
    detection_method: DetectionMethod
    file_path: Optional[str] = None
    line_hint: Optional[int] = None
    title: str
    description: str
    suggestion: str


class BugDetectionResponse(BaseModel):
    success: bool = True
    repository_name: str
    summary: str
    findings: List[BugFinding]
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# POST /api/intelligence/security
# ---------------------------------------------------------------------------
class SecurityAnalysisRequest(IntelligenceRequestBase):
    pass


class SecurityFinding(BaseModel):
    category: SecurityCategory
    severity: Severity
    detection_method: DetectionMethod
    file_path: Optional[str] = None
    line_hint: Optional[int] = None
    title: str
    description: str
    remediation: str


class SecurityAnalysisResponse(BaseModel):
    success: bool = True
    repository_name: str
    summary: str
    risk_level: Severity
    findings: List[SecurityFinding]
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# POST /api/intelligence/performance
# ---------------------------------------------------------------------------
class PerformanceAnalysisRequest(IntelligenceRequestBase):
    pass


class PerformanceFinding(BaseModel):
    category: PerformanceCategory
    severity: Severity
    detection_method: DetectionMethod
    file_path: Optional[str] = None
    line_hint: Optional[int] = None
    title: str
    description: str
    suggestion: str


class PerformanceAnalysisResponse(BaseModel):
    success: bool = True
    repository_name: str
    summary: str
    findings: List[PerformanceFinding]
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# POST /api/intelligence/readme
# ---------------------------------------------------------------------------
class ReadmeGenerationRequest(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])
    include_badges: bool = True
    license_name: Optional[str] = Field(default=None, description="Override; auto-detected from disk if omitted.")


class ReadmeGenerationResponse(BaseModel):
    success: bool = True
    repository_name: str
    markdown: str
    sections_included: List[str]
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# POST /api/intelligence/documentation
# ---------------------------------------------------------------------------
class DocumentationRequest(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])
    mode: DocumentationMode
    target: Optional[str] = Field(
        default=None,
        description="Function/class name for explain_function/explain_class, or a file path for "
        "explain_file. Ignored for api_docs and coding_standards.",
    )


class DocumentationResponse(BaseModel):
    success: bool = True
    repository_name: str
    mode: DocumentationMode
    target: Optional[str] = None
    content_markdown: str
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# POST /api/intelligence/architecture
# ---------------------------------------------------------------------------
class ArchitectureRequest(BaseModel):
    repository_name: str = Field(..., examples=["psf__requests"])


class ArchitectureComponent(BaseModel):
    name: str
    responsibility: str
    key_files: List[str] = Field(default_factory=list)


class ArchitectureResponse(BaseModel):
    success: bool = True
    repository_name: str
    summary: str
    components: List[ArchitectureComponent]
    content_markdown: str
    sources: List[SourceReference]
    generated_at: datetime


# ---------------------------------------------------------------------------
# GET /api/intelligence/quality/{repository}
# ---------------------------------------------------------------------------
class QualityScoreBreakdown(BaseModel):
    structure_score: float = Field(..., ge=0, le=100)
    documentation_score: float = Field(..., ge=0, le=100)
    complexity_score: float = Field(..., ge=0, le=100)
    security_score: float = Field(..., ge=0, le=100)
    performance_score: float = Field(..., ge=0, le=100)
    maintainability_score: float = Field(..., ge=0, le=100)
    test_coverage_score: float = Field(..., ge=0, le=100)


class QualityScoreResponse(BaseModel):
    success: bool = True
    repository_name: str
    overall_score: float = Field(..., ge=0, le=100)
    grade: QualityGrade
    breakdown: QualityScoreBreakdown
    highlights: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    calculated_at: datetime


# ---------------------------------------------------------------------------
# Dependency analysis (surfaced within /security's findings and available
# for reuse by other Step 13 services — no dedicated endpoint per the
# Step 13 endpoint list, folded into /security + /performance + quality).
# ---------------------------------------------------------------------------
class DependencyInfo(BaseModel):
    name: str
    version: Optional[str] = None
    ecosystem: str = Field(..., description="e.g. 'pip', 'npm'.")
    manifest_file: str
    is_pinned: bool
    risk_notes: List[str] = Field(default_factory=list)


class DependencyAnalysis(BaseModel):
    repository_name: str
    manifests_found: List[str]
    dependencies: List[DependencyInfo]
    unpinned_count: int
    flagged_count: int
