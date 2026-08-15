"""
app/services/context_ranker.py

Implements three RAG pipeline stages:
    - "Similarity Ranking" via hybrid scoring (semantic + keyword overlap)
    - "Duplicate Removal" (near-identical chunks, e.g. repeated license
      headers or boilerplate, collapsed to their highest-scoring occurrence)
    - "Context Compression" (long chunks truncated to a character budget
      before they're added to the prompt, keeping head + tail — the parts
      most likely to contain a signature/summary and a return/conclusion)
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Set

from app.core.logging import get_logger
from app.core.rag_config import RAGSettings, get_rag_settings
from app.schemas.rag import RetrievedChunk

logger = get_logger("services.context_ranker")

_WHITESPACE_PATTERN = re.compile(r"\s+")


class ContextRanker:
    """Ranks, deduplicates, and compresses retrieved chunks before prompt assembly."""

    def __init__(self, settings: Optional[RAGSettings] = None) -> None:
        self.settings = settings or get_rag_settings()

    def rank(self, chunks: List[RetrievedChunk], keywords: List[str]) -> List[RetrievedChunk]:
        """
        Hybrid re-ranking: final `score` = semantic_weight * similarity +
        keyword_weight * keyword_overlap_ratio. Pure vector similarity can
        miss exact identifier matches (e.g. a function name typed verbatim
        in the question); blending in lexical overlap recovers those.

        Returns a new list sorted by the blended score, descending.
        """
        if not chunks:
            return []

        semantic_weight = self.settings.RAG_HYBRID_SEMANTIC_WEIGHT
        keyword_weight = self.settings.RAG_HYBRID_KEYWORD_WEIGHT

        reranked: List[RetrievedChunk] = []
        for chunk in chunks:
            keyword_overlap = self._keyword_overlap_ratio(chunk.content, keywords)
            blended_score = round(
                (semantic_weight * chunk.similarity_score) + (keyword_weight * keyword_overlap), 6
            )
            reranked.append(chunk.model_copy(update={"score": blended_score}))

        reranked.sort(key=lambda c: c.score, reverse=True)
        return reranked

    def deduplicate(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """
        Collapses near-identical chunks (e.g. the same boilerplate/license
        header appearing in many files) to their single highest-scoring
        occurrence. Chunks are assumed pre-sorted by score (call `rank`
        first) so "first occurrence wins" is equivalent to "best wins".
        """
        seen_hashes: Set[str] = set()
        deduplicated: List[RetrievedChunk] = []

        for chunk in chunks:
            normalized = _WHITESPACE_PATTERN.sub(" ", chunk.content).strip().lower()
            content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

            if content_hash in seen_hashes:
                logger.debug(
                    "Dropping duplicate chunk | file=%s | chunk=%d", chunk.file_path, chunk.chunk_number
                )
                continue

            seen_hashes.add(content_hash)
            deduplicated.append(chunk)

        return deduplicated

    def compress(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """
        Truncates any chunk whose content exceeds `RAG_MAX_CHARS_PER_CHUNK`,
        keeping the head and tail (most likely to contain a definition/
        signature and a return statement/summary) and marking the cut.
        """
        max_chars = self.settings.RAG_MAX_CHARS_PER_CHUNK
        compressed: List[RetrievedChunk] = []

        for chunk in chunks:
            if len(chunk.content) <= max_chars:
                compressed.append(chunk)
                continue

            half = max_chars // 2
            truncated = (
                f"{chunk.content[:half]}\n... [truncated for length] ...\n{chunk.content[-half:]}"
            )
            compressed.append(chunk.model_copy(update={"content": truncated}))
            logger.debug(
                "Compressed chunk | file=%s | chunk=%d | original_len=%d | new_len=%d",
                chunk.file_path,
                chunk.chunk_number,
                len(chunk.content),
                len(truncated),
            )

        return compressed

    @staticmethod
    def _keyword_overlap_ratio(content: str, keywords: List[str]) -> float:
        """Fraction of `keywords` that appear (case-insensitive) in `content`."""
        if not keywords:
            return 0.0
        lowered = content.lower()
        matches = sum(1 for kw in keywords if kw in lowered)
        return matches / len(keywords)


def get_context_ranker() -> ContextRanker:
    """FastAPI dependency provider — see app/services/rag_service.py."""
    return ContextRanker()
