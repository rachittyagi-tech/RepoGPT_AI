"""
app/services/performance_service.py

Performance Optimization Suggestions (Step 13) — two detection methods:

    1. HEURISTIC (deterministic): large files (by line count, from
       Scanner's cached stats/files, Step 4), nested loops (indentation-
       based block tracking — language-agnostic, since it doesn't rely
       on brace-parsing), and query-like calls found inside a loop body
       (a simple N+1-query smell signal).
    2. AI (Gemini over RAG context, Step 8): repeated computation,
       inefficient algorithms, slow queries beyond the simple in-loop
       pattern, and general unoptimized code — genuinely requires
       reasoning about what the code is trying to do.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from fastapi import Depends

from app.core.exceptions import ScanNotPerformedError
from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_performance_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import (
    DetectionMethod,
    PerformanceAnalysisRequest,
    PerformanceAnalysisResponse,
    PerformanceCategory,
    PerformanceFinding,
    Severity,
)
from app.schemas.scanner import ScannedFile
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service
from app.services.scanner_service import ScannerService, get_scanner_service

logger = get_logger("services.performance")

_RETRIEVAL_TOP_K = 12
_MAX_HEURISTIC_FINDINGS = 20
_LARGE_FILE_LINE_THRESHOLD = 500

_LOOP_RE = re.compile(r"^\s*(for|while)\b")
_QUERY_CALL_RE = re.compile(
    r"(?i)\.(execute|query|raw|filter|get|find|findOne|find_one|fetchall|fetchone|save|update|delete)\s*\("
)


class PerformanceService:
    def __init__(self, scanner_service: ScannerService, rag_service: RAGService, gemini_service: GeminiService) -> None:
        self.scanner_service = scanner_service
        self.rag_service = rag_service
        self.gemini_service = gemini_service

    async def analyze(self, request: PerformanceAnalysisRequest) -> PerformanceAnalysisResponse:
        heuristic_findings = self.run_heuristics(request.repository_name, request.focus_path)

        query = (
            f"algorithms, computations, and data access patterns in {request.focus_path}"
            if request.focus_path
            else "algorithms, repeated computations, caching opportunities, and database access patterns"
        )
        _, chunks = await self.rag_service.retrieve(
            repository_name=request.repository_name,
            question=query,
            top_k=_RETRIEVAL_TOP_K,
            language=request.language,
            file_name=request.focus_path,
        )
        sources = chunks_to_sources(chunks)

        remaining_budget = max(request.max_findings - len(heuristic_findings), 3)
        prompt = build_performance_prompt(chunks, sources, remaining_budget)
        raw_text, _usage = await self.gemini_service.generate(prompt)
        ai_findings = self._parse_ai_findings(raw_text, remaining_budget)

        all_findings = (heuristic_findings + ai_findings)[: request.max_findings]
        summary = self._build_summary(heuristic_findings, ai_findings)

        logger.info(
            "Performance analysis complete | repo=%s | heuristic=%d | ai=%d",
            request.repository_name,
            len(heuristic_findings),
            len(ai_findings),
        )

        return PerformanceAnalysisResponse(
            repository_name=request.repository_name,
            summary=summary,
            findings=all_findings,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Heuristic (deterministic) detection
    # ------------------------------------------------------------------
    def run_heuristics(self, repository_name: str, focus_path: Optional[str]) -> List[PerformanceFinding]:
        """Public — also reused directly by `QualityScoreService` (Step 13) for a fast,
        LLM-free performance signal in the Repository Quality Score."""
        try:
            files = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            return []

        if focus_path:
            files = [f for f in files if f.relative_path == focus_path]

        findings: List[PerformanceFinding] = []
        findings.extend(self._detect_large_files(files))
        for f in files:
            findings.extend(self._detect_loop_issues(f))
            if len(findings) >= _MAX_HEURISTIC_FINDINGS:
                break
        return findings[:_MAX_HEURISTIC_FINDINGS]

    @staticmethod
    def _detect_large_files(files: List[ScannedFile]) -> List[PerformanceFinding]:
        findings: List[PerformanceFinding] = []
        for f in sorted(files, key=lambda x: x.line_count, reverse=True):
            if f.line_count < _LARGE_FILE_LINE_THRESHOLD:
                break
            findings.append(
                PerformanceFinding(
                    category=PerformanceCategory.LARGE_FILE,
                    severity=Severity.LOW if f.line_count < 1000 else Severity.MEDIUM,
                    detection_method=DetectionMethod.HEURISTIC,
                    file_path=f.relative_path,
                    line_hint=None,
                    title=f"Large file ({f.line_count} lines)",
                    description="Very large files are harder to review, test, and optimize, and can "
                    "slow down IDE tooling and code review.",
                    suggestion="Consider splitting this file into smaller, more focused modules.",
                )
            )
        return findings

    @classmethod
    def _detect_loop_issues(cls, f: ScannedFile) -> List[PerformanceFinding]:
        """Language-agnostic indentation-stack loop tracker: flags nested loops, and
        loops whose body contains a query-like call (possible N+1 pattern)."""
        if not f.content:
            return []

        findings: List[PerformanceFinding] = []
        lines = f.content.splitlines()
        # Stack of (indent, line_no) for currently-open loop blocks.
        stack: List[Tuple[int, int]] = []

        for line_no, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" \t"))

            while stack and indent <= stack[-1][0]:
                stack.pop()

            if _LOOP_RE.match(line):
                if stack:
                    findings.append(
                        PerformanceFinding(
                            category=PerformanceCategory.EXPENSIVE_LOOP,
                            severity=Severity.MEDIUM,
                            detection_method=DetectionMethod.HEURISTIC,
                            file_path=f.relative_path,
                            line_hint=line_no,
                            title="Nested loop detected",
                            description=f"A loop starting at line {line_no} is nested inside another "
                            f"loop starting at line {stack[-1][1]}, which can lead to O(n^2) or worse "
                            "behavior on large inputs.",
                            suggestion="Check whether the inner loop's work can be hoisted out, cached, "
                            "or replaced with a more efficient data structure/algorithm.",
                        )
                    )
                stack.append((indent, line_no))
            elif stack and _QUERY_CALL_RE.search(line):
                findings.append(
                    PerformanceFinding(
                        category=PerformanceCategory.SLOW_QUERY,
                        severity=Severity.MEDIUM,
                        detection_method=DetectionMethod.HEURISTIC,
                        file_path=f.relative_path,
                        line_hint=line_no,
                        title="Possible query executed inside a loop (N+1 pattern)",
                        description=f"Line {line_no} calls what looks like a database/query method "
                        f"inside the loop starting at line {stack[-1][1]} — this often means one query "
                        "is issued per iteration instead of a single batched query.",
                        suggestion="Batch this into a single query outside the loop (e.g. a bulk "
                        "fetch/`IN (...)` query) where possible.",
                    )
                )

            if len(findings) >= _MAX_HEURISTIC_FINDINGS:
                break

        return findings

    # ------------------------------------------------------------------
    # AI (Gemini) detection
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_ai_findings(raw_text: str, max_findings: int) -> List[PerformanceFinding]:
        payload = extract_json_payload(raw_text)
        if not isinstance(payload, dict):
            return []

        findings: List[PerformanceFinding] = []
        raw_findings = payload.get("findings")
        if isinstance(raw_findings, list):
            for item in raw_findings[:max_findings]:
                finding = PerformanceService._parse_ai_finding(item)
                if finding:
                    findings.append(finding)
        return findings

    @staticmethod
    def _parse_ai_finding(item: Any) -> Optional[PerformanceFinding]:
        if not isinstance(item, dict):
            return None
        try:
            return PerformanceFinding(
                category=item.get("category", "unoptimized_code"),
                severity=item.get("severity", "info"),
                detection_method=DetectionMethod.AI,
                file_path=item.get("file_path"),
                line_hint=None,
                title=str(item.get("title", "")).strip() or "Untitled finding",
                description=str(item.get("description", "")).strip(),
                suggestion=str(item.get("suggestion", "")).strip(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Performance analysis: skipping malformed AI finding: %s", exc)
            return None

    @staticmethod
    def _build_summary(heuristic: List[PerformanceFinding], ai: List[PerformanceFinding]) -> str:
        total = len(heuristic) + len(ai)
        if total == 0:
            return "No performance issues were detected by static analysis or AI review."
        return (
            f"Found {total} potential performance issue(s): {len(heuristic)} from static analysis "
            f"(large files, nested loops, in-loop queries) and {len(ai)} from AI review of the "
            f"retrieved context (algorithmic efficiency, caching, query patterns)."
        )


def get_performance_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> PerformanceService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return PerformanceService(scanner_service=scanner_service, rag_service=rag_service, gemini_service=gemini_service)
