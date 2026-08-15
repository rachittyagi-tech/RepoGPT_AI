"""
tests/test_chunking_utils.py

Pure unit tests for app/utils/text_utils.py. No network, no filesystem,
no cloned repository required.
"""

from app.utils.text_utils import (
    compute_chunk_size_stats,
    get_langchain_language,
    is_blank_content,
)


def test_is_blank_content() -> None:
    assert is_blank_content("") is True
    assert is_blank_content("   \n\t  ") is True
    assert is_blank_content("x") is False


def test_get_langchain_language_supported() -> None:
    assert get_langchain_language("Python") is not None
    assert get_langchain_language("Java") is not None
    assert get_langchain_language("Markdown") is not None


def test_get_langchain_language_unsupported_returns_none() -> None:
    # JSON/YAML/CSS/SQL/Shell/Text have no dedicated LangChain splitter —
    # they should fall back to the generic RecursiveCharacterTextSplitter.
    assert get_langchain_language("JSON") is None
    assert get_langchain_language("YAML") is None
    assert get_langchain_language("Text") is None


def test_compute_chunk_size_stats_empty() -> None:
    assert compute_chunk_size_stats([]) == (0.0, 0, 0)


def test_compute_chunk_size_stats_typical() -> None:
    average, smallest, largest = compute_chunk_size_stats([100, 200, 300])
    assert average == 200.0
    assert smallest == 100
    assert largest == 300
