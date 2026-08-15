"""
app/services/bug_detection_service.py

Bug Detection (Step 13) — two detection methods, merged into one response:

    1. HEURISTIC (deterministic regex/static-analysis over Scanner's
       already-cached files, Step 4): unused variables, dead code,
       duplicate code, bare/broad exception handling. Zero hallucination
       risk — these are mechanically detectable, so an LLM is never
       asked to "guess" at them.
    2. AI (Gemini reasoning over RAG-retrieved context, Step 8): possible
       bugs, null/None-pointer risks, and memory leaks — genuinely
       requires understanding intent, which regex can't do.

Every finding's `detection_method` field tells the caller which kind it is.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends

from app.core.exceptions import ScanNotPerformedError
from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_bug_detection_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import BugCategory, BugDetectionRequest, BugDetectionResponse, BugFinding, DetectionMethod, Severity
from app.schemas.scanner import ScannedFile
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service
from app.services.scanner_service import ScannerService, get_scanner_service

logger = get_logger("services.bug_detection")

_RETRIEVAL_TOP_K = 12
_MAX_HEURISTIC_FINDINGS = 25

# Languages where a simple "assigned but never referenced again" heuristic
# is reasonably reliable (single-assignment scripting/OOP languages).
# Skipped for languages with heavy destructuring/pattern-matching idioms
# where the heuristic would be too noisy to be useful.
_UNUSED_VAR_LANGUAGES = {"Python", "JavaScript", "TypeScript", "Java", "Go", "C#"}

_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^=]")
_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$")
_BROAD_EXCEPT_RE = re.compile(r"^\s*except\s+Exception\s*(as\s+\w+)?\s*:\s*$")
_TODO_DEAD_CODE_RE = re.compile(r"#\s*(TODO|FIXME|XXX|DEAD CODE|UNREACHABLE)", re.IGNORECASE)
_COMMENTED_CODE_RE = re.compile(r"^\s*#\s*(def |class |if |for |while |return |import )")

_PYTHON_KEYWORDS = {
    "self", "cls", "true", "false", "none", "and", "or", "not", "if", "else", "elif",
    "for", "while", "return", "yield", "import", "from", "as", "with", "try", "except",
    "finally", "def", "class", "pass", "break", "continue", "lambda", "in", "is",
}


class BugDetectionService:
    def __init__(self, scanner_service: ScannerService, rag_service: RAGService, gemini_service: GeminiService) -> None:
        self.scanner_service = scanner_service
        self.rag_service = rag_service
        self.gemini_service = gemini_service

    async def detect(self, request: BugDetectionRequest) -> BugDetectionResponse:
        heuristic_findings = self._run_heuristics(request.repository_name, request.focus_path)

        query = (
            f"possible bugs, null checks, and error handling in {request.focus_path}"
            if request.focus_path
            else "possible bugs, null/None handling, resource management, and error handling"
        )
        _, chunks = await self.rag_service.retrieve(
            repository_name=request.repository_name,
            question=query,
            top_k=_RETRIEVAL_TOP_K,
            language=request.language,
            file_name=request.focus_path,
        )
        sources = chunks_to_sources(chunks)

        remaining_budget = max(request.max_findings - len(heuristic_findings), 3)
        prompt = build_bug_detection_prompt(chunks, sources, remaining_budget)
        raw_text, _usage = await self.gemini_service.generate(prompt)
        ai_findings = self._parse_ai_findings(raw_text, remaining_budget)

        all_findings = (heuristic_findings + ai_findings)[: request.max_findings]
        summary = self._build_summary(heuristic_findings, ai_findings)

        logger.info(
            "Bug detection complete | repo=%s | heuristic=%d | ai=%d",
            request.repository_name,
            len(heuristic_findings),
            len(ai_findings),
        )

        return BugDetectionResponse(
            repository_name=request.repository_name,
            summary=summary,
            findings=all_findings,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Heuristic (deterministic) detection
    # ------------------------------------------------------------------
    def _run_heuristics(self, repository_name: str, focus_path: Optional[str]) -> List[BugFinding]:
        try:
            files = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            return []

        if focus_path:
            files = [f for f in files if f.relative_path == focus_path]

        findings: List[BugFinding] = []
        findings.extend(self._detect_exception_issues(files))
        findings.extend(self._detect_dead_code(files))
        findings.extend(self._detect_unused_variables(files))
        findings.extend(self._detect_duplicate_code(files))
        return findings[:_MAX_HEURISTIC_FINDINGS]

    @staticmethod
    def _detect_exception_issues(files: List[ScannedFile]) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for f in files:
            if f.language != "Python" or not f.content:
                continue
            for line_no, line in enumerate(f.content.splitlines(), start=1):
                if _BARE_EXCEPT_RE.match(line):
                    findings.append(
                        BugFinding(
                            category=BugCategory.EXCEPTION_HANDLING,
                            severity=Severity.MEDIUM,
                            detection_method=DetectionMethod.HEURISTIC,
                            file_path=f.relative_path,
                            line_hint=line_no,
                            title="Bare `except:` clause",
                            description="Catches every exception, including SystemExit/KeyboardInterrupt, "
                            "which can hide real bugs and make the program hard to interrupt.",
                            suggestion="Catch a specific exception type, or at least `except Exception:`.",
                        )
                    )
                elif _BROAD_EXCEPT_RE.match(line):
                    findings.append(
                        BugFinding(
                            category=BugCategory.EXCEPTION_HANDLING,
                            severity=Severity.LOW,
                            detection_method=DetectionMethod.HEURISTIC,
                            file_path=f.relative_path,
                            line_hint=line_no,
                            title="Broad `except Exception:` clause",
                            description="Catching the base Exception class can silently swallow unrelated "
                            "errors, making bugs harder to trace.",
                            suggestion="Catch the narrowest exception type(s) the code actually expects.",
                        )
                    )
        return findings

    @staticmethod
    def _detect_dead_code(files: List[ScannedFile]) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for f in files:
            if not f.content:
                continue
            for line_no, line in enumerate(f.content.splitlines(), start=1):
                if _COMMENTED_CODE_RE.match(line):
                    findings.append(
                        BugFinding(
                            category=BugCategory.DEAD_CODE,
                            severity=Severity.LOW,
                            detection_method=DetectionMethod.HEURISTIC,
                            file_path=f.relative_path,
                            line_hint=line_no,
                            title="Commented-out code",
                            description="A commented-out statement was found, which usually indicates "
                            "dead code left behind rather than an intentional comment.",
                            suggestion="Remove it if unneeded, or restore it if it's still required "
                            "(version control already preserves history).",
                        )
                    )
        return findings

    @staticmethod
    def _detect_unused_variables(files: List[ScannedFile]) -> List[BugFinding]:
        """Heuristic ONLY — flags a variable assigned exactly once and never referenced
        again within the same file. Deliberately conservative (whole-file text search,
        not real scope analysis) to keep false positives low; genuine scope-aware
        unused-variable detection would need a per-language AST parser."""
        findings: List[BugFinding] = []
        for f in files:
            if f.language not in _UNUSED_VAR_LANGUAGES or not f.content:
                continue

            lines = f.content.splitlines()
            for line_no, line in enumerate(lines, start=1):
                match = _ASSIGNMENT_RE.match(line)
                if not match:
                    continue
                name = match.group(1)
                if name.lower() in _PYTHON_KEYWORDS or name.startswith("_"):
                    continue

                occurrences = sum(1 for other in lines if re.search(rf"\b{re.escape(name)}\b", other))
                if occurrences <= 1:
                    findings.append(
                        BugFinding(
                            category=BugCategory.UNUSED_VARIABLE,
                            severity=Severity.INFO,
                            detection_method=DetectionMethod.HEURISTIC,
                            file_path=f.relative_path,
                            line_hint=line_no,
                            title=f"Possibly unused variable `{name}`",
                            description=f"`{name}` is assigned but doesn't appear to be referenced "
                            "again anywhere else in the file.",
                            suggestion="Remove it if truly unused, or check for a typo elsewhere.",
                        )
                    )
                    if len(findings) >= _MAX_HEURISTIC_FINDINGS:
                        return findings
        return findings

    @staticmethod
    def _detect_duplicate_code(files: List[ScannedFile]) -> List[BugFinding]:
        """Heuristic ONLY — hashes normalized 6-line windows and flags windows that
        recur across 2+ locations (same file or different files). A simple, fast
        duplicate-detection signal, not a semantic clone detector."""
        window_size = 6
        seen: Dict[str, List[str]] = defaultdict(list)

        for f in files:
            if not f.content:
                continue
            lines = [ln.strip() for ln in f.content.splitlines() if ln.strip()]
            for i in range(0, max(len(lines) - window_size + 1, 0)):
                window = "\n".join(lines[i : i + window_size])
                if len(window) < 80:  # skip trivial/short windows (imports, blank blocks)
                    continue
                digest = hashlib.sha1(window.encode("utf-8", errors="ignore")).hexdigest()
                seen[digest].append(f"{f.relative_path}:{i + 1}")

        findings: List[BugFinding] = []
        for locations in seen.values():
            if len(locations) < 2:
                continue
            first_file, first_line = locations[0].rsplit(":", 1)
            findings.append(
                BugFinding(
                    category=BugCategory.DUPLICATE_CODE,
                    severity=Severity.LOW,
                    detection_method=DetectionMethod.HEURISTIC,
                    file_path=first_file,
                    line_hint=int(first_line),
                    title="Duplicate code block detected",
                    description=f"A {window_size}-line block also appears at: {', '.join(locations[1:4])}"
                    + (f" and {len(locations) - 4} more" if len(locations) > 4 else "") + ".",
                    suggestion="Consider extracting the shared logic into a reusable function.",
                )
            )
            if len(findings) >= _MAX_HEURISTIC_FINDINGS:
                break
        return findings

    # ------------------------------------------------------------------
    # AI (Gemini) detection
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_ai_findings(raw_text: str, max_findings: int) -> List[BugFinding]:
        payload = extract_json_payload(raw_text)
        if not isinstance(payload, dict):
            return []

        findings: List[BugFinding] = []
        raw_findings = payload.get("findings")
        if isinstance(raw_findings, list):
            for item in raw_findings[:max_findings]:
                finding = BugDetectionService._parse_ai_finding(item)
                if finding:
                    findings.append(finding)
        return findings

    @staticmethod
    def _parse_ai_finding(item: Any) -> Optional[BugFinding]:
        if not isinstance(item, dict):
            return None
        try:
            return BugFinding(
                category=item.get("category", "possible_bug"),
                severity=item.get("severity", "info"),
                detection_method=DetectionMethod.AI,
                file_path=item.get("file_path"),
                line_hint=None,
                title=str(item.get("title", "")).strip() or "Untitled finding",
                description=str(item.get("description", "")).strip(),
                suggestion=str(item.get("suggestion", "")).strip(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Bug detection: skipping malformed AI finding: %s", exc)
            return None

    @staticmethod
    def _build_summary(heuristic: List[BugFinding], ai: List[BugFinding]) -> str:
        total = len(heuristic) + len(ai)
        if total == 0:
            return "No likely bugs were detected by static analysis or AI review."
        return (
            f"Found {total} potential issue(s): {len(heuristic)} from static analysis "
            f"(unused variables, dead code, duplicate code, exception handling) and "
            f"{len(ai)} from AI review of the retrieved context (possible bugs, null-handling, "
            f"memory/resource management)."
        )


def get_bug_detection_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> BugDetectionService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return BugDetectionService(scanner_service=scanner_service, rag_service=rag_service, gemini_service=gemini_service)
