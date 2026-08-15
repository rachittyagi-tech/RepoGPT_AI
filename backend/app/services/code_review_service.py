"""
app/services/code_review_service.py

AI Code Review (Step 13) — bug risks, code smells, clean-code violations,
best-practice/maintainability concerns.

Orchestration: RAGService (retrieval, Step 8) -> intelligence_prompts
(prompt + JSON schema) -> GeminiService (generation) -> parse JSON into
`ReviewFinding`s. Same "sequence collaborators, own no logic of theirs"
shape as `ChatService` (Step 9).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import Depends

from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_code_review_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import CodeReviewRequest, CodeReviewResponse, ReviewFinding
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service

logger = get_logger("services.code_review")

_DEFAULT_QUERY = "overall code quality, structure, patterns, and potential issues across the repository"
_RETRIEVAL_TOP_K = 12


class CodeReviewService:
    def __init__(self, rag_service: RAGService, gemini_service: GeminiService) -> None:
        self.rag_service = rag_service
        self.gemini_service = gemini_service

    async def review(self, request: CodeReviewRequest) -> CodeReviewResponse:
        query = (
            f"code quality and potential issues in {request.focus_path}"
            if request.focus_path
            else _DEFAULT_QUERY
        )

        _, chunks = await self.rag_service.retrieve(
            repository_name=request.repository_name,
            question=query,
            top_k=_RETRIEVAL_TOP_K,
            language=request.language,
            file_name=request.focus_path,
        )
        sources = chunks_to_sources(chunks)

        prompt = build_code_review_prompt(chunks, sources, request.max_findings)
        raw_text, _usage = await self.gemini_service.generate(prompt)

        summary, findings = self._parse_response(raw_text, request.max_findings)

        logger.info(
            "Code review complete | repo=%s | findings=%d", request.repository_name, len(findings)
        )

        return CodeReviewResponse(
            repository_name=request.repository_name,
            summary=summary,
            findings=findings,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _parse_response(raw_text: str, max_findings: int) -> tuple[str, List[ReviewFinding]]:
        payload = extract_json_payload(raw_text)

        if not isinstance(payload, dict):
            logger.warning("Code review: Gemini response was not parseable JSON — returning raw summary only.")
            return raw_text.strip() or "No summary generated.", []

        summary = str(payload.get("summary") or "").strip() or "No summary generated."
        raw_findings = payload.get("findings")
        findings: List[ReviewFinding] = []

        if isinstance(raw_findings, list):
            for item in raw_findings[:max_findings]:
                finding = CodeReviewService._parse_finding(item)
                if finding:
                    findings.append(finding)

        return summary, findings

    @staticmethod
    def _parse_finding(item: Any) -> Optional[ReviewFinding]:
        if not isinstance(item, dict):
            return None
        try:
            return ReviewFinding(
                category=item.get("category", "best_practice"),
                severity=item.get("severity", "info"),
                file_path=item.get("file_path"),
                title=str(item.get("title", "")).strip() or "Untitled finding",
                description=str(item.get("description", "")).strip(),
                suggestion=str(item.get("suggestion", "")).strip(),
            )
        except Exception as exc:  # noqa: BLE001 — one malformed finding shouldn't fail the whole response
            logger.warning("Code review: skipping malformed finding: %s", exc)
            return None


def get_code_review_service(
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> CodeReviewService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return CodeReviewService(rag_service=rag_service, gemini_service=gemini_service)
