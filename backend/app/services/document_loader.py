"""
app/services/document_loader.py

Converts Step 4's `ScannedFile` records into LangChain `Document` objects,
attaching the metadata needed downstream for chunking and (in a later
step) retrieval/citation back to exact files.

Kept separate from `chunking_service.py` (Single Responsibility):
    - document_loader.py   -> "how do I turn one ScannedFile into a Document?"
    - chunking_service.py  -> "how do I split a list of Documents into
      chunks and aggregate statistics?"
"""

from __future__ import annotations

from typing import List, Tuple

from langchain_core.documents import Document

from app.core.constants import REPOSITORIES_BASE_DIR
from app.core.logging import get_logger
from app.schemas.scanner import ScannedFile
from app.utils.text_utils import is_blank_content

logger = get_logger("services.document_loader")


def load_documents(
    scanned_files: List[ScannedFile], repository_name: str
) -> Tuple[List[Document], int]:
    """
    Converts scanned files into LangChain Documents.

    Returns `(documents, skipped_count)`. Files with blank/whitespace-only
    content are skipped (logged at DEBUG) rather than raising — an empty
    file has nothing meaningful to embed and would only pollute the index.
    Any unexpected per-file error is caught and counted as skipped too,
    so one malformed file never aborts the whole repository's processing.
    """
    repository_path = str((REPOSITORIES_BASE_DIR / repository_name).resolve())
    documents: List[Document] = []
    skipped = 0

    for scanned_file in scanned_files:
        if is_blank_content(scanned_file.content):
            logger.debug("Skipping empty file: %s", scanned_file.relative_path)
            skipped += 1
            continue

        try:
            document = Document(
                page_content=scanned_file.content,
                metadata={
                    "repository_name": repository_name,
                    "repository_path": repository_path,
                    "relative_file_path": scanned_file.relative_path,
                    "absolute_file_path": scanned_file.absolute_path,
                    "language": scanned_file.language,
                    "extension": scanned_file.extension,
                    "file_size": scanned_file.size_bytes,
                    "lines_of_code": scanned_file.line_count,
                },
            )
            documents.append(document)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to build Document for %s | error=%s", scanned_file.relative_path, exc
            )
            skipped += 1

    logger.info(
        "Documents built | repo=%s | created=%d | skipped=%d",
        repository_name,
        len(documents),
        skipped,
    )
    return documents, skipped
