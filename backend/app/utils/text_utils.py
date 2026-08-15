"""
app/utils/text_utils.py

Text-level helpers for the Code Processing Pipeline (Step 5):
    - Mapping our internal language names (from Step 4's language_detector)
      to LangChain's `Language` enum, where a dedicated code-aware splitter
      exists for that language.
    - Basic content sanity checks (empty/whitespace-only detection).
    - Chunk-size statistics helpers (avg/min/max) shared by the service
      and the API response layer.

Kept dependency-light and pure so it's trivially unit-testable.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from langchain_text_splitters import Language

# Maps our Step 4 language names -> LangChain's Language enum, but ONLY for
# languages LangChain has a dedicated syntax-aware splitter for (it knows
# how to split on "def "/"class " for Python, "function "/"class " for JS,
# etc). Languages not in this map fall back to the generic
# RecursiveCharacterTextSplitter with DEFAULT_SEPARATORS.
LANGUAGE_TO_LANGCHAIN: dict[str, Language] = {
    "Python": Language.PYTHON,
    "JavaScript": Language.JS,
    "TypeScript": Language.TS,
    "TSX": Language.TS,
    "JSX": Language.JS,
    "Java": Language.JAVA,
    "Go": Language.GO,
    "Rust": Language.RUST,
    "C": Language.C,
    "C++": Language.CPP,
    "C#": Language.CSHARP,
    "PHP": Language.PHP,
    "Ruby": Language.RUBY,
    "Swift": Language.SWIFT,
    "Kotlin": Language.KOTLIN,
    "HTML": Language.HTML,
    "Markdown": Language.MARKDOWN,
}


def get_langchain_language(language: str) -> Optional[Language]:
    """
    Returns the LangChain `Language` enum for a syntax-aware splitter, or
    `None` if this language should use the generic character splitter
    (e.g. JSON, YAML, CSS, SQL, Shell, Text, Dockerfile).
    """
    return LANGUAGE_TO_LANGCHAIN.get(language)


def is_blank_content(content: str) -> bool:
    """True if `content` is empty or contains only whitespace."""
    return not content or not content.strip()


def compute_chunk_size_stats(chunk_lengths: Sequence[int]) -> tuple[float, int, int]:
    """
    Returns (average, smallest, largest) character length across all
    chunks. Returns (0.0, 0, 0) for an empty sequence rather than raising,
    so callers can always render statistics safely even with zero chunks.
    """
    if not chunk_lengths:
        return 0.0, 0, 0
    average = sum(chunk_lengths) / len(chunk_lengths)
    return round(average, 2), min(chunk_lengths), max(chunk_lengths)
