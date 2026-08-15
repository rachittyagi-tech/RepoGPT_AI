"""
app/prompts/rag_prompt.py

The professional RAG prompt template used to assemble the final prompt
context (Step 8's last pipeline stage). Step 9 will send this exact
string to Gemini — this module does NOT call any LLM itself.

Design goals for the template, per the Step 8 spec:
    - Answer only from retrieved repository context
    - Never hallucinate
    - Explicitly say when information is unavailable in the context
    - Cite source files
    - Explain code clearly
    - Summarize architecture when asked
    - Explain functions and classes when asked
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.rag import ConversationTurn, SourceReference

SYSTEM_INSTRUCTIONS = """You are RepoGPT AI, an expert code assistant answering questions about a \
specific GitHub repository. You must follow these rules strictly:

1. Answer ONLY using the information in the "Repository Context" section below. \
Do not use outside knowledge about libraries, frameworks, or general programming \
facts unless it is needed to explain code that IS shown in the context.
2. NEVER invent or guess code, file names, function names, or behavior that is not \
present in the context. If the context does not contain enough information to \
answer confidently, say so explicitly — e.g. "The provided context doesn't show \
how X is implemented."
3. When you reference specific logic, mention the source file it came from (see \
"Available Sources"), e.g. "In `requests/sessions.py`, the `Session` class...".
4. Explain code clearly and at an appropriate depth: describe what it does, why it \
matters, and how it fits into the surrounding architecture when that's visible in \
the context.
5. If asked to summarize architecture, base the summary only on the files/chunks \
present in the context — do not assume components exist that aren't shown.
6. If asked to explain a specific function or class, and its full body isn't in the \
context, explain what IS shown and state plainly that the rest isn't available in \
the retrieved context.
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


def build_prompt(
    question: str,
    context_text: str,
    sources: List[SourceReference],
    conversation_history: Optional[List[ConversationTurn]] = None,
) -> str:
    """
    Assembles the final, ready-to-send prompt: system instructions +
    available sources + retrieved repository context + (optional) prior
    conversation + the current question.

    This is the literal "Final Prompt Context" the Step 8 pipeline
    produces — Step 9 passes this string directly to Gemini.
    """
    conversation_section = _format_conversation(conversation_history or [])
    sources_section = _format_sources(sources)

    sections = [
        SYSTEM_INSTRUCTIONS.strip(),
        "\n---\nAvailable Sources:\n" + sources_section,
        "\n---\nRepository Context:\n" + (context_text.strip() or "(no relevant context retrieved)"),
    ]

    if conversation_section:
        sections.append("\n---\n" + conversation_section)

    sections.append(f"\n---\nCurrent Question:\n{question.strip()}")
    sections.append(
        "\n---\nAnswer the current question following all rules above. If the "
        "context is insufficient, say so clearly instead of guessing."
    )

    return "\n".join(sections)
