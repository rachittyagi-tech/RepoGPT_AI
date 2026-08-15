"""
app/services/conversation_service.py

Manages conversation state for the AI Chat Engine (Step 9): creating
conversations, appending messages, retrieving/clearing history, and
repository switching within an existing conversation.

Storage: in-memory, process-wide (class-level dict), same pattern as
Scanner/Chunking/Embedding services' caches. Conversations do NOT survive
a server restart — acceptable for this step; a persistent store (Redis/
Postgres) would be a natural follow-up, not required here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar, Dict, List, Optional

from app.core.exceptions import ConversationNotFoundError
from app.core.logging import get_logger
from app.schemas.chat import ChatMessage, ChatRole
from app.schemas.rag import ConversationTurn, SourceReference

logger = get_logger("services.conversation")

# Only the most recent N user/assistant turns are handed to the RAG
# pipeline as conversation context — keeps prompt size bounded regardless
# of how long a conversation has run (Step 8's own token budget is the
# hard limit, this just avoids handing it an ever-growing list).
_MAX_TURNS_FOR_RAG = 6


@dataclass
class Conversation:
    conversation_id: str
    repository_name: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationService:
    """In-memory conversation store: create, append, retrieve, clear, and switch repositories."""

    _CONVERSATIONS: ClassVar[Dict[str, Conversation]] = {}

    def get_or_create(self, conversation_id: Optional[str], repository_name: str) -> Conversation:
        """
        Returns the existing conversation if `conversation_id` is provided
        and exists, otherwise creates a new one (new UUID if
        `conversation_id` is None or unknown).
        """
        if conversation_id and conversation_id in self._CONVERSATIONS:
            return self._CONVERSATIONS[conversation_id]

        new_id = conversation_id or str(uuid.uuid4())
        conversation = Conversation(conversation_id=new_id, repository_name=repository_name)
        self._CONVERSATIONS[new_id] = conversation
        logger.info("Created new conversation | id=%s | repo=%s", new_id, repository_name)
        return conversation

    def get(self, conversation_id: str) -> Conversation:
        """Raises `ConversationNotFoundError` if `conversation_id` doesn't exist."""
        conversation = self._CONVERSATIONS.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def switch_repository(self, conversation_id: str, new_repository_name: str) -> Conversation:
        """
        "Repository Switching": points an existing conversation at a
        different repository. Prior message history is kept (for
        conversational continuity of phrasing/tone) but new retrieval
        calls will target the new repository's vector collection —
        callers should be aware the assistant's prior answers may
        reference a different codebase than what's now being searched.
        """
        conversation = self.get(conversation_id)
        if conversation.repository_name != new_repository_name:
            logger.info(
                "Switching conversation repository | id=%s | %s -> %s",
                conversation_id,
                conversation.repository_name,
                new_repository_name,
            )
            conversation.repository_name = new_repository_name
            conversation.updated_at = datetime.now(timezone.utc)
        return conversation

    def add_message(
        self,
        conversation_id: str,
        role: ChatRole,
        content: str,
        sources: Optional[List[SourceReference]] = None,
    ) -> ChatMessage:
        conversation = self.get(conversation_id)
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            sources=sources or [],
        )
        conversation.messages.append(message)
        conversation.updated_at = message.timestamp
        return message

    def get_history(self, conversation_id: str) -> Conversation:
        """Raises `ConversationNotFoundError` if `conversation_id` doesn't exist."""
        return self.get(conversation_id)

    def clear_history(self, conversation_id: str) -> None:
        """
        "Conversation Reset": clears a conversation's messages but keeps
        its ID and repository binding — the next message continues under
        the same `conversation_id` with a clean slate.
        """
        conversation = self.get(conversation_id)
        conversation.messages.clear()
        conversation.updated_at = datetime.now(timezone.utc)
        logger.info("Conversation history cleared | id=%s", conversation_id)

    def get_recent_turns_for_rag(self, conversation_id: str) -> List[ConversationTurn]:
        """
        Converts the most recent `_MAX_TURNS_FOR_RAG` messages into Step 8's
        `ConversationTurn` shape for conversation-aware context building.
        Returns an empty list for a brand-new conversation (no error).
        """
        conversation = self._CONVERSATIONS.get(conversation_id)
        if conversation is None or not conversation.messages:
            return []

        recent = conversation.messages[-_MAX_TURNS_FOR_RAG:]
        return [ConversationTurn(role=m.role.value, content=m.content) for m in recent]

    def count_conversations(self, repository_name: Optional[str] = None) -> int:
        """Returns the total number of in-memory conversations, optionally scoped to
        one repository. Used by the Analytics module (Step 12) — read-only, does not
        expose conversation content, only a count."""
        if repository_name is None:
            return len(self._CONVERSATIONS)
        return sum(1 for c in self._CONVERSATIONS.values() if c.repository_name == repository_name)


def get_conversation_service() -> ConversationService:
    """FastAPI dependency provider — see app/services/chat_service.py."""
    return ConversationService()
