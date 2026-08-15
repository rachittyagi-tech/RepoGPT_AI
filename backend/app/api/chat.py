"""
app/api/chat.py

HTTP layer for the AI Chat Engine module (Step 9).

Thin router — validates input via Pydantic, delegates to `ChatService`,
shapes the response. Error translation (invalid request, repository not
indexed, empty context, Gemini auth/rate-limit/timeout/provider failures)
happens via domain exceptions + the global exception handlers.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ClearHistoryResponse,
    HistoryResponse,
    ModelsResponse,
)
from app.services.chat_service import ChatService, get_chat_service
from app.middleware.rate_limit import rate_limit

logger = get_logger("api.chat")

# Step 15: every chat turn calls Gemini (real cost + latency), so this is
# throttled — 20/min/IP comfortably covers normal back-and-forth
# conversation while limiting runaway/scripted usage. History/list/delete
# reads share the bucket too, kept simple; they're cheap enough that the
# same generous limit doesn't affect normal use.
router = APIRouter(tags=["Chat"], dependencies=[Depends(rate_limit("chat", 20, 60))])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message and get a complete answer (non-streaming)",
)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Runs the full chat flow: retrieve repository context (Step 8 RAG) ->
    build prompt -> call Gemini -> attach citations -> save conversation
    -> return the answer.

    Omit `conversation_id` to start a new conversation; pass one back in
    subsequent calls to continue it (and enable conversation memory).

    Returns 400 for an empty message, 404 if the repository isn't
    indexed or nothing relevant is found, 401/429/504/502 for Gemini
    auth/rate-limit/timeout/provider failures.
    """
    logger.info(
        "Received chat request | repo=%s | conversation=%s",
        payload.repository_name,
        payload.conversation_id or "(new)",
    )
    return await service.chat(
        repository_name=payload.repository_name,
        message=payload.message,
        conversation_id=payload.conversation_id,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        language=payload.language,
        file_name=payload.file_name,
    )


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Send a message and stream the answer as Server-Sent Events",
)
async def chat_stream(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """
    Same flow as POST /api/chat, but streams the answer incrementally as
    it's generated (Server-Sent Events). Each text chunk is sent as:

        event: chunk
        data: {"text": "..."}

    followed by a final event once generation completes:

        event: done
        data: {"conversation_id": "...", "sources": [...], "similarity_scores": [...], ...}

    Or, on failure mid-stream:

        event: error
        data: {"error": {"code": "...", "message": "..."}}
    """
    logger.info(
        "Received chat stream request | repo=%s | conversation=%s",
        payload.repository_name,
        payload.conversation_id or "(new)",
    )

    async def event_generator():
        try:
            async for text_chunk, metadata in service.chat_stream(
                repository_name=payload.repository_name,
                message=payload.message,
                conversation_id=payload.conversation_id,
                top_k=payload.top_k,
                score_threshold=payload.score_threshold,
                language=payload.language,
                file_name=payload.file_name,
            ):
                if metadata is not None:
                    yield f"event: done\ndata: {json.dumps(metadata)}\n\n"
                else:
                    yield f"event: chunk\ndata: {json.dumps({'text': text_chunk})}\n\n"
        except Exception as exc:  # noqa: BLE001
            error_code = getattr(exc, "error_code", "chat_stream_error")
            error_message = getattr(exc, "message", str(exc))
            logger.exception("Chat stream failed: %s", exc)
            yield (
                f"event: error\n"
                f"data: {json.dumps({'error': {'code': error_code, 'message': error_message}})}\n\n"
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    "/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a conversation's full message history",
)
async def get_history(
    conversation_id: str = Query(..., description="The conversation ID returned by a prior chat call."),
    service: ChatService = Depends(get_chat_service),
) -> HistoryResponse:
    """Returns every message (user + assistant, with citations) for `conversation_id`.

    Returns 404 if the conversation doesn't exist.
    """
    conversation = service.get_history(conversation_id)
    return HistoryResponse(
        conversation_id=conversation.conversation_id,
        repository_name=conversation.repository_name,
        messages=conversation.messages,
        message_count=len(conversation.messages),
    )


@router.delete(
    "/history",
    response_model=ClearHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset a conversation (clear its message history)",
)
async def clear_history(
    conversation_id: str = Query(..., description="The conversation to reset."),
    service: ChatService = Depends(get_chat_service),
) -> ClearHistoryResponse:
    """Clears `conversation_id`'s messages — the ID remains valid for continued use.

    Returns 404 if the conversation doesn't exist.
    """
    service.clear_history(conversation_id)
    return ClearHistoryResponse(
        message=f"Conversation '{conversation_id}' history cleared.",
        conversation_id=conversation_id,
    )


@router.get(
    "/models",
    response_model=ModelsResponse,
    status_code=status.HTTP_200_OK,
    summary="List available chat models and their configuration status",
)
async def list_models(
    service: ChatService = Depends(get_chat_service),
) -> ModelsResponse:
    """Returns the currently configured Gemini model and its readiness."""
    models = service.list_models()
    return ModelsResponse(active_model=models[0]["name"], models=models)
