"""Input guardrails: length, destructive SQL, prompt injection, PII redaction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple


@dataclass
class GuardrailResult:
    passed: bool
    query: str          # possibly redacted
    reason: str = ""    # why it was blocked, empty if passed


_DESTRUCTIVE_SQL = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER)\b", re.IGNORECASE
)
_PROMPT_INJECTION = re.compile(
    r"(ignore\s+(previous|above|all)\s+instructions?|jailbreak|DAN\b|do\s+anything\s+now)",
    re.IGNORECASE,
)
_PII_PATTERNS = [
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    # Credit cards (basic)
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARD_REDACTED]"),
    # Email
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL_REDACTED]"),
    # UK National Insurance
    (re.compile(r"\b[A-Z]{2}\d{6}[A-D]\b"), "[NI_REDACTED]"),
]

MIN_LEN = 2
MAX_LEN = 2000


def check_guardrails(query: str) -> GuardrailResult:
    """
    Run all guardrail checks in order. First match blocks or redacts.

    Order:
      1. Length         → block
      2. Destructive SQL → block
      3. Prompt injection → block
      4. PII            → redact silently, allow
    """
    # 1. Length
    if len(query) < MIN_LEN:
        return GuardrailResult(False, query, f"Query too short (min {MIN_LEN} chars)")
    if len(query) > MAX_LEN:
        return GuardrailResult(False, query, f"Query too long (max {MAX_LEN} chars)")

    # 2. Destructive SQL
    if _DESTRUCTIVE_SQL.search(query):
        return GuardrailResult(False, query, "Destructive SQL keyword detected")

    # 3. Prompt injection
    if _PROMPT_INJECTION.search(query):
        return GuardrailResult(False, query, "Prompt injection attempt detected")

    # 4. PII — redact silently
    redacted = query
    for pattern, replacement in _PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)

    return GuardrailResult(True, redacted)