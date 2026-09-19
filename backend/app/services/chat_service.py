"""
app/services/chat_service.py

Orchestrates the full AI Chat Engine flow.

Flow:
Validate Request
    -> Get/Create user-owned conversation
    -> Retrieve RAG context
    -> Build prompt
    -> Call Gemini
    -> Save conversation
    -> Return response
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from fastapi import Depends

from app.core.exceptions import InvalidChatRequestError
from app.core.logging import get_logger
from app.prompts.chat_prompt import build_chat_prompt
from app.schemas.chat import ChatResponse, ChatRole
from app.schemas.rag import SourceReference
from app.services.conversation_service import (
    Conversation,
    ConversationService,
    get_conversation_service,
)
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service
from app.services.statistics_service import UsageMetricsRecorder


logger = get_logger("services.chat")


class ChatService:
    """Orchestrates retrieval, generation, citation and persistent chat."""

    def __init__(
        self,
        rag_service: RAGService,
        gemini_service: GeminiService,
        conversation_service: ConversationService,
    ) -> None:
        self.rag_service = rag_service
        self.gemini_service = gemini_service
        self.conversation_service = conversation_service

    # ------------------------------------------------------------------
    # Non-streaming chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        repository_name: str,
        message: str,
        user_id: uuid.UUID,
        conversation_id: Optional[str] = None,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        language: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> ChatResponse:

        start_time = time.perf_counter()

        trimmed_message = self._validate_message(message)

        conversation = await self.conversation_service.get_or_create(
            conversation_id=conversation_id,
            repository_name=repository_name,
            user_id=user_id,
        )

        if conversation.repository_name != repository_name:
            conversation = await self.conversation_service.switch_repository(
                conversation_id=str(conversation.id),
                new_repository_name=repository_name,
                user_id=user_id,
            )

        history_turns = (
            await self.conversation_service.get_recent_turns_for_rag(
                conversation_id=str(conversation.id),
                user_id=user_id,
            )
        )

        _, chunks = await self.rag_service.retrieve(
            repository_name=repository_name,
            question=trimmed_message,
            top_k=top_k,
            score_threshold=score_threshold,
            language=language,
            file_name=file_name,
        )

        sources = self._build_sources(chunks)

        prompt = build_chat_prompt(
            question=trimmed_message,
            chunks=chunks,
            sources=sources,
            conversation_history=history_turns,
        )

        answer, token_usage = await self.gemini_service.generate(prompt)

        await self._save_turn(
            conversation_id=str(conversation.id),
            user_id=user_id,
            user_message=trimmed_message,
            answer=answer,
            sources=sources,
        )

        processing_time = round(
            time.perf_counter() - start_time,
            3,
        )

        logger.info(
            "Chat complete | user_id=%s | repo=%s | conversation=%s | tokens=%d | time=%.3fs",
            user_id,
            repository_name,
            conversation.id,
            token_usage.total_tokens,
            processing_time,
        )

        UsageMetricsRecorder.record_chat_interaction(
            repository_name=repository_name,
            question=trimmed_message,
            processing_time_seconds=processing_time,
            similarity_scores=[c.score for c in chunks],
            token_usage=token_usage,
        )

        return ChatResponse(
            answer=answer,
            repository_name=repository_name,
            conversation_id=str(conversation.id),
            processing_time_seconds=processing_time,
            token_usage=token_usage,
            sources=sources,
            similarity_scores=[c.score for c in chunks],
            created_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Streaming chat
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        repository_name: str,
        message: str,
        user_id: uuid.UUID,
        conversation_id: Optional[str] = None,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        language: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> AsyncIterator[Tuple[str, Optional[Dict[str, Any]]]]:

        start_time = time.perf_counter()

        trimmed_message = self._validate_message(message)

        conversation = await self.conversation_service.get_or_create(
            conversation_id=conversation_id,
            repository_name=repository_name,
            user_id=user_id,
        )

        if conversation.repository_name != repository_name:
            conversation = await self.conversation_service.switch_repository(
                conversation_id=str(conversation.id),
                new_repository_name=repository_name,
                user_id=user_id,
            )

        history_turns = (
            await self.conversation_service.get_recent_turns_for_rag(
                conversation_id=str(conversation.id),
                user_id=user_id,
            )
        )

        _, chunks = await self.rag_service.retrieve(
            repository_name=repository_name,
            question=trimmed_message,
            top_k=top_k,
            score_threshold=score_threshold,
            language=language,
            file_name=file_name,
        )

        sources = self._build_sources(chunks)

        prompt = build_chat_prompt(
            question=trimmed_message,
            chunks=chunks,
            sources=sources,
            conversation_history=history_turns,
        )

        full_answer_parts: List[str] = []

        async for text_chunk in self.gemini_service.generate_stream(prompt):
            full_answer_parts.append(text_chunk)
            yield text_chunk, None

        full_answer = "".join(full_answer_parts)

        await self._save_turn(
            conversation_id=str(conversation.id),
            user_id=user_id,
            user_message=trimmed_message,
            answer=full_answer,
            sources=sources,
        )

        processing_time = round(
            time.perf_counter() - start_time,
            3,
        )

        logger.info(
            "Chat stream complete | user_id=%s | repo=%s | conversation=%s | time=%.3fs",
            user_id,
            repository_name,
            conversation.id,
            processing_time,
        )

        UsageMetricsRecorder.record_chat_interaction(
            repository_name=repository_name,
            question=trimmed_message,
            processing_time_seconds=processing_time,
            similarity_scores=[c.score for c in chunks],
        )

        metadata: Dict[str, Any] = {
            "repository_name": repository_name,
            "conversation_id": str(conversation.id),
            "processing_time_seconds": processing_time,
            "sources": [
                s.model_dump(mode="json")
                for s in sources
            ],
            "similarity_scores": [
                c.score for c in chunks
            ],
        }

        yield "", metadata

    # ------------------------------------------------------------------
    # History / models
    # ------------------------------------------------------------------

    async def get_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> Conversation:

        return await self.conversation_service.get_history(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def clear_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> None:

        await self.conversation_service.clear_history(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def list_conversations(
        self,
        user_id: uuid.UUID,
        repository_name: Optional[str] = None,
    ) -> List[Conversation]:

        return await self.conversation_service.list_conversations(
            user_id=user_id,
            repository_name=repository_name,
        )

    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> None:

        await self.conversation_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def list_models(self) -> List[Dict[str, Any]]:

        settings = self.gemini_service.settings

        return [
            {
                "name": settings.GEMINI_MODEL,
                "display_name": settings.GEMINI_MODEL.replace(
                    "-",
                    " ",
                ).title(),
                "max_output_tokens": settings.MAX_OUTPUT_TOKENS,
                "status": (
                    "active"
                    if self.gemini_service.is_configured()
                    else "not_configured"
                ),
            }
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_message(message: str) -> str:

        trimmed = (message or "").strip()

        if not trimmed:
            raise InvalidChatRequestError(
                "message cannot be empty."
            )

        return trimmed

    @staticmethod
    def _build_sources(
        chunks: List[Any],
    ) -> List[SourceReference]:

        return [
            SourceReference(
                repository_name=chunk.repository_name,
                file_path=chunk.file_path,
                language=chunk.language,
                chunk_number=chunk.chunk_number,
                total_chunks=chunk.total_chunks,
                score=chunk.score,
            )
            for chunk in chunks
        ]

    async def _save_turn(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
        user_message: str,
        answer: str,
        sources: List[SourceReference],
    ) -> None:
        await self.conversation_service.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=ChatRole.USER,
            content=user_message,
        )

        await self.conversation_service.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=ChatRole.ASSISTANT,
            content=answer,
            sources=sources,
        )

        # Persist both messages immediately.
        # This is important for streaming responses because the
        # StreamingResponse generator continues after the route returns.
        await self.conversation_service.db.commit()

        logger.info(
            "Conversation turn persisted | conversation=%s | user_id=%s",
            conversation_id,
            user_id,
        )


def get_chat_service(
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
    conversation_service: ConversationService = Depends(
        get_conversation_service
    ),
) -> ChatService:

    return ChatService(
        rag_service=rag_service,
        gemini_service=gemini_service,
        conversation_service=conversation_service,
    )