"""
app/core/exceptions.py

Custom exception hierarchy + global FastAPI exception handlers.

Design rationale:
- Services/repositories raise domain-specific exceptions (e.g.
  `ResourceNotFoundError`) instead of HTTPException directly — this keeps
  business logic decoupled from the HTTP layer (Clean Architecture: inner
  layers must not depend on outer/framework layers).
- The API layer never needs try/except boilerplate in every route; a single
  set of global handlers, registered once in `main.py`, translates domain
  exceptions into consistent JSON error responses.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("core.exceptions")


# ---------------------------------------------------------------------------
# Domain exception hierarchy
# ---------------------------------------------------------------------------
class AppError(Exception):
    """Base class for all application (domain-level) errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred.", **details: Any) -> None:
        self.message = message
        self.details: Dict[str, Any] = details
        super().__init__(message)


class ResourceNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "resource_not_found"

    def __init__(self, resource: str = "Resource", identifier: Optional[Any] = None) -> None:
        message = f"{resource} not found" + (f" (id={identifier})" if identifier else "")
        super().__init__(message, resource=resource, identifier=identifier)


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"

    def __init__(self, message: str = "You do not have access to this resource.") -> None:
        super().__init__(message)


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class ExternalServiceError(AppError):
    """Raised when a downstream dependency (DB, Redis, future GitHub/Gemini calls) fails."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "external_service_error"


# ---------------------------------------------------------------------------
# GitHub Repository Module exceptions (Step 3)
# All of these reuse the existing AppError hierarchy above, so they are
# automatically caught by `app_error_handler` — no new handler registration
# needed. Each just narrows the status_code/error_code/message for its case.
# ---------------------------------------------------------------------------
class InvalidGitHubURLError(ValidationAppError):
    """Raised when the supplied URL is not a well-formed public GitHub repo URL."""

    error_code = "invalid_github_url"

    def __init__(self, url: str, reason: str = "URL is not a valid GitHub repository URL.") -> None:
        super().__init__(reason, url=url)


class RepositoryAlreadyExistsError(ConflictError):
    """Raised by /clone when the repo is already cloned (client should call /update instead)."""

    error_code = "repository_already_exists"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"Repository '{repository_name}' already exists locally. Use the update endpoint instead.",
            repository_name=repository_name,
        )


class RepositoryNotFoundError(ResourceNotFoundError):
    """Raised when a requested local repository folder does not exist."""

    def __init__(self, repository_name: str) -> None:
        super().__init__(resource="Repository", identifier=repository_name)


class PrivateRepositoryAccessError(ForbiddenError):
    """Raised when Git reports an authentication failure (repo is private or access is denied)."""

    error_code = "private_repository_access_denied"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"'{repository_name}' appears to be a private repository or access was denied. "
            "RepoGPT AI currently supports public repositories only."
        )


class GitNetworkError(ExternalServiceError):
    """Raised when a git operation fails due to network/connectivity issues."""

    error_code = "git_network_error"

    def __init__(self, message: str = "Network error while communicating with GitHub.") -> None:
        super().__init__(message)


class GitCloneError(ExternalServiceError):
    """Raised when `git clone` fails for a reason other than auth/network (e.g. repo missing)."""

    error_code = "git_clone_failed"

    def __init__(self, repository_name: str, reason: str) -> None:
        super().__init__(
            f"Failed to clone repository '{repository_name}': {reason}",
            repository_name=repository_name,
        )


class GitPullError(ExternalServiceError):
    """Raised when `git pull` fails on an existing local repository."""

    error_code = "git_pull_failed"

    def __init__(self, repository_name: str, reason: str) -> None:
        super().__init__(
            f"Failed to update repository '{repository_name}': {reason}",
            repository_name=repository_name,
        )


# ---------------------------------------------------------------------------
# Repository Scanner & File Processing exceptions (Step 4)
# ---------------------------------------------------------------------------
class RepositoryPathNotFoundError(ResourceNotFoundError):
    """Raised when the scanner is asked to scan a repository that isn't cloned locally."""

    def __init__(self, repository_name: str) -> None:
        super().__init__(resource="Repository", identifier=repository_name)


