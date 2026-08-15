"""
app/services/security_service.py

Security Vulnerability Detection (Step 13) — three detection methods,
merged into one response:

    1. HEURISTIC — hardcoded secrets/API keys: deterministic regex over
       Scanner's cached files (Step 4). This category is intentionally
       NEVER delegated to the LLM: a missed secret is a real credential
       leak, and regex pattern-matching is both more reliable and free
       of hallucination risk for this specific, mechanically-detectable
       category.
    2. AI — SQL injection / XSS / CSRF / weak authentication / unsafe
       file access: genuinely requires reasoning about data flow and
       intent, via Gemini over RAG-retrieved context (Step 8).
    3. HEURISTIC — unsafe dependencies: delegated to `DependencyService`
       (manifest parsing + a small illustrative risk list — NOT a live
       CVE feed; see that module's docstring).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import Depends

from app.core.exceptions import RepositoryNotFoundError, ScanNotPerformedError
from app.core.logging import get_logger
from app.prompts.intelligence_prompts import build_security_prompt, chunks_to_sources, extract_json_payload
from app.schemas.intelligence import (
    DetectionMethod,
    SecurityAnalysisRequest,
    SecurityAnalysisResponse,
    SecurityCategory,
    SecurityFinding,
    Severity,
)
from app.schemas.scanner import ScannedFile
from app.services.dependency_service import DependencyService, get_dependency_service
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.rag_service import RAGService, get_rag_service
from app.services.scanner_service import ScannerService, get_scanner_service

logger = get_logger("services.security")

_RETRIEVAL_TOP_K = 12
_MAX_HEURISTIC_FINDINGS = 25

# Placeholders that would otherwise false-positive as "hardcoded secrets".
_PLACEHOLDER_TOKENS = {
    "changeme", "change-me", "your-api-key", "your_api_key", "xxxxxxxx", "example",
    "placeholder", "dummy", "fake", "test", "todo", "insert-key-here", "<your-key>",
}

_SECRET_PATTERNS: List[tuple[str, "re.Pattern[str]", Severity]] = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), Severity.CRITICAL),
    (
        "Generic private key block",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        Severity.CRITICAL,
    ),
    (
        "Hardcoded API key assignment",
        re.compile(r"(?i)\b(api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
        Severity.HIGH,
    ),
    (
        "Hardcoded secret/token assignment",
        re.compile(r"(?i)\b(secret|token|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-./+=]{12,}['\"]"),
        Severity.HIGH,
    ),
    (
        "Hardcoded password assignment",
        re.compile(r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]{4,}['\"]"),
        Severity.HIGH,
    ),
]

_ENV_LOOKUP_HINT_RE = re.compile(r"os\.(environ|getenv)|process\.env|config\(")


class SecurityService:
    def __init__(
        self,
        scanner_service: ScannerService,
        rag_service: RAGService,
        gemini_service: GeminiService,
        dependency_service: DependencyService,
    ) -> None:
        self.scanner_service = scanner_service
        self.rag_service = rag_service
        self.gemini_service = gemini_service
        self.dependency_service = dependency_service

    async def analyze(self, request: SecurityAnalysisRequest) -> SecurityAnalysisResponse:
        heuristic_findings = self.scan_for_secrets(request.repository_name, request.focus_path)
        heuristic_findings.extend(self._scan_dependencies(request.repository_name))

        query = (
            f"authentication, input handling, database queries, and file access in {request.focus_path}"
            if request.focus_path
            else "authentication, input validation, database queries, template rendering, and file access"
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
        prompt = build_security_prompt(chunks, sources, remaining_budget)
        raw_text, _usage = await self.gemini_service.generate(prompt)
        ai_summary, ai_risk_level, ai_findings = self._parse_ai_response(raw_text, remaining_budget)

        all_findings = (heuristic_findings + ai_findings)[: request.max_findings]
        overall_risk = self._overall_risk(all_findings, ai_risk_level)
        summary = self._build_summary(heuristic_findings, ai_findings, ai_summary)

        logger.info(
            "Security analysis complete | repo=%s | heuristic=%d | ai=%d | risk=%s",
            request.repository_name,
            len(heuristic_findings),
            len(ai_findings),
            overall_risk.value,
        )

        return SecurityAnalysisResponse(
            repository_name=request.repository_name,
            summary=summary,
            risk_level=overall_risk,
            findings=all_findings,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Heuristic: hardcoded secrets
    # ------------------------------------------------------------------
    def scan_for_secrets(self, repository_name: str, focus_path: Optional[str]) -> List[SecurityFinding]:
        """Public — also reused directly by `QualityScoreService` (Step 13) for a fast,
        LLM-free security signal in the Repository Quality Score."""
        try:
            files = self.scanner_service.get_cached_files(repository_name)
        except ScanNotPerformedError:
            return []

        if focus_path:
            files = [f for f in files if f.relative_path == focus_path]

        findings: List[SecurityFinding] = []
        for f in files:
            if not f.content:
                continue
            for line_no, line in enumerate(f.content.splitlines(), start=1):
                if _ENV_LOOKUP_HINT_RE.search(line):
                    continue  # value is pulled from env/config, not hardcoded
                if self._looks_like_placeholder(line):
                    continue

                for label, pattern, severity in _SECRET_PATTERNS:
                    if pattern.search(line):
                        category = (
                            SecurityCategory.API_KEY if "API key" in label else SecurityCategory.HARDCODED_SECRET
                        )
                        findings.append(
                            SecurityFinding(
                                category=category,
                                severity=severity,
                                detection_method=DetectionMethod.HEURISTIC,
                                file_path=f.relative_path,
                                line_hint=line_no,
                                title=label,
                                description=f"A pattern matching '{label}' was found hardcoded in source.",
                                remediation="Move this value to an environment variable or a secrets "
                                "manager, remove it from version control, and rotate the credential.",
                            )
                        )
                        break  # one finding per line is enough
                if len(findings) >= _MAX_HEURISTIC_FINDINGS:
                    return findings
        return findings

    @staticmethod
    def _looks_like_placeholder(line: str) -> bool:
        lowered = line.lower()
        return any(token in lowered for token in _PLACEHOLDER_TOKENS)

    # ------------------------------------------------------------------
    # Heuristic: unsafe dependencies
    # ------------------------------------------------------------------
    def _scan_dependencies(self, repository_name: str) -> List[SecurityFinding]:
        try:
            analysis = self.dependency_service.analyze(repository_name)
        except RepositoryNotFoundError:
            return []

        findings: List[SecurityFinding] = []
        for dep in analysis.dependencies:
            if not dep.risk_notes:
                continue
            findings.append(
                SecurityFinding(
                    category=SecurityCategory.UNSAFE_DEPENDENCY,
                    severity=Severity.MEDIUM,
                    detection_method=DetectionMethod.HEURISTIC,
                    file_path=dep.manifest_file,
                    line_hint=None,
                    title=f"Dependency flagged: {dep.name}",
                    description=" ".join(dep.risk_notes)
                    + " (This is an illustrative advisory, not a live CVE database lookup — verify "
                    "against the pinned version before acting.)",
                    remediation=f"Confirm the pinned version of `{dep.name}` and upgrade if it's "
                    "affected by a known advisory.",
                )
            )
        return findings

    # ------------------------------------------------------------------
    # AI: SQLi / XSS / CSRF / weak auth / unsafe file access
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_ai_response(raw_text: str, max_findings: int) -> tuple[str, Optional[Severity], List[SecurityFinding]]:
        payload = extract_json_payload(raw_text)
        if not isinstance(payload, dict):
            return "", None, []

        summary = str(payload.get("summary") or "").strip()
        risk_level: Optional[Severity] = None
        try:
            risk_level = Severity(payload.get("risk_level"))
        except ValueError:
            pass

        findings: List[SecurityFinding] = []
        raw_findings = payload.get("findings")
        if isinstance(raw_findings, list):
            for item in raw_findings[:max_findings]:
                finding = SecurityService._parse_ai_finding(item)
                if finding:
                    findings.append(finding)
        return summary, risk_level, findings

    @staticmethod
    def _parse_ai_finding(item: Any) -> Optional[SecurityFinding]:
        if not isinstance(item, dict):
            return None
        try:
            return SecurityFinding(
                category=item.get("category", "weak_authentication"),
                severity=item.get("severity", "info"),
                detection_method=DetectionMethod.AI,
                file_path=item.get("file_path"),
                line_hint=None,
                title=str(item.get("title", "")).strip() or "Untitled finding",
                description=str(item.get("description", "")).strip(),
                remediation=str(item.get("remediation", "")).strip(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Security analysis: skipping malformed AI finding: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    @staticmethod
    def _overall_risk(findings: List[SecurityFinding], ai_risk_level: Optional[Severity]) -> Severity:
        severities = [f.severity for f in findings]
        for level in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            if level in severities:
                return level
        return ai_risk_level or Severity.INFO

    @staticmethod
    def _build_summary(heuristic: List[SecurityFinding], ai: List[SecurityFinding], ai_summary: str) -> str:
        total = len(heuristic) + len(ai)
        base = (
            f"Found {total} security finding(s): {len(heuristic)} from deterministic pattern "
            f"scanning (secrets/keys/dependencies) and {len(ai)} from AI review of the retrieved "
            f"context."
            if total
            else "No security issues were detected by pattern scanning or AI review."
        )
        return f"{base} {ai_summary}".strip()


def get_security_service(
    scanner_service: ScannerService = Depends(get_scanner_service),
    rag_service: RAGService = Depends(get_rag_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
    dependency_service: DependencyService = Depends(get_dependency_service),
) -> SecurityService:
    """FastAPI dependency provider — see app/api/intelligence.py."""
    return SecurityService(
        scanner_service=scanner_service,
        rag_service=rag_service,
        gemini_service=gemini_service,
        dependency_service=dependency_service,
    )
