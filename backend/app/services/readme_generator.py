"""
app/services/readme_generator.py

README Generator (Step 13). Grounds Gemini with deterministic signals —
language breakdown (Scanner, Step 4), detected likely entry points, and
an on-disk LICENSE file, if any (GitHubService's clone path, Step 3) —
plus broad RAG-retrieved context (Step 8), then asks Gemini to write the
actual README content as Markdown.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import Depends

from app.core.constants import REPOSITORIES_BASE_DIR
from app.core.exceptions import ScanNotPerformedError
from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_readme_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import ReadmeGenerationRequest, ReadmeGenerationResponse
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.github_service import GitHubService, get_github_service
from app.services.rag_service import RAGService, get_rag_service
from app.services.scanner_service import ScannerService, get_scanner_service

logger = get_logger("services.readme_generator")

_RETRIEVAL_TOP_K = 15
_README_QUERY = (
    "project purpose, main features, how to install and run it, folder structure, and API endpoints"
)
_ENTRYPOINT_NAMES = {
    "main.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts",
    "main.go", "main.rs", "Program.cs",
}
_LICENSE_FILENAMES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
_LICENSE_KEYWORDS = {
    "MIT License": "MIT",
    "Apache License": "Apache-2.0",
    "GNU GENERAL PUBLIC LICENSE": "GPL",
    "BSD": "BSD",
    "Mozilla Public License": "MPL-2.0",
}
_DEFAULT_SECTIONS = [
    "Project Overview", "Features", "Installation", "Usage",
    "Folder Structure", "Architecture", "License", "Contributing",
]


class ReadmeGeneratorService:
    def __init__(
        self,
        scanner_service: ScannerService,
        rag_service: RAGService,
        gemini_service: GeminiService,
        github_service: GitHubService,
        base_dir: Path = REPOSITORIES_BASE_DIR,
    ) -> None:
        self.scanner_service = scanner_service
        self.rag_service = rag_service
        self.gemini_service = gemini_service
        self.github_service = github_service
        self.base_dir = base_dir

    async def generate(self, request: ReadmeGenerationRequest) -> ReadmeGenerationResponse:
        info = await self.github_service.get_repository_status(request.repository_name)
        language_summary = self._build_language_summary(request.repository_name)
        entrypoints = self._detect_entrypoints(request.repository_name)
        license_name = request.license_name or self._detect_license(request.repository_name)

        _, chunks = await self.rag_service.retrieve(
            repository_name=request.repository_name,
            question=_README_QUERY,
            top_k=_RETRIEVAL_TOP_K,
        )
        sources = chunks_to_sources(chunks)

        prompt = build_readme_prompt(
            chunks=chunks,
            sources=sources,
            repo_display_name=f"{info.owner}/{info.repo}",
            language_summary=language_summary,
            detected_entrypoints=entrypoints or "(none detected)",
            license_name=license_name,
            include_badges=request.include_badges,
        )
        raw_text, _usage = await self.gemini_service.generate(prompt)
        markdown, sections = self._parse_response(raw_text)

        logger.info("README generated | repo=%s | sections=%d", request.repository_name, len(sections))

        return ReadmeGenerationResponse(
            repository_name=request.repository_name,
            markdown=markdown,
            sections_included=sections,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Deterministic grounding signals
    # ------------------------------------------------------------------
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

    def _detect_entrypoints(self, repository_name: str) -> str:
        try:
            files = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            return ""
        matches = [f.relative_path for f in files if f.relative_path.split("/")[-1] in _ENTRYPOINT_NAMES]
        return "\n".join(f"- {m}" for m in matches[:10])

    def _detect_license(self, repository_name: str) -> Optional[str]:
        local_path = self.base_dir / repository_name
        for filename in _LICENSE_FILENAMES:
            license_file = local_path / filename
            if license_file.exists():
                try:
                    text = license_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                except OSError:
                    continue
                for keyword, short_name in _LICENSE_KEYWORDS.items():
                    if keyword.lower() in text.lower():
                        return short_name
                return "See LICENSE file"
        return None

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw_text: str) -> tuple[str, List[str]]:
        payload = extract_json_payload(raw_text)
        if isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            sections = payload.get("sections_included")
            if markdown:
                return markdown, [str(s) for s in sections] if isinstance(sections, list) else _DEFAULT_SECTIONS

        logger.warning("README generator: Gemini response was not parseable JSON — returning raw text.")
        return raw_text.strip() or "# README\n\n(Could not generate README content.)", _DEFAULT_SECTIONS


def get_readme_generator_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
    github_service: GitHubService = Depends(get_github_service),
) -> ReadmeGeneratorService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return ReadmeGeneratorService(
        scanner_service=scanner_service,
        rag_service=rag_service,
        gemini_service=gemini_service,
        github_service=github_service,
    )
