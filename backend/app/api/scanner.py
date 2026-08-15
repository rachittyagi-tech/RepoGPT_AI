"""
app/api/scanner.py

HTTP layer for the Repository Scanner & File Processing module (Step 4).

Thin router — each endpoint validates input via Pydantic, delegates to
`ScannerService`, and shapes the response. All error translation (repo
not cloned, scan not yet performed, scan failures) happens via domain
exceptions + the global exception handlers from Step 2/3.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.logging import get_logger
from app.schemas.scanner import (
    FileListResponse,
    ScanRequest,
    ScanResponse,
    StatisticsResponse,
)
from app.services.scanner_service import ScannerService, get_scanner_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.scanner")

router = APIRouter(tags=["Scanner"], dependencies=[Depends(rate_limit("scanner", 10, 60))])


@router.post(
    "/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Recursively scan a cloned repository and cache the results",
)
async def scan_repository(
    payload: ScanRequest,
    service: ScannerService = Depends(get_scanner_service),
) -> ScanResponse:
    """
    Scans every file in `repository_name` (which must already be cloned
    via POST /api/github/clone), skipping ignored directories, binaries,
    and oversized files. Results are cached in memory for subsequent
    GET /files and GET /statistics calls.

    Returns 404 if the repository hasn't been cloned locally.
    """
    logger.info("Received scan request | repo=%s", payload.repository_name)
    statistics = await service.scan_repository(payload.repository_name)
    return ScanResponse(
        message=f"Scan complete for '{payload.repository_name}'.",
        statistics=statistics,
    )


@router.get(
    "/files/{repository}",
    response_model=FileListResponse,
    status_code=status.HTTP_200_OK,
    summary="List scanned files for a repository (from the cached scan)",
)
async def list_scanned_files(
    repository: str,
    language: Optional[str] = Query(
        default=None, description="Filter by language, e.g. 'Python' (case-insensitive)."
    ),
    include_content: bool = Query(
        default=True, description="Include full file content in the response."
    ),
    service: ScannerService = Depends(get_scanner_service),
) -> FileListResponse:
    """
    Returns the cached list of scanned files for `repository`.

    Returns 404 if the repository has never been scanned — call
    POST /api/scanner/scan first.
    """
    files = service.get_cached_files(repository, language=language)

    if not include_content:
        files = [f.model_copy(update={"content": ""}) for f in files]

    return FileListResponse(
        repository_name=repository,
        count=len(files),
        language_filter=language,
        files=files,
    )


@router.get(
    "/statistics/{repository}",
    response_model=StatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregate statistics for a scanned repository",
)
async def get_statistics(
    repository: str,
    service: ScannerService = Depends(get_scanner_service),
) -> StatisticsResponse:
    """
    Returns total/supported/ignored file counts, language breakdown,
    total lines of code, and size for `repository`'s last scan.

    Returns 404 if the repository has never been scanned.
    """
    statistics = service.get_cached_statistics(repository)
    return StatisticsResponse(statistics=statistics)
