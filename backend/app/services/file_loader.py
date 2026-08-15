"""
app/services/file_loader.py

Handles loading ONE file at a time: deciding whether it's supported,
safely reading its contents, and building a `ScannedFile` record.

Kept separate from `scanner_service.py` (Single Responsibility):
- `file_loader.py`   → "how do I safely turn one Path into a ScannedFile?"
- `scanner_service.py` → "how do I walk a whole repo and aggregate results?"

This separation also makes the per-file logic independently unit-testable
without needing a full repository on disk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger
from app.schemas.scanner import ScannedFile
from app.utils.file_utils import (
    count_lines,
    exceeds_size_limit,
    is_binary_file,
    read_text_safely,
)
from app.utils.language_detector import detect_language

logger = get_logger("services.file_loader")


def load_file(path: Path, repo_root: Path, repository_name: str) -> Optional[ScannedFile]:
    """
    Attempts to load `path` as a supported source file.

    Returns `None` (and logs the reason at DEBUG level) if the file should
    be ignored: unsupported extension, exceeds the size limit, looks
    binary, or can't be decoded as text. This lets the caller simply do
    `if result: files.append(result)` without needing try/except per file.
    """
    language = detect_language(path)
    if language is None:
        logger.debug("Ignored (unsupported type): %s", path)
        return None

    if exceeds_size_limit(path):
        logger.debug("Ignored (exceeds size limit): %s", path)
        return None

    if is_binary_file(path):
        logger.debug("Ignored (binary content): %s", path)
        return None

    content = read_text_safely(path)
    if content is None:
        logger.warning("Ignored (unreadable/encoding failure): %s", path)
        return None

    try:
        stat = path.stat()
    except OSError as exc:
        logger.warning("Ignored (stat failed): %s | %s", path, exc)
        return None

    return ScannedFile(
        repository_name=repository_name,
        relative_path=str(path.relative_to(repo_root)),
        absolute_path=str(path.resolve()),
        language=language,
        extension=path.suffix.lower() or path.name,
        size_bytes=stat.st_size,
        line_count=count_lines(content),
        last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        content=content,
    )
