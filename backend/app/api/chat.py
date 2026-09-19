"""
app/api/chat.py

HTTP layer for the AI Chat Engine.

All chat and conversation operations are scoped to the
authenticated user.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.middleware.rate_limit import rate_limit
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.auth_service import get_current_user
from app.services.chat_service import ChatService, get_chat_service


logger = get_logger("api.chat")

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    dependencies=[Depends(rate_limit("chat", 20, 60))],
)


# ------------------------------------------------------------------
# Normal chat
# ------------------------------------------------------------------

@router.post(
    "",
    response_model=ChatResponse,
    summary="Chat with an indexed repository",
)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Run a normal non-streaming repository chat."""

    return await service.chat(
        repository_name=payload.repository_name,
        message=payload.message,
        user_id=current_user.id,
        conversation_id=payload.conversation_id,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        language=payload.language,
        file_name=payload.file_name,
    )


# ------------------------------------------------------------------
# Streaming chat
# ------------------------------------------------------------------

@router.post(
    "/stream",
    summary="Stream an AI response",
)
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Stream Gemini's response using Server-Sent Events."""

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for text_chunk, metadata in service.chat_stream(
                repository_name=payload.repository_name,
                message=payload.message,
                user_id=current_user.id,
                conversation_id=payload.conversation_id,
                top_k=payload.top_k,
                score_threshold=payload.score_threshold,
                language=payload.language,
                file_name=payload.file_name,
            ):
                if metadata is None:
                    yield (
                        "event: chunk\n"
                        f"data: {json.dumps({'text': text_chunk})}\n\n"
                    )
                else:
                    yield (
                        "event: done\n"
                        f"data: {json.dumps(metadata)}\n\n"
                    )

        except Exception as exc:
            logger.exception(
                "Chat stream failed | user_id=%s",
                current_user.id,
            )

            yield (
                "event: error\n"
                f"data: {json.dumps({'error': str(exc)})}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------
# Conversation history
# ------------------------------------------------------------------

@router.get(
    "/history",
    summary="Get conversation history",
)
async def get_history(
    conversation_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> Dict[str, Any]:
    """Return persisted messages for the authenticated user's conversation."""

    conversation = await service.get_history(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return {
        "success": True,
        "conversation_id": str(conversation.id),
        "repository_name": conversation.repository_name,
        "title": conversation.title,
        "messages": [
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "timestamp": message.created_at,
                "sources": [],
            }
            for message in conversation.messages
        ],
        "message_count": len(conversation.messages),
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


# ------------------------------------------------------------------
# Conversation list
# ------------------------------------------------------------------

@router.get(
    "/conversations",
    summary="List the authenticated user's conversations",
)
async def list_conversations(
    repository_name: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> Dict[str, Any]:
    """Return conversations belonging only to the authenticated user."""

    conversations = await service.list_conversations(
        user_id=current_user.id,
        repository_name=repository_name,
    )

    return {
        "success": True,
        "conversations": [
            {
                "id": str(conversation.id),
                "repository_name": conversation.repository_name,
                "title": conversation.title,
                "message_count": len(conversation.messages),
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            }
            for conversation in conversations
        ],
        "count": len(conversations),
    }


# ------------------------------------------------------------------
# Clear conversation messages
# ------------------------------------------------------------------

@router.delete(
    "/history",
    summary="Clear conversation messages",
)
async def clear_history(
    conversation_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> Dict[str, Any]:
    """Clear messages while keeping the conversation."""

    await service.clear_history(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return {
        "success": True,
        "message": "Conversation history cleared.",
        "conversation_id": conversation_id,
    }


# ------------------------------------------------------------------
# Delete conversation completely
# ------------------------------------------------------------------

@router.delete(
    "/conversations/{conversation_id}",
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> Dict[str, Any]:
    """Permanently delete a conversation owned by the authenticated user."""

    await service.delete_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return {
        "success": True,
        "message": "Conversation deleted.",
        "conversation_id": conversation_id,
    }


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------

@router.get(
    "/models",
    summary="List available chat models",
)
async def list_models(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> Dict[str, Any]:
    """Return configured AI models."""

    return {
        "success": True,
        "models": service.list_models(),
    }