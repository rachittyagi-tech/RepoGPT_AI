"""
app/services/chunking_service.py

Business logic for the Code Processing Pipeline (Step 5):
    - Loads scanned files (from Step 4's cache) as LangChain Documents
    - Splits each Document into chunks, using a syntax-aware splitter
      (`RecursiveCharacterTextSplitter.from_language`) when LangChain
      supports the file's language — this tries to keep function/class
      bodies intact rather than cutting mid-block — and a generic
      character splitter otherwise
    - Enriches each chunk with `chunk_number`/`total_chunks` metadata
    - Aggregates repository-wide chunk statistics
    - Caches the result per repository (class-level, same pattern as
      `ScannerService`) so GET /statistics and GET /chunks don't need to
      reprocess on every call

Clean Architecture note: `ChunkingService` itself has no FastAPI import —
only the `get_chunking_service` provider function at the bottom uses
`Depends`, which is the conventional, narrow exception for wiring DI.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar, Dict, List, Optional

from fastapi import Depends
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.chunk_config import ChunkSettings, get_chunk_settings
from app.core.exceptions import ChunkingFailedError, ChunkingNotPerformedError, NoScannedFilesError
from app.core.logging import get_logger
from app.schemas.chunking import ChunkMetadata, ChunkRecord, ChunkStatistics
from app.services.document_loader import load_documents
from app.services.scanner_service import ScannerService, get_scanner_service
from app.utils.text_utils import compute_chunk_size_stats, get_langchain_language

logger = get_logger("services.chunking")


@dataclass
class ChunkingResult:
    """Internal container for one repository's cached chunking result."""

    chunks: List[ChunkRecord] = field(default_factory=list)
    statistics: Optional[ChunkStatistics] = None