class ScanNotPerformedError(AppError):
    """
    Raised by GET /files and GET /statistics when a repository has never been
    scanned (no cached scan result exists yet) — client should call
    POST /api/scanner/scan first.
    """

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "scan_not_performed"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"Repository '{repository_name}' has not been scanned yet. "
            "Call POST /api/scanner/scan first.",
            repository_name=repository_name,
        )


class ScanFailedError(AppError):
    """Raised when the filesystem scan itself fails unexpectedly (permissions, I/O errors, etc.)."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "scan_failed"

    def __init__(self, repository_name: str, reason: str) -> None:
        super().__init__(
            f"Failed to scan repository '{repository_name}': {reason}",
            repository_name=repository_name,
        )


# ---------------------------------------------------------------------------
# Code Processing Pipeline exceptions (Step 5)
# ---------------------------------------------------------------------------
class NoScannedFilesError(AppError):
    """Raised when /chunking/process is called for a repository with zero scanned files."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "no_scanned_files"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"Repository '{repository_name}' has no scanned files to process. "
            "Call POST /api/scanner/scan first.",
            repository_name=repository_name,
        )


class ChunkingNotPerformedError(AppError):
    """
    Raised by GET /chunking/statistics and GET /chunking/chunks when a
    repository has never been processed — client should call
    POST /api/chunking/process first.
    """

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "chunking_not_performed"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"Repository '{repository_name}' has not been processed yet. "
            "Call POST /api/chunking/process first.",
            repository_name=repository_name,
        )


class ChunkingFailedError(AppError):
    """Raised when document loading or splitting fails unexpectedly for a file/repository."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "chunking_failed"

    def __init__(self, repository_name: str, reason: str) -> None:
        super().__init__(
            f"Failed to process repository '{repository_name}': {reason}",
            repository_name=repository_name,
        )


# ---------------------------------------------------------------------------
# Embedding Generation Layer exceptions (Step 6)
# ---------------------------------------------------------------------------
class InvalidEmbeddingProviderError(ValidationAppError):
    """Raised when an unknown provider name is requested (not in the provider registry)."""

    error_code = "invalid_embedding_provider"

    def __init__(self, provider: str, available: list) -> None:
        super().__init__(
            f"Unknown embedding provider '{provider}'. Available: {', '.join(available)}.",
            provider=provider,
            available=available,
        )


class EmbeddingProviderNotConfiguredError(AppError):
    """Raised when the selected provider is missing required config (e.g. API key)."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "embedding_provider_not_configured"

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(
            f"Embedding provider '{provider}' is not configured: {reason}",
            provider=provider,
        )


class NoDocumentsToEmbedError(AppError):
    """Raised by /embeddings/generate when the repository has no chunks to embed."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "no_documents_to_embed"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"Repository '{repository_name}' has no chunks to embed. "
            "Call POST /api/chunking/process first.",
            repository_name=repository_name,
        )


class EmbeddingAuthError(AppError):
    """Raised when a provider rejects the request due to an invalid/missing API key."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "embedding_auth_error"

    def __init__(self, provider: str) -> None:
        super().__init__(f"Authentication with '{provider}' failed — check the configured API key.")


class EmbeddingRateLimitError(AppError):
    """Raised when a provider reports rate limiting/quota exhaustion."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "embedding_rate_limited"

    def __init__(self, provider: str) -> None:
        super().__init__(f"'{provider}' rate limit exceeded. Please retry later.")


class EmbeddingTimeoutError(AppError):
    """Raised when a provider call exceeds the configured TIMEOUT, even after retries."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "embedding_timeout"

    def __init__(self, provider: str, timeout_seconds: int) -> None:
        super().__init__(f"'{provider}' did not respond within {timeout_seconds}s.")


