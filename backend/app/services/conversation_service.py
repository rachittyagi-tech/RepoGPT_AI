"""
app/services/conversation_service.py

Persistent PostgreSQL-backed conversation storage for RepoGPT AI.

Responsibilities:
- Create and retrieve conversations
- Keep conversations isolated per authenticated user
- Store user/assistant messages permanently
- Persist source references with messages
- Retrieve recent conversation turns for RAG
- Clear conversation history
- Switch repository within a conversation
- Count conversations for analytics
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError
from app.core.logging import get_logger
from app.database.session import get_db
from app.models.conversation import Conversation, ConversationMessage
from app.schemas.chat import ChatMessage, ChatRole
from app.schemas.rag import ConversationTurn, SourceReference


logger = get_logger("services.conversation")

_MAX_TURNS_FOR_RAG = 6


class ConversationService:
    """PostgreSQL-backed conversation service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create(
        self,
        conversation_id: Optional[str],
        repository_name: str,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Return an existing user-owned conversation or create a new one."""

        if conversation_id:
            try:
                conversation_uuid = uuid.UUID(conversation_id)
            except ValueError:
                raise ConversationNotFoundError(conversation_id)

            result = await self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_uuid,
                    Conversation.user_id == user_id,
                )
            )

            conversation = result.scalar_one_or_none()

            if conversation is None:
                raise ConversationNotFoundError(conversation_id)

            return conversation

        conversation = Conversation(
            user_id=user_id,
            repository_name=repository_name,
            title=None,
        )

        self.db.add(conversation)
        await self.db.flush()

        logger.info(
            "Created new conversation | id=%s | user_id=%s | repo=%s",
            conversation.id,
            user_id,
            repository_name,
        )

        return conversation

    async def get(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Return a conversation owned by the authenticated user."""

        try:
            conversation_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise ConversationNotFoundError(conversation_id)

        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_uuid,
                Conversation.user_id == user_id,
            )
        )

        conversation = result.scalar_one_or_none()

        if conversation is None:
            raise ConversationNotFoundError(conversation_id)

        return conversation

    async def switch_repository(
        self,
        conversation_id: str,
        new_repository_name: str,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Switch repository while preserving the conversation."""

        conversation = await self.get(
            conversation_id,
            user_id,
        )

        if conversation.repository_name != new_repository_name:
            logger.info(
                "Switching conversation repository | id=%s | %s -> %s",
                conversation_id,
                conversation.repository_name,
                new_repository_name,
            )

            conversation.repository_name = new_repository_name
            conversation.updated_at = datetime.now(timezone.utc)

            await self.db.flush()

        return conversation

    async def add_message(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
        role: ChatRole,
        content: str,
        sources: Optional[List[SourceReference]] = None,
    ) -> ChatMessage:
        """
        Persist a conversation message.

        Source references are stored permanently in PostgreSQL as JSONB.
        """

        conversation = await self.get(
            conversation_id,
            user_id,
        )

        # Set the conversation title from the first user message.
        if (
            role == ChatRole.USER
            and not conversation.title
            and content.strip()
        ):
            title = " ".join(content.strip().split())

            if len(title) > 60:
                title = title[:57].rstrip() + "..."

            conversation.title = title

        serialized_sources = []

        for source in sources or []:
            if hasattr(source, "model_dump"):
                serialized_sources.append(source.model_dump())
            elif hasattr(source, "dict"):
                serialized_sources.append(source.dict())
            elif isinstance(source, dict):
                serialized_sources.append(source)
            else:
                serialized_sources.append(dict(source))

        message = ConversationMessage(
            conversation_id=conversation.id,
            role=role.value,
            content=content,
            sources=serialized_sources,
        )

        self.db.add(message)

        conversation.updated_at = datetime.now(timezone.utc)

        await self.db.flush()

        return ChatMessage(
            role=role,
            content=content,
            timestamp=message.created_at,
            sources=sources or [],
        )

    async def get_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Return conversation and its persisted messages."""

        conversation = await self.get(
            conversation_id,
            user_id,
        )

        await self.db.refresh(
            conversation,
            attribute_names=["messages"],
        )

        return conversation

    async def clear_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> None:
        """Delete all messages while keeping the conversation."""

        conversation = await self.get(
            conversation_id,
            user_id,
        )

        await self.db.refresh(
            conversation,
            attribute_names=["messages"],
        )

        for message in list(conversation.messages):
            await self.db.delete(message)

        conversation.updated_at = datetime.now(timezone.utc)

        await self.db.flush()

        logger.info(
            "Conversation history cleared | id=%s | user_id=%s",
            conversation_id,
            user_id,
        )

    async def get_recent_turns_for_rag(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> List[ConversationTurn]:
        """Return the most recent messages for conversation-aware RAG."""

        conversation = await self.get(
            conversation_id,
            user_id,
        )

        await self.db.refresh(
            conversation,
            attribute_names=["messages"],
        )

        if not conversation.messages:
            return []

        recent_messages = conversation.messages[-_MAX_TURNS_FOR_RAG:]

        return [
            ConversationTurn(
                role=message.role,
                content=message.content,
            )
            for message in recent_messages
        ]

    async def list_conversations(
        self,
        user_id: uuid.UUID,
        repository_name: Optional[str] = None,
    ) -> List[Conversation]:
        """List conversations belonging only to the authenticated user."""

        query = select(Conversation).where(
            Conversation.user_id == user_id
        )

        if repository_name:
            query = query.where(
                Conversation.repository_name == repository_name
            )

        query = query.order_by(
            Conversation.updated_at.desc()
        )

        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
    ) -> None:
        """Permanently delete a conversation owned by the user."""

        conversation = await self.get(
            conversation_id,
            user_id,
        )

        await self.db.delete(conversation)
        await self.db.flush()

        logger.info(
            "Conversation deleted | id=%s | user_id=%s",
            conversation_id,
            user_id,
        )

    async def count_conversations(
        self,
        user_id: Optional[uuid.UUID] = None,
        repository_name: Optional[str] = None,
    ) -> int:
        """Count conversations, optionally scoped to user/repository."""

        query = select(
            func.count(Conversation.id)
        )

        if user_id is not None:
            query = query.where(
                Conversation.user_id == user_id
            )

        if repository_name is not None:
            query = query.where(
                Conversation.repository_name == repository_name
            )

        result = await self.db.execute(query)

        return int(result.scalar_one())


def get_conversation_service(
    db: AsyncSession = Depends(get_db),
) -> ConversationService:
    """FastAPI dependency provider."""

    return ConversationService(db)