class ChunkingService:
    """Converts a scanned repository's files into chunked LangChain Documents."""

    # Shared across all instances/requests — same rationale as ScannerService.
    _CHUNK_CACHE: ClassVar[Dict[str, ChunkingResult]] = {}

    def __init__(
        self,
        scanner_service: ScannerService,
        settings: Optional[ChunkSettings] = None,
    ) -> None:
        self.scanner_service = scanner_service
        self.settings = settings or get_chunk_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def process_repository(
        self,
        repository_name: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> ChunkStatistics:
        """
        Runs the full pipeline for `repository_name`: load scanned files ->
        build Documents -> split into chunks -> aggregate statistics ->
        cache. Returns the resulting statistics.

        Raises:
            NoScannedFilesError: if the repository has no cached scan
                (or the scan found zero supported files).
            ChunkingFailedError: on unexpected processing errors.
        """
        start_time = time.perf_counter()
        effective_size, effective_overlap = self._resolve_chunk_params(
            chunk_size, chunk_overlap, repository_name
        )

        scanned_files = self.scanner_service.get_cached_files(repository_name)
        if not scanned_files:
            raise NoScannedFilesError(repository_name)

        logger.info(
            "Starting chunking | repo=%s | files=%d | chunk_size=%d | overlap=%d",
            repository_name,
            len(scanned_files),
            effective_size,
            effective_overlap,
        )

        try:
            documents, files_skipped = load_documents(scanned_files, repository_name)
            chunks = await asyncio.to_thread(
                self._split_documents, documents, effective_size, effective_overlap, repository_name
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chunking failed | repo=%s", repository_name)
            raise ChunkingFailedError(repository_name, reason=str(exc)) from exc

        statistics = self._build_statistics(
            repository_name=repository_name,
            total_files=len(scanned_files),
            files_skipped=files_skipped,
            documents_created=len(documents),
            chunks=chunks,
            processing_time=time.perf_counter() - start_time,
            chunk_size=effective_size,
            chunk_overlap=effective_overlap,
        )

        self._CHUNK_CACHE[repository_name] = ChunkingResult(chunks=chunks, statistics=statistics)

        logger.info(
            "Chunking complete | repo=%s | documents=%d | chunks=%d | time=%.3fs",
            repository_name,
            len(documents),
            len(chunks),
            statistics.processing_time_seconds,
        )
        return statistics

    def get_cached_chunks(self, repository_name: str) -> List[ChunkRecord]:
        """Raises `ChunkingNotPerformedError` if /process hasn't been run yet."""
        return self._get_cached_result(repository_name).chunks

    def get_cached_statistics(self, repository_name: str) -> ChunkStatistics:
        """Raises `ChunkingNotPerformedError` if /process hasn't been run yet."""
        result = self._get_cached_result(repository_name)
        assert result.statistics is not None  # invariant: set together with chunks
        return result.statistics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_cached_result(self, repository_name: str) -> ChunkingResult:
        result = self._CHUNK_CACHE.get(repository_name)
        if result is None:
            raise ChunkingNotPerformedError(repository_name)
        return result

    def _resolve_chunk_params(
        self, chunk_size: Optional[int], chunk_overlap: Optional[int], repository_name: str
    ) -> tuple[int, int]:
        """Applies request overrides on top of env defaults, with a safety clamp."""
        size = chunk_size or self.settings.SIZE
        overlap = chunk_overlap if chunk_overlap is not None else self.settings.OVERLAP

        if overlap >= size:
            clamped = max(0, size // 5)
            logger.warning(
                "chunk_overlap (%d) >= chunk_size (%d) for repo=%s — clamped overlap to %d",
                overlap,
                size,
                repository_name,
                clamped,
            )
            overlap = clamped

        return size, overlap

    def _split_documents(
        self,
        documents: List[Document],
        chunk_size: int,
        chunk_overlap: int,
        repository_name: str,
    ) -> List[ChunkRecord]:
        """Synchronous splitting loop (runs inside asyncio.to_thread)."""
        all_chunks: List[ChunkRecord] = []

        for document in documents:
            if len(all_chunks) >= self.settings.MAX_CHUNKS_PER_REPOSITORY:
                logger.warning(
                    "MAX_CHUNKS_PER_REPOSITORY (%d) reached for repo=%s — stopping further chunking.",
                    self.settings.MAX_CHUNKS_PER_REPOSITORY,
                    repository_name,
                )
                break

            file_chunks = self._split_single_document(document, chunk_size, chunk_overlap)
            all_chunks.extend(file_chunks)

        return all_chunks

    def _split_single_document(
        self, document: Document, chunk_size: int, chunk_overlap: int
    ) -> List[ChunkRecord]:
        relative_path = document.metadata["relative_file_path"]
        splitter = self._build_splitter(document.metadata["language"], chunk_size, chunk_overlap)

        try:
            split_texts = splitter.split_text(document.page_content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to split %s | error=%s — skipping file.", relative_path, exc)
            return []

        if not split_texts:
            return []

        if len(split_texts) > self.settings.MAX_CHUNKS_PER_FILE:
            logger.warning(
                "File %s produced %d chunks, truncating to MAX_CHUNKS_PER_FILE=%d",
                relative_path,
                len(split_texts),
                self.settings.MAX_CHUNKS_PER_FILE,
            )
            split_texts = split_texts[: self.settings.MAX_CHUNKS_PER_FILE]

        total_chunks = len(split_texts)
        records: List[ChunkRecord] = []
        for index, text in enumerate(split_texts, start=1):
            metadata = ChunkMetadata(
                repository_name=document.metadata["repository_name"],
                repository_path=document.metadata["repository_path"],
                relative_file_path=relative_path,
                absolute_file_path=document.metadata["absolute_file_path"],
                language=document.metadata["language"],
                extension=document.metadata["extension"],
                file_size=document.metadata["file_size"],
                lines_of_code=document.metadata["lines_of_code"],
                chunk_number=index,
                total_chunks=total_chunks,
            )
            records.append(ChunkRecord(metadata=metadata, content=text, character_count=len(text)))

        return records

    def _build_splitter(
        self, language: str, chunk_size: int, chunk_overlap: int
    ) -> RecursiveCharacterTextSplitter:
        """
        Returns a syntax-aware splitter (tries to preserve function/class
        boundaries) when LangChain has one for `language`, otherwise falls
        back to the generic separator chain from ChunkSettings.
        """
        langchain_language = get_langchain_language(language)
        if langchain_language is not None:
            return RecursiveCharacterTextSplitter.from_language(
                language=langchain_language,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.settings.DEFAULT_SEPARATORS,
        )

    @staticmethod
    def _build_statistics(
        repository_name: str,
        total_files: int,
        files_skipped: int,
        documents_created: int,
        chunks: List[ChunkRecord],
        processing_time: float,
        chunk_size: int,
        chunk_overlap: int,
    ) -> ChunkStatistics:
        lengths = [c.character_count for c in chunks]
        average, smallest, largest = compute_chunk_size_stats(lengths)

        return ChunkStatistics(
            repository_name=repository_name,
            processing_time_seconds=round(processing_time, 3),
            total_files=total_files,
            files_skipped=files_skipped,
            documents_created=documents_created,
            chunks_created=len(chunks),
            average_chunk_size=average,
            largest_chunk=largest,
            smallest_chunk=smallest,
            chunk_size_setting=chunk_size,
            chunk_overlap_setting=chunk_overlap,
            processed_at=datetime.now(timezone.utc),
        )


def get_chunking_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
) -> ChunkingService:
    """FastAPI dependency provider — see app/api/chunking.py."""
    return ChunkingService(scanner_service=scanner_service)
