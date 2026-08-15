"""
app/services/documentation_service.py

API Documentation Generator + Explain Function/Class/File + Coding
Standards Report (Step 13) — one service, five modes
(`DocumentationMode`), since they share the same shape: RAG-retrieve
relevant context (scoped to a target when one's given) -> ask Gemini for
Markdown content -> return it with citations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends

from app.core.exceptions import InvalidQueryError
from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_documentation_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import DocumentationMode, DocumentationRequest, DocumentationResponse
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service

logger = get_logger("services.documentation")

_RETRIEVAL_TOP_K = 12

_MODE_QUERIES = {
    DocumentationMode.API_DOCS: "HTTP API routes, endpoints, request handlers, and their request/response shapes",
    DocumentationMode.CODING_STANDARDS: "naming conventions, code formatting, docstring style, and error handling patterns",
}


class DocumentationService:
    def __init__(self, rag_service: RAGService, gemini_service: GeminiService) -> None:
        self.rag_service = rag_service
        self.gemini_service = gemini_service

    async def generate(self, request: DocumentationRequest) -> DocumentationResponse:
        needs_target = request.mode in (
            DocumentationMode.EXPLAIN_FUNCTION,
            DocumentationMode.EXPLAIN_CLASS,
            DocumentationMode.EXPLAIN_FILE,
        )
        if needs_target and not request.target:
            raise InvalidQueryError(f"mode '{request.mode.value}' requires a non-empty 'target'.")

        question = self._build_query(request.mode, request.target)
        file_name = request.target if request.mode == DocumentationMode.EXPLAIN_FILE else None

        _, chunks = await self.rag_service.retrieve(
            repository_name=request.repository_name,
            question=question,
            top_k=_RETRIEVAL_TOP_K,
            file_name=file_name,
        )
        sources = chunks_to_sources(chunks)

        prompt = build_documentation_prompt(request.mode.value, request.target, chunks, sources)
        raw_text, _usage = await self.gemini_service.generate(prompt)
        content_markdown = self._parse_response(raw_text)

        logger.info(
            "Documentation generated | repo=%s | mode=%s | target=%s",
            request.repository_name,
            request.mode.value,
            request.target,
        )

        return DocumentationResponse(
            repository_name=request.repository_name,
            mode=request.mode,
            target=request.target,
            content_markdown=content_markdown,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _build_query(mode: DocumentationMode, target: Optional[str]) -> str:
        if mode in _MODE_QUERIES:
            return _MODE_QUERIES[mode]
        if mode == DocumentationMode.EXPLAIN_FUNCTION:
            return f"the function named {target} and where it is used"
        if mode == DocumentationMode.EXPLAIN_CLASS:
            return f"the class named {target} and where it is used"
        if mode == DocumentationMode.EXPLAIN_FILE:
            return f"the overall purpose and contents of {target}"
        return "repository overview"  # unreachable given the enum, kept as a safe default

    @staticmethod
    def _parse_response(raw_text: str) -> str:
        payload = extract_json_payload(raw_text)
        if isinstance(payload, dict):
            content = str(payload.get("content_markdown") or "").strip()
            if content:
                return content
        return raw_text.strip() or "No documentation could be generated from the retrieved context."


def get_documentation_service(
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> DocumentationService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return DocumentationService(rag_service=rag_service, gemini_service=gemini_service)
