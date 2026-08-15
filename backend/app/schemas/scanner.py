"""
app/schemas/scanner.py

Pydantic v2 request/response DTOs for the Repository Scanner & File
Processing module (Step 4).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class ScanRequest(BaseModel):
    """Body for POST /api/scanner/scan"""

    repository_name: str = Field(
        ...,
        description="Folder name of a repository already cloned via /api/github/clone (owner__repo).",
        examples=["psf__requests"],
    )


# ---------------------------------------------------------------------------
# Per-file record
# ---------------------------------------------------------------------------
class ScannedFile(BaseModel):
    """Full metadata + content for one supported source file."""

    repository_name: str
    relative_path: str
    absolute_path: str
    language: str
    extension: str
    size_bytes: int
    line_count: int
    last_modified: datetime
    content: str


class ScannedFileSummary(BaseModel):
    """Lightweight version of `ScannedFile` without file content — used by list views."""

    repository_name: str
    relative_path: str
    absolute_path: str
    language: str
    extension: str
    size_bytes: int
    line_count: int
    last_modified: datetime


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
class ScanStatistics(BaseModel):
    repository_name: str
    total_files: int = Field(..., description="All files encountered, supported + ignored.")
    supported_files: int = Field(..., description="Files successfully parsed and included in the scan.")
    ignored_files: int = Field(..., description="Files skipped (unsupported type, binary, or too large).")
    programming_languages: List[str] = Field(..., description="Distinct languages detected.")
    language_counts: Dict[str, int] = Field(..., description="File count per detected language.")
    total_lines_of_code: int
    repository_size_bytes: int
    repository_size_mb: float
    scanned_at: datetime


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class ScanResponse(BaseModel):
    success: bool = True
    message: str
    statistics: ScanStatistics


class FileListResponse(BaseModel):
    success: bool = True
    repository_name: str
    count: int
    language_filter: Optional[str] = None
    files: List[ScannedFile] | List[ScannedFileSummary]


class StatisticsResponse(BaseModel):
    success: bool = True
    statistics: ScanStatistics
