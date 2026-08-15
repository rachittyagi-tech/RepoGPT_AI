"""
app/prompts/chat_prompt.py

The professional system prompt for the AI Chat Engine (Step 9) — the
actual prompt sent to Gemini. Builds on Step 8's anti-hallucination rules
but adds chat-specific requirements: Markdown formatting, generating
examples, and explaining APIs — since this prompt's output is rendered
directly to an end user in a chat UI, not consumed as raw RAG context.
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.rag import ConversationTurn, RetrievedChunk, SourceReference

SYSTEM_INSTRUCTIONS = """You are RepoGPT AI, a friendly and precise expert assistant that helps \
developers understand a specific GitHub repository through chat. Follow these rules strictly:

1. Answer ONLY using the information in the "Repository Context" section below, plus the \
ongoing conversation. Do not rely on outside knowledge about a library or framework unless \
it's needed to explain code that IS shown in the context.
2. NEVER invent or guess code, file names, function signatures, or behavior that isn't present \
in the context. If the context doesn't contain enough information, say so plainly — e.g. \
"I don't see that in the retrieved context from this repository."
3. Cite the source file(s) you're drawing from inline, e.g. "In `requests/sessions.py`...". \
Use the "Available Sources" list below for exact file paths.
4. Format your answer in clean Markdown: use headings, bullet points, and fenced code blocks \
(```python, ```javascript, etc.) where appropriate — your response is rendered directly in a chat UI.
5. When explaining architecture, functions, classes, or APIs, be concrete: describe what each \
piece does, its parameters/return values if shown, and how it fits into the broader system.
6. When it would help understanding, generate a short illustrative usage example based on the \
context (e.g. how a function shown in the context might be called) — but do NOT present a \
generated example as if it were verbatim code found in the repository; make clear it's illustrative.
7. Keep answers focused and readable — prefer a well-structured shorter answer over a rambling long one.
"""


def _format_conversation(history: List[ConversationTurn]) -> str:
    if not history:
        return ""
    lines = ["Conversation so far:"]
    for turn in history:
        speaker = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.content}")
    return "\n".join(lines)


def _format_sources(sources: List[SourceReference]) -> str:
    if not sources:
        return "(no sources retrieved)"
    lines = []
    for src in sources:
        lines.append(
            f"- {src.file_path} (repository: {src.repository_name}, "
            f"language: {src.language}, chunk {src.chunk_number}/{src.total_chunks}, "
            f"relevance: {src.score:.2f})"
        )
    return "\n".join(lines)


def _format_context(chunks: List[RetrievedChunk]) -> str:
    if not chunks:
        return "(no relevant context retrieved)"
    parts = []
    for chunk in chunks:
        parts.append(
            f"[Source: {chunk.file_path} | {chunk.language} | "
            f"chunk {chunk.chunk_number}/{chunk.total_chunks}]\n{chunk.content}"
        )
    return "\n\n".join(parts)


def build_chat_prompt(
    question: str,
    chunks: List[RetrievedChunk],
    sources: List[SourceReference],
    conversation_history: Optional[List[ConversationTurn]] = None,
) -> str:
    """
    Assembles the final prompt actually sent to Gemini: system
    instructions + available sources + repository context + conversation
    history + the current question.
    """
    conversation_section = _format_conversation(conversation_history or [])
    sources_section = _format_sources(sources)
    context_section = _format_context(chunks)

    sections = [
        SYSTEM_INSTRUCTIONS.strip(),
        "\n---\nAvailable Sources:\n" + sources_section,
        "\n---\nRepository Context:\n" + context_section,
    ]

    if conversation_section:
        sections.append("\n---\n" + conversation_section)

    sections.append(f"\n---\nCurrent Question:\n{question.strip()}")
    sections.append(
        "\n---\nRespond to the current question now, in Markdown, following all rules above."
    )

    return "\n".join(sections)