class EmbeddingProviderError(AppError):
    """Generic catch-all for provider failures not otherwise classified."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "embedding_provider_error"

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"'{provider}' failed to generate embeddings: {reason}")


class EmbeddingsNotGeneratedError(AppError):
    """
    Raised when a later step (e.g. Step 7's vector indexing) needs a
    repository's embeddings but POST /api/embeddings/generate was never run.
    """

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "embeddings_not_generated"

    def __init__(self, repository_name: str) -> None:
        super().__init__(
            f"No embeddings found for repository '{repository_name}'. "
            "Call POST /api/embeddings/generate first.",
            repository_name=repository_name,
        )


# ---------------------------------------------------------------------------
# ChromaDB Vector Store Layer exceptions (Step 7)
# ---------------------------------------------------------------------------
class CollectionNotFoundError(ResourceNotFoundError):
    """Raised when searching/updating/deleting/inspecting a collection that doesn't exist."""

    def __init__(self, collection_name: str) -> None:
        super().__init__(resource="Vector collection", identifier=collection_name)


class DuplicateCollectionError(ConflictError):
    """Raised when explicitly creating a collection that already exists (exist_ok=False)."""

    error_code = "duplicate_collection"

    def __init__(self, collection_name: str) -> None:
        super().__init__(
            f"Collection '{collection_name}' already exists.",
            collection_name=collection_name,
        )


class InvalidEmbeddingError(ValidationAppError):
    """Raised when a vector is empty, non-numeric, or otherwise malformed."""

    error_code = "invalid_embedding"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid embedding vector: {reason}")


class DimensionMismatchError(ValidationAppError):
    """Raised when a vector's length doesn't match the collection's recorded dimension."""

    error_code = "dimension_mismatch"

    def __init__(self, collection_name: str, expected: int, actual: int) -> None:
        super().__init__(
            f"Dimension mismatch for collection '{collection_name}': "
            f"expected {expected}, got {actual}.",
            collection_name=collection_name,
            expected=expected,
            actual=actual,
        )


class EmptyCollectionError(AppError):
    """Raised when a similarity search is attempted against a collection with zero vectors."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "empty_collection"

    def __init__(self, collection_name: str) -> None:
        super().__init__(
            f"Collection '{collection_name}' has no vectors to search. "
            "Call POST /api/vector/index first.",
            collection_name=collection_name,
        )


class VectorSearchFailedError(ExternalServiceError):
    """Raised when the underlying ChromaDB query call fails unexpectedly."""

    error_code = "vector_search_failed"

    def __init__(self, collection_name: str, reason: str) -> None:
        super().__init__(f"Search failed for collection '{collection_name}': {reason}")


class VectorPersistenceError(ExternalServiceError):
    """Raised when ChromaDB fails to persist inserts/updates/deletes to disk."""

    error_code = "vector_persistence_failed"

    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(f"Vector store {operation} failed: {reason}")


# ---------------------------------------------------------------------------
# RAG Pipeline exceptions (Step 8)
# ---------------------------------------------------------------------------
class InvalidQueryError(ValidationAppError):
    """Raised when a user's question is empty, too short, or too long."""

    error_code = "invalid_query"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid question: {reason}")


class NoRelevantChunksError(AppError):
    """Raised when retrieval succeeds but nothing scores above the similarity threshold."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "no_relevant_chunks"

    def __init__(self, repository_name: str, threshold: float) -> None:
        super().__init__(
            f"No chunks in '{repository_name}' scored above the similarity "
            f"threshold ({threshold}). Try lowering it or rephrasing the question.",
            repository_name=repository_name,
            threshold=threshold,
        )


class TokenLimitExceededError(AppError):
    """Raised when even the question alone exceeds the configured context token budget."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "token_limit_exceeded"

    def __init__(self, estimated_tokens: int, max_tokens: int) -> None:
        super().__init__(
            f"Question alone is ~{estimated_tokens} tokens, exceeding the "
            f"context budget of {max_tokens} tokens. Please shorten it.",
            estimated_tokens=estimated_tokens,
            max_tokens=max_tokens,
        )


class RAGProcessingError(AppError):
    """Generic catch-all for unexpected failures anywhere in the RAG pipeline."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "rag_processing_failed"

    def __init__(self, reason: str) -> None:
        super().__init__(f"RAG pipeline failed: {reason}")


# ---------------------------------------------------------------------------
# AI Chat Engine exceptions (Step 9)
# ---------------------------------------------------------------------------
class InvalidChatRequestError(ValidationAppError):
    """Raised when a chat message is empty or otherwise malformed."""

    error_code = "invalid_chat_request"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid chat request: {reason}")


class ConversationNotFoundError(ResourceNotFoundError):
    """Raised when a conversation_id doesn't exist (history/reset on an unknown conversation)."""

    def __init__(self, conversation_id: str) -> None:
        super().__init__(resource="Conversation", identifier=conversation_id)


class ChatProviderNotConfiguredError(AppError):
    """Raised when the chat LLM provider is missing required config (e.g. GEMINI_API_KEY)."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "chat_provider_not_configured"

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"Chat provider '{provider}' is not configured: {reason}")


class ChatProviderAuthError(AppError):
    """Raised when the LLM provider rejects the request due to an invalid/missing API key."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "chat_auth_error"

    def __init__(self, provider: str) -> None:
        super().__init__(f"Authentication with '{provider}' failed — check the configured API key.")


class ChatRateLimitError(AppError):
    """Raised when the LLM provider reports rate limiting/quota exhaustion."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "chat_rate_limited"

    def __init__(self, provider: str) -> None:
        super().__init__(f"'{provider}' rate limit exceeded. Please retry later.")


class ChatTimeoutError(AppError):
    """Raised when the LLM provider call exceeds the configured REQUEST_TIMEOUT, even after retries."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "chat_timeout"

    def __init__(self, provider: str, timeout_seconds: int) -> None:
        super().__init__(f"'{provider}' did not respond within {timeout_seconds}s.")


class ChatProviderError(AppError):
    """Generic catch-all for LLM provider failures not otherwise classified."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "chat_provider_error"

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"'{provider}' failed to generate a response: {reason}")


# ---------------------------------------------------------------------------
# Authentication & User Management exceptions (Step 11)
# ---------------------------------------------------------------------------
class DuplicateEmailError(ConflictError):
    """Raised by /register when the email is already registered."""

    error_code = "duplicate_email"

    def __init__(self, email: str) -> None:
        super().__init__(f"An account with email '{email}' already exists.", email=email)


class DuplicateUsernameError(ConflictError):
    """Raised by /register when the username is already taken."""

    error_code = "duplicate_username"

    def __init__(self, username: str) -> None:
        super().__init__(f"Username '{username}' is already taken.", username=username)


class InvalidCredentialsError(UnauthorizedError):
    """Raised by /login on a wrong username/email or password.

    Deliberately generic (never reveals *which* of the two was wrong) to
    avoid leaking whether an email/username is registered (user enumeration).
    """

    error_code = "invalid_credentials"

    def __init__(self) -> None:
        super().__init__("Invalid username/email or password.")


class TokenExpiredError(UnauthorizedError):
    error_code = "token_expired"

    def __init__(self, token_type: str = "token") -> None:
        super().__init__(f"The provided {token_type} has expired.")


class InvalidTokenError(UnauthorizedError):
    error_code = "invalid_token"

    def __init__(self, reason: str = "The provided token is invalid.") -> None:
        super().__init__(reason)


class TokenRevokedError(UnauthorizedError):
    error_code = "token_revoked"

    def __init__(self) -> None:
        super().__init__("This refresh token has been revoked. Please log in again.")


class InactiveUserError(ForbiddenError):
    error_code = "inactive_user"

    def __init__(self) -> None:
        super().__init__("This account has been deactivated. Contact support to reactivate it.")


class UnverifiedEmailError(ForbiddenError):
    error_code = "unverified_email"

    def __init__(self) -> None:
        super().__init__("Please verify your email address before continuing.")


class UserNotFoundError(ResourceNotFoundError):
    def __init__(self, identifier: Optional[Any] = None) -> None:
        super().__init__(resource="User", identifier=identifier)


class IncorrectPasswordError(UnauthorizedError):
    error_code = "incorrect_password"

    def __init__(self) -> None:
        super().__init__("The current password you entered is incorrect.")


class InsufficientRoleError(ForbiddenError):
    """Raised by RBAC dependencies when the user's role lacks permission."""

    error_code = "insufficient_role"

    def __init__(self, required_roles: Optional[list] = None) -> None:
        roles_str = ", ".join(required_roles) if required_roles else "a higher privilege level"
        super().__init__(f"This action requires role: {roles_str}.")


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------
def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {},
            },
            "request_id": request_id,
            "path": str(request.url.path),
        },
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "Handled AppError: %s | code=%s | path=%s",
        exc.message,
        exc.error_code,
        request.url.path,
    )
    return _error_response(request, exc.status_code, exc.error_code, exc.message, exc.details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning("HTTPException: %s | path=%s", exc.detail, request.url.path)
    return _error_response(
        request,
        exc.status_code,
        "http_error",
        str(exc.detail),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "Request validation failed.",
        {"errors": exc.errors()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "An unexpected error occurred. Please try again later.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers all global exception handlers on the FastAPI app instance."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
