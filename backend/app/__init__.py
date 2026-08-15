"""
RepoGPT AI — Backend Application Package.

This package follows Clean Architecture principles, separated into:
    - api/            → HTTP interface layer (routers, controllers)
    - core/            → App configuration, security, and cross-cutting concerns
    - models/          → SQLAlchemy ORM models (persistence layer)
    - schemas/         → Pydantic request/response DTOs
    - services/         → Business logic (use-cases)
    - repositories/    → Data access abstraction layer
    - rag/             → Retrieval-Augmented Generation pipeline
    - integrations/    → External service adapters (GitHub, Gemini)
    - db/              → Database session & engine management
    - utils/           → Shared helper utilities

Version is tracked here for API versioning / health-check reporting.
"""

__version__ = "0.1.0"
