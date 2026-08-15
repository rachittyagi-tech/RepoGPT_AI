"""
app/prompts/intelligence_prompts.py

Prompt templates for the AI Code Intelligence Engine (Step 13). Follows
the same structure as `app/prompts/chat_prompt.py` (Step 9) — strict
anti-hallucination system instructions + a formatted "Repository Context"
section built from RAG-retrieved chunks — but every prompt here
additionally instructs Gemini to answer as STRICT JSON matching a
specific shape, so each service can parse the response into its Pydantic
schema instead of freeform Markdown.

`extract_json_payload` is the shared, defensive parser every Step 13
service uses to pull that JSON back out of Gemini's raw text response
(handling ```json fences, leading/trailing prose, etc.), so a single
place owns "what happens when the model doesn't return clean JSON."
"""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional

from app.schemas.rag import RetrievedChunk, SourceReference

_BASE_RULES = """You are RepoGPT AI's Code Intelligence Engine, a precise senior code-review \
assistant. Follow these rules strictly:

1. Base your analysis ONLY on the "Repository Context" below — the actual retrieved code from \
this repository. Do NOT invent file names, functions, classes, or code that isn't shown.
2. If the context doesn't contain enough information for a thorough analysis, say so explicitly \
in your summary rather than fabricating findings to fill space.
3. Every finding MUST reference a real file path that appears in the context (in `file_path`), \
or be left as `null` if it's a repository-wide observation not tied to one file.
4. Respond with STRICT JSON ONLY — no Markdown fences, no prose before or after, no trailing \
commas. The JSON must exactly match the schema described below.
"""


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


def _format_sources(sources: List[SourceReference]) -> str:
    if not sources:
        return "(no sources retrieved)"
    return "\n".join(f"- {src.file_path} (relevance: {src.score:.2f})" for src in sources)


def chunks_to_sources(chunks: List[RetrievedChunk]) -> List[SourceReference]:
    """Converts retrieved chunks into citable `SourceReference`s — every Step 13
    service uses this (instead of `ContextBuilder.build()`, which also builds a
    chat-oriented prompt this module doesn't use) to attach citations to its output."""
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


def _assemble(
    task_instructions: str,
    schema_description: str,
    chunks: List[RetrievedChunk],
    sources: List[SourceReference],
) -> str:
    return "\n".join(
        [
            _BASE_RULES.strip(),
            "\n---\nTask:\n" + task_instructions.strip(),
            "\n---\nRequired JSON schema:\n" + schema_description.strip(),
            "\n---\nAvailable Sources:\n" + _format_sources(sources),
            "\n---\nRepository Context:\n" + _format_context(chunks),
            "\n---\nRespond now with the JSON object only.",
        ]
    )


# ---------------------------------------------------------------------------
# Code Review (+ Code Smell + Clean Code Analysis)
# ---------------------------------------------------------------------------
def build_code_review_prompt(
    chunks: List[RetrievedChunk], sources: List[SourceReference], max_findings: int
) -> str:
    task = f"""Perform a thorough code review of the repository context above. Look for:
- Bug risks (logic errors, edge cases not handled)
- Code smells (long functions, deep nesting, god classes, magic numbers)
- Clean-code violations (poor naming, missing docstrings/comments, duplicated logic)
- Best-practice violations and maintainability concerns
Return at most {max_findings} findings, most important first."""
    schema = """{
  "summary": "2-4 sentence overall assessment",
  "findings": [
    {
      "category": "bug_risk | code_smell | clean_code | best_practice | maintainability",
      "severity": "critical | high | medium | low | info",
      "file_path": "relative/path.py or null",
      "title": "short title",
      "description": "what the issue is and why it matters",
      "suggestion": "concrete fix"
    }
  ]
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# Bug Detection (AI-reasoning half — heuristics run separately, see bug_detection_service.py)
# ---------------------------------------------------------------------------
def build_bug_detection_prompt(
    chunks: List[RetrievedChunk], sources: List[SourceReference], max_findings: int
) -> str:
    task = f"""Look for likely bugs in the repository context above that a static regex scan \
