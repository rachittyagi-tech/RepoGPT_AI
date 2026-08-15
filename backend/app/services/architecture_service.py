"""
app/services/architecture_service.py

Architecture Explanation + Repository Summary (Step 13). Grounds Gemini
with three things: broad RAG-retrieved context (Step 8), the actual
folder structure (from Scanner's cached files, Step 4), and the language
breakdown — so the architecture explanation reflects the real repository
layout, not just whatever a handful of retrieved chunks happen to show.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends

from app.core.exceptions import ScanNotPerformedError
from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_architecture_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import ArchitectureComponent, ArchitectureRequest, ArchitectureResponse
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service
from app.services.scanner_service import ScannerService, get_scanner_service

logger = get_logger("services.architecture")

_RETRIEVAL_TOP_K = 15
_ARCHITECTURE_QUERY = (
    "project structure, main entry point, core modules, layers, and how components interact"
)


class ArchitectureService:
    def __init__(self, scanner_service: ScannerService, rag_service: RAGService, gemini_service: GeminiService) -> None:
        self.scanner_service = scanner_service
        self.rag_service = rag_service
        self.gemini_service = gemini_service

    async def explain(self, request: ArchitectureRequest) -> ArchitectureResponse:
        folder_structure = self._build_folder_structure(request.repository_name)
        language_summary = self._build_language_summary(request.repository_name)

        _, chunks = await self.rag_service.retrieve(
            repository_name=request.repository_name,
            question=_ARCHITECTURE_QUERY,
            top_k=_RETRIEVAL_TOP_K,
        )
        sources = chunks_to_sources(chunks)

        prompt = build_architecture_prompt(chunks, sources, folder_structure, language_summary)
        raw_text, _usage = await self.gemini_service.generate(prompt)
        summary, components, content_markdown = self._parse_response(raw_text)

        logger.info(
            "Architecture explanation complete | repo=%s | components=%d",
            request.repository_name,
            len(components),
        )

        return ArchitectureResponse(
            repository_name=request.repository_name,
            summary=summary,
            components=components,
            content_markdown=content_markdown,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Grounding data (deterministic — from Scanner's cache, Step 4)
    # ------------------------------------------------------------------
    def _build_folder_structure(self, repository_name: str) -> str:
        try:
            files = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            return "(repository not scanned yet)"

        top_level: Dict[str, int] = defaultdict(int)
        for f in files:
            parts = f.relative_path.split("/")
            top_level[parts[0] if len(parts) > 1 else "(root)"] += 1

        lines = [f"- {name}/ ({count} files)" for name, count in sorted(top_level.items(), key=lambda kv: -kv[1])]
        return "\n".join(lines[:25]) or "(no files)"

    def _build_language_summary(self, repository_name: str) -> str:
        try:
            stats = self.scanner_service.get_cached_statistics(repository_name)
        except ScanNotPerformedError:
            return "(repository not scanned yet)"

        lines = [
            f"- {lang}: {count} files"
            for lang, count in sorted(stats.language_counts.items(), key=lambda kv: -kv[1])
        ]
        return "\n".join(lines[:15]) or "(no files)"

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw_text: str) -> tuple[str, List[ArchitectureComponent], str]:
        payload = extract_json_payload(raw_text)
        if not isinstance(payload, dict):
            logger.warning("Architecture: Gemini response was not parseable JSON — returning raw text.")
            return "Architecture summary could not be structured.", [], raw_text.strip()

        summary = str(payload.get("summary") or "").strip() or "No summary generated."
        content_markdown = str(payload.get("content_markdown") or "").strip() or raw_text.strip()

        components: List[ArchitectureComponent] = []
        raw_components = payload.get("components")
        if isinstance(raw_components, list):
            for item in raw_components:
                component = ArchitectureService._parse_component(item)
                if component:
                    components.append(component)

        return summary, components, content_markdown

    @staticmethod
    def _parse_component(item: Any) -> ArchitectureComponent | None:
        if not isinstance(item, dict):
            return None
        try:
            key_files = item.get("key_files")
            return ArchitectureComponent(
                name=str(item.get("name", "")).strip() or "Unnamed component",
                responsibility=str(item.get("responsibility", "")).strip(),
                key_files=[str(f) for f in key_files] if isinstance(key_files, list) else [],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Architecture: skipping malformed component: %s", exc)
            return None


def get_architecture_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> ArchitectureService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return ArchitectureService(scanner_service=scanner_service, rag_service=rag_service, gemini_service=gemini_service)
