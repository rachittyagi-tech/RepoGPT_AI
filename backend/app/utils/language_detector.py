"""
app/utils/language_detector.py

Pure, framework-free helper that maps a file path to a programming
language name (or `None` if the file type isn't supported).

Kept separate from `file_utils.py` (Single Responsibility): this module
only knows "extension/filename -> language", nothing about reading
bytes, encodings, or file sizes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.constants import EXTENSION_LANGUAGE_MAP, SPECIAL_FILENAME_LANGUAGES


def detect_language(path: Path) -> Optional[str]:
    """
    Returns the detected language name for `path`, or `None` if the file
    type is not in the supported list (caller should treat it as ignored).

    Resolution order:
        1. Exact filename match (e.g. "Dockerfile", "Makefile") — these
           have no extension, so they must be checked before suffix lookup.
        2. Extension lookup (case-insensitive) against EXTENSION_LANGUAGE_MAP.
    """
    if path.name in SPECIAL_FILENAME_LANGUAGES:
        return SPECIAL_FILENAME_LANGUAGES[path.name]

    suffix = path.suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(suffix)


def is_supported_file(path: Path) -> bool:
    """Convenience boolean wrapper around `detect_language`."""
    return detect_language(path) is not None