would miss — real logic issues, not style preferences. Focus on:
- Possible bugs (off-by-one, incorrect conditionals, wrong operator, unhandled edge cases)
- Null/None-pointer risks (dereferencing a value that could be null/None without a check)
- Memory leaks (resources opened but not closed/released, growing collections never cleared)
- Exception handling issues (bare except, swallowing exceptions, catching too broadly)
Return at most {max_findings} findings. Do NOT flag unused variables or dead code — those are \
handled separately by static analysis."""
    schema = """{
  "summary": "2-4 sentence overall assessment",
  "findings": [
    {
      "category": "possible_bug | null_pointer_risk | memory_leak | exception_handling",
      "severity": "critical | high | medium | low | info",
      "file_path": "relative/path.py or null",
      "title": "short title",
      "description": "what the bug is and why it matters",
      "suggestion": "concrete fix"
    }
  ]
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# Security Analysis (AI-reasoning half — secret/key regex scan runs separately)
# ---------------------------------------------------------------------------
def build_security_prompt(
    chunks: List[RetrievedChunk], sources: List[SourceReference], max_findings: int
) -> str:
    task = f"""Analyze the repository context above for security vulnerabilities BEYOND hardcoded \
secrets/API keys (those are already detected separately). Focus on:
- SQL injection risk (string-concatenated or f-string-built SQL queries)
- XSS risk (unescaped user input rendered into HTML/templates)
- CSRF risk (state-changing endpoints without CSRF protection)
- Weak authentication (weak password hashing, missing auth checks, hardcoded credentials logic)
- Unsafe file access (path traversal, unsanitized file paths from user input)
Return at most {max_findings} findings."""
    schema = """{
  "summary": "2-4 sentence overall security assessment",
  "risk_level": "critical | high | medium | low | info",
  "findings": [
    {
      "category": "sql_injection | xss | csrf | weak_authentication | unsafe_file_access",
      "severity": "critical | high | medium | low | info",
      "file_path": "relative/path.py or null",
      "title": "short title",
      "description": "what the vulnerability is and how it could be exploited",
      "remediation": "concrete fix"
    }
  ]
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# Performance Analysis (AI-reasoning half — large-file/nested-loop scan runs separately)
# ---------------------------------------------------------------------------
def build_performance_prompt(
    chunks: List[RetrievedChunk], sources: List[SourceReference], max_findings: int
) -> str:
    task = f"""Analyze the repository context above for performance issues. Focus on:
- Repeated computations that could be cached/memoized
- Inefficient algorithms (e.g. O(n^2) where O(n log n) is achievable, linear search over a set)
- Slow database queries (N+1 query patterns, missing pagination on large result sets)
- Generally unoptimized code (unnecessary copies, inefficient string building)
Do NOT flag large files or simple nested loops — those are handled separately by static analysis. \
Return at most {max_findings} findings."""
    schema = """{
  "summary": "2-4 sentence overall performance assessment",
  "findings": [
    {
      "category": "repeated_computation | inefficient_algorithm | slow_query | unoptimized_code",
      "severity": "critical | high | medium | low | info",
      "file_path": "relative/path.py or null",
      "title": "short title",
      "description": "what the issue is and its performance impact",
      "suggestion": "concrete optimization"
    }
  ]
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# Architecture / Repository Summary
# ---------------------------------------------------------------------------
def build_architecture_prompt(
    chunks: List[RetrievedChunk],
    sources: List[SourceReference],
    folder_structure: str,
    language_summary: str,
) -> str:
    task = f"""Explain this repository's architecture based on the context, folder structure, \
and language breakdown below. Identify the main components/layers and what each is responsible \
for, and write a clear architecture summary suitable for a new contributor.

Folder structure (top levels):
{folder_structure}

Language breakdown:
{language_summary}"""
    schema = """{
  "summary": "3-6 sentence high-level architecture summary",
  "components": [
    { "name": "component/layer name", "responsibility": "what it does", "key_files": ["relative/path.py"] }
  ],
  "content_markdown": "A full architecture explanation in Markdown, with headings, suitable to include in documentation."
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# Documentation (API docs / explain function / explain class / explain file / coding standards)
# ---------------------------------------------------------------------------
def build_documentation_prompt(
    mode: str, target: Optional[str], chunks: List[RetrievedChunk], sources: List[SourceReference]
) -> str:
    target_line = f'Target: "{target}"\n' if target else ""
    mode_instructions = {
        "api_docs": "Generate API documentation for every HTTP endpoint/route visible in the "
        "context: method, path, request/response shape, and a short description of what it does.",
        "explain_function": f'Explain the function named "{target}" in detail: purpose, '
        "parameters, return value, side effects, and an illustrative (clearly-marked-as-illustrative) "
        "usage example.",
        "explain_class": f'Explain the class named "{target}" in detail: purpose, key '
        "attributes/methods, and how it's typically used elsewhere in the codebase.",
        "explain_file": f'Explain the file "{target}" in detail: its overall purpose, the key '
        "functions/classes it defines, and how it fits into the rest of the repository.",
        "coding_standards": "Analyze the coding standards/conventions actually used in this "
        "codebase (naming conventions, formatting patterns, docstring style, error-handling style) "
        "and summarize them as a coding standards report a new contributor could follow.",
    }
    task = target_line + mode_instructions.get(mode, mode_instructions["api_docs"])
    schema = """{
  "content_markdown": "The full documentation content in clean Markdown, with headings/code blocks as appropriate."
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# README Generator
# ---------------------------------------------------------------------------
def build_readme_prompt(
    chunks: List[RetrievedChunk],
    sources: List[SourceReference],
    repo_display_name: str,
    language_summary: str,
    detected_entrypoints: str,
    license_name: Optional[str],
    include_badges: bool,
) -> str:
    badge_line = (
        "Include Markdown badges (build/license/language) near the top."
        if include_badges
        else "Do not include any badges."
    )
    license_line = (
        f"State the license as: {license_name}." if license_name else "Omit the license section if unclear."
    )
    task = f"""Write a complete, professional README.md for the repository "{repo_display_name}", \
based ONLY on the context below. Include these sections, in order: Project Overview, Features, \
Installation, Usage, Folder Structure, Architecture, API Endpoints (only if the context shows \
HTTP endpoints — omit the section otherwise), License, Contributing. {badge_line} {license_line}

Language breakdown:
{language_summary}

Likely entry points detected:
{detected_entrypoints}"""
    schema = """{
  "sections_included": ["Project Overview", "Features", "..."],
  "markdown": "The complete README.md content in Markdown."
}"""
    return _assemble(task, schema, chunks, sources)


# ---------------------------------------------------------------------------
# Shared JSON extraction
# ---------------------------------------------------------------------------
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def extract_json_payload(raw_text: str) -> Optional[Any]:
    """
    Defensively pulls a JSON object/array out of an LLM's raw text response.

    Tries, in order: (1) a ```json fenced block, (2) the first
    brace-to-last-brace span in the text, (3) the whole text as-is.
    Returns None (never raises) if nothing parses — callers fall back to
    wrapping the raw text as a single unstructured finding rather than
    failing the whole request.
    """
    if not raw_text or not raw_text.strip():
        return None

    fenced = _JSON_FENCE_RE.search(raw_text)
    candidate = fenced.group(1) if fenced else None

    if candidate is None:
        bare = _BARE_JSON_RE.search(raw_text)
        candidate = bare.group(1) if bare else raw_text.strip()

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
