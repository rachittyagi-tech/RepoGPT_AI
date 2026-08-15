"""
app/services/context_builder.py

Implements the final two RAG pipeline stages:
    - "Prompt Context Builder": assembles ranked/deduplicated/compressed
      chunks into a single context string, enforcing a token budget
      (dropping lowest-ranked chunks first if the budget is exceeded),
      and builds the `SourceReference` citation list
    - "Return Final Context": calls `app.prompts.rag_prompt.build_prompt`
      to produce the fully assembled, ready-to-send prompt string

Token estimation uses `tiktoken`'s `cl100k_base` encoding as a
model-agnostic approximation (Step 9 may use any LLM; this keeps token
budgeting reasonable without coupling to one specific model's tokenizer).
Falls back to a chars/4 heuristic if `tiktoken` can't load (e.g. offline
first run before its vocab file is cached).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.exceptions import TokenLimitExceededError
from app.core.logging import get_logger
from app.core.rag_config import RAGSettings, get_rag_settings
from app.prompts.rag_prompt import build_prompt
from app.schemas.rag import ConversationTurn, RetrievedChunk, SourceReference

logger = get_logger("services.context_builder")

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # noqa: BLE001 — tiktoken missing or offline on first run
    _ENCODING = None
    logger.warning("tiktoken unavailable — falling back to a chars/4 token estimate.")


def estimate_tokens(text: str) -> int:
    """Best-effort token count for `text`, used throughout the RAG pipeline."""
    if not text:
        return 0
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // 4)


@dataclass
class ContextBuildResult:
    context_text: str
    final_prompt: str
    sources: List[SourceReference] = field(default_factory=list)
    estimated_tokens: int = 0
    chunks_included: int = 0
    chunks_dropped: int = 0


class ContextBuilder:
    """Assembles ranked chunks into a token-budgeted context and final prompt."""

    def __init__(self, settings: Optional[RAGSettings] = None) -> None:
        self.settings = settings or get_rag_settings()

    def build(
        self,
        question: str,
        chunks: List[RetrievedChunk],
        conversation_history: Optional[List[ConversationTurn]] = None,
    ) -> ContextBuildResult:
        """
        Greedily includes chunks (already ranked best-first) until the
        context token budget would be exceeded, then assembles the final
        prompt via `app.prompts.rag_prompt.build_prompt`.

        Raises:
            TokenLimitExceededError: if the question alone already exceeds
                the total context budget — nothing else could ever fit.
        """
        question_tokens = estimate_tokens(question)
        if question_tokens >= self.settings.RAG_MAX_CONTEXT_TOKENS:
            raise TokenLimitExceededError(question_tokens, self.settings.RAG_MAX_CONTEXT_TOKENS)

        conversation_history = conversation_history or []
        conversation_text, conversation_tokens = self._budget_conversation(conversation_history)

        remaining_budget = (
            self.settings.RAG_MAX_CONTEXT_TOKENS - question_tokens - conversation_tokens
        )

        included_chunks: List[RetrievedChunk] = []
        included_sources: List[SourceReference] = []
        context_parts: List[str] = []
        used_tokens = 0
        dropped = 0

        for chunk in chunks:
            snippet = self._format_chunk(chunk)
            snippet_tokens = estimate_tokens(snippet)

            if used_tokens + snippet_tokens > remaining_budget:
                dropped += 1
                continue

            included_chunks.append(chunk)
            context_parts.append(snippet)
            used_tokens += snippet_tokens
            included_sources.append(
                SourceReference(
                    repository_name=chunk.repository_name,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    chunk_number=chunk.chunk_number,
                    total_chunks=chunk.total_chunks,
                    score=chunk.score,
                )
            )

        context_text = "\n\n".join(context_parts)
        final_prompt = build_prompt(
            question=question,
            context_text=context_text,
            sources=included_sources,
            conversation_history=conversation_history,
        )

        total_estimated_tokens = question_tokens + conversation_tokens + used_tokens

        if dropped:
            logger.info(
                "Context budget reached — included %d chunk(s), dropped %d for token limit.",
                len(included_chunks),
                dropped,
            )

        return ContextBuildResult(
            context_text=context_text,
            final_prompt=final_prompt,
            sources=included_sources,
            estimated_tokens=total_estimated_tokens,
            chunks_included=len(included_chunks),
            chunks_dropped=dropped,
        )

    def _budget_conversation(self, history: List[ConversationTurn]) -> Tuple[str, int]:
        """
        Keeps the most recent turns that fit within
        `RAG_MAX_CONVERSATION_TOKENS`, working backwards from the end of
        the conversation (most recent context matters most).
        """
        if not history:
            return "", 0

        budget = self.settings.RAG_MAX_CONVERSATION_TOKENS
        kept: List[ConversationTurn] = []
        used = 0

        for turn in reversed(history):
            turn_text = f"{turn.role}: {turn.content}"
            turn_tokens = estimate_tokens(turn_text)
            if used + turn_tokens > budget:
                break
            kept.insert(0, turn)
            used += turn_tokens

        combined = "\n".join(f"{t.role}: {t.content}" for t in kept)
        return combined, used

    @staticmethod
    def _format_chunk(chunk: RetrievedChunk) -> str:
        return (
            f"[Source: {chunk.file_path} | {chunk.language} | "
            f"chunk {chunk.chunk_number}/{chunk.total_chunks} | score {chunk.score:.2f}]\n"
            f"{chunk.content}"
        )


def get_context_builder() -> ContextBuilder:
    """FastAPI dependency provider — see app/services/rag_service.py."""
    return ContextBuilder()
