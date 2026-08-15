"""
app/utils/file_utils.py

Low-level, framework-free filesystem helpers used by the Repository
Scanner module. Every function here is pure/synchronous and side-effect
free except for reading from disk — callers (services/file_loader.py)
are responsible for running these inside `asyncio.to_thread` where needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.constants import (
    BINARY_SNIFF_CHUNK_SIZE,
    IGNORE_DIRECTORIES,
    MAX_SCAN_FILE_SIZE_BYTES,
    TEXT_FILE_ENCODINGS,
)


def should_ignore_directory(directory_name: str) -> bool:
    """True if a directory (by name only, not full path) must be skipped."""
    return directory_name in IGNORE_DIRECTORIES


def is_binary_file(path: Path) -> bool:
    """
    Heuristically detects binary files by sniffing the first chunk of bytes
    for a NUL byte — the same approach used by `git` and most text editors.
    Returns True (treat as binary/unreadable) if the file can't be opened.
    """
    try:
        with path.open("rb") as f:
            chunk = f.read(BINARY_SNIFF_CHUNK_SIZE)
        return b"\x00" in chunk
    except OSError:
        return True


def exceeds_size_limit(path: Path, max_bytes: int = MAX_SCAN_FILE_SIZE_BYTES) -> bool:
    """True if the file's on-disk size exceeds the configured scan limit."""
    try:
        return path.stat().st_size > max_bytes
    except OSError:
        return True


def read_text_safely(path: Path) -> Optional[str]:
    """
    Reads a text file's full contents, trying each encoding in
    `TEXT_FILE_ENCODINGS` in order. Returns `None` (rather than raising) if
    the file cannot be read at all — callers log this as a skipped file
    instead of failing the whole scan.
    """
    for encoding in TEXT_FILE_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def count_lines(content: str) -> int:
    """Counts lines in `content`, treating a trailing newline as not adding an extra blank line."""
    if not content:
        return 0
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def get_directory_size_bytes(path: Path) -> int:
    """Total on-disk size (bytes) of every file under `path`, recursively."""
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                continue
    return total
