"""
app/core/constants.py

Static, non-secret constants used by the GitHub Repository Management
module (Step 3). Kept separate from `settings.py` because these are
code-level constants, not environment-driven configuration — they don't
change between dev/staging/prod and don't belong in `.env`.
"""

import re
from pathlib import Path

from app.core.settings import settings

# ---------------------------------------------------------------------------
# Storage location
# ---------------------------------------------------------------------------
# All cloned repositories live under <backend_root>/<REPOSITORY_STORAGE_PATH>/<name>.
# Driven by `settings.REPOSITORY_STORAGE_PATH` (Step 14) so it's a mountable
# Docker volume path in production without touching code — defaults to the
# same "data/repositories" used throughout local development.
REPOSITORIES_BASE_DIR: Path = Path(settings.REPOSITORY_STORAGE_PATH)

# ---------------------------------------------------------------------------
# GitHub URL validation
# ---------------------------------------------------------------------------
ALLOWED_GITHUB_HOSTS = {"github.com", "www.github.com"}

# Matches: https://github.com/owner/repo , https://github.com/owner/repo.git ,
# with or without a trailing slash. Deliberately does NOT match git@ SSH URLs —
# Step 3 only supports public HTTPS cloning.
GITHUB_URL_PATTERN = re.compile(
    r"^https?://(www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)"
    r"(\.git)?/?$"
)

# Reserved/unsafe folder name characters — used when deriving a filesystem-safe
# repository folder name from "owner/repo".
UNSAFE_FOLDER_NAME_CHARS = re.compile(r"[^A-Za-z0-9_-]")
MAX_REPO_FOLDER_NAME_LENGTH = 200

# ---------------------------------------------------------------------------
# Git operation limits
# ---------------------------------------------------------------------------
GIT_CLONE_TIMEOUT_SECONDS = 120
GIT_PULL_TIMEOUT_SECONDS = 60
GIT_CLONE_DEPTH = 1  # shallow clone — full history not needed for code analysis

# ---------------------------------------------------------------------------
# Error-message substrings used to classify low-level GitPython/GitCommandError
# failures into meaningful domain exceptions (auth vs. network vs. not-found).
# Matched case-insensitively against the raw git stderr output.
# ---------------------------------------------------------------------------
GIT_AUTH_FAILURE_MARKERS = (
    "could not read username",
    "could not read password",
    "authentication failed",
    "permission denied (publickey)",
    "please make sure you have the correct access rights",
    "terminal prompts disabled",
)

GIT_NOT_FOUND_MARKERS = (
    "repository not found",
    "not found",
)

GIT_NETWORK_FAILURE_MARKERS = (
    "could not resolve host",
    "failed to connect",
    "connection timed out",
    "network is unreachable",
    "temporary failure in name resolution",
)

# =============================================================================
# Repository Scanner & File Processing module (Step 4)
# =============================================================================

# Directories that are never scanned, regardless of depth. Matched against
# each individual path segment (not the full path), so "node_modules" is
# skipped whether it's at the repo root or nested inside a subfolder.
IGNORE_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".git",
        ".github",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "coverage",
        ".idea",
        ".vscode",
        ".chroma",
        "repositories",
        "logs",
    }
)

# Maximum size (bytes) for a file to be read/processed. Larger files are
# counted as "ignored" in statistics but never read into memory — this
# protects the scanner from accidentally loading huge binaries/datasets.
MAX_SCAN_FILE_SIZE_BYTES: int = 2 * 1024 * 1024  # 2 MB

# Number of bytes sampled from the start of a file to heuristically decide
# whether it's binary (presence of a NUL byte is a strong binary signal).
BINARY_SNIFF_CHUNK_SIZE: int = 8192

# Encodings tried in order when reading a text file. Most repos are UTF-8;
# latin-1 never raises UnicodeDecodeError (every byte is valid) so it's a
# safe last-resort fallback rather than silently dropping the file.
TEXT_FILE_ENCODINGS: tuple[str, ...] = ("utf-8", "utf-8-sig", "latin-1")

# Filenames (exact match, case-sensitive) treated as a supported language
# even though they have no file extension.
SPECIAL_FILENAME_LANGUAGES: dict[str, str] = {
    "Dockerfile": "Dockerfile",
    "Makefile": "Text",
}

# Extension -> language name. Drives both "is this file supported?" and
# the language breakdown in repository statistics. Keys are lowercase and
# include the leading dot to match `Path.suffix` directly.
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TSX",
    ".jsx": "JSX",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".less": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".txt": "Text",
}
