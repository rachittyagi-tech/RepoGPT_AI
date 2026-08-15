"""
app/services/query_rewriter.py

Query validation, rule-based rewriting, and keyword extraction for the
RAG pipeline (Step 8).

No LLM call happens here (Gemini Chat is explicitly out of scope until
Step 9) — rewriting is deterministic and rule-based: whitespace/markdown
cleanup, common programming-abbreviation expansion (improves embedding
recall), and optional language-hint injection. Keyword extraction feeds
`ContextRanker`'s hybrid (semantic + keyword) scoring.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set

from app.core.exceptions import InvalidQueryError
from app.core.logging import get_logger
from app.core.rag_config import RAGSettings, get_rag_settings

logger = get_logger("services.query_rewriter")

# Common shorthand -> expanded form. Expanding abbreviations before
# embedding tends to improve recall, since indexed code/comments usually
# spell things out in full.
_ABBREVIATION_EXPANSIONS = {
    r"\bfunc\b": "function",
    r"\bfn\b": "function",
    r"\bauth\b": "authentication",
    r"\bconfig\b": "configuration",
    r"\bdb\b": "database",
    r"\benv\b": "environment",
    r"\bexc\b": "exception",
    r"\bimpl\b": "implementation",
    r"\binit\b": "initialize",
    r"\barg\b": "argument",
    r"\bargs\b": "arguments",
    r"\bkwarg\b": "keyword argument",
    r"\bkwargs\b": "keyword arguments",
}

# Stopwords stripped when extracting keywords for hybrid retrieval —
# short, code-search-oriented list rather than a full NLP stopword corpus.
_STOPWORDS: Set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "how", "what", "when", "where", "why", "who", "which", "does", "do",
    "did", "to", "of", "in", "on", "for", "and", "or", "with", "this",
    "that", "it", "its", "as", "by", "from", "can", "could", "should",
    "would", "please", "explain", "show", "me", "tell", "about",
}

_WORD_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class QueryRewriter:
    """Validates, rewrites, and extracts keywords from a user's question."""

    def __init__(self, settings: Optional[RAGSettings] = None) -> None:
        self.settings = settings or get_rag_settings()

    def validate(self, question: str) -> str:
        """
        Validates `question`, returning it trimmed.

        Raises:
            InvalidQueryError: if empty, too short, or too long.
        """
        trimmed = (question or "").strip()

        if not trimmed:
            raise InvalidQueryError("question cannot be empty.")
        if len(trimmed) < self.settings.RAG_MIN_QUERY_LENGTH:
            raise InvalidQueryError(
                f"question must be at least {self.settings.RAG_MIN_QUERY_LENGTH} characters."
            )
        if len(trimmed) > self.settings.RAG_MAX_QUERY_LENGTH:
            raise InvalidQueryError(
                f"question must not exceed {self.settings.RAG_MAX_QUERY_LENGTH} characters."
            )
        return trimmed

    def rewrite(self, question: str, language: Optional[str] = None) -> str:
        """
        Rule-based rewrite: collapses whitespace, strips markdown code
        fences/backticks, expands common abbreviations, and optionally
        prepends a language hint — all of which tend to improve embedding
        similarity for code-search queries without needing an LLM call.
        """
        text = question.strip()
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # drop embedded code blocks
        text = text.replace("`", "")
        text = re.sub(r"\s+", " ", text).strip()

        lowered = text.lower()
        for pattern, expansion in _ABBREVIATION_EXPANSIONS.items():
            lowered = re.sub(pattern, expansion, lowered)
        # Preserve original casing for the parts we didn't touch by only
        # using the expanded lowercase version if it actually changed —
        # otherwise keep the user's original casing/punctuation intact.
        rewritten = lowered if lowered != text.lower() else text

        if language:
            rewritten = f"In {language}: {rewritten}"

        if rewritten != question.strip():
            logger.debug("Query rewritten | original=%r | rewritten=%r", question, rewritten)

        return rewritten

    def extract_keywords(self, question: str) -> List[str]:
        """
        Returns lowercase, de-duplicated, stopword-filtered keyword tokens
        used for hybrid (keyword-overlap) ranking alongside semantic search.
        """
        words = _WORD_PATTERN.findall(question.lower())
        seen: Set[str] = set()
        keywords: List[str] = []
        for word in words:
            if word in _STOPWORDS or len(word) < 2:
                continue
            if word not in seen:
                seen.add(word)
                keywords.append(word)
        return keywords


def get_query_rewriter() -> QueryRewriter:
    """FastAPI dependency provider — see app/services/rag_service.py."""
    return QueryRewriter()
