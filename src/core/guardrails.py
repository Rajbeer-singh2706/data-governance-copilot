"""
Day 13: Input guardrails — run in pre_hook_node before any LLM call.
 
Checks (in order):
  1. Query length   — too short / too long
  2. Destructive SQL patterns  — DROP, DELETE, TRUNCATE
  3. PII detection  — SSN, credit cards, emails → redacted (query still allowed)
  4. Prompt injection attempts — "ignore previous instructions" etc.
 
Returns GuardrailResult.  If passed=False the pre_hook short-circuits the graph.
If passed=True but cleaned_query differs from the original, the cleaned version
is forwarded to the supervisor so PII never reaches the LLM.
"""
from __future__ import annotations
 
import re
from dataclasses import dataclass, field

# ── Config ─────────────────────────────────────────────────────────────────
MIN_LENGTH = 3       # characters
MAX_LENGTH = 2_000   # characters

# ── Patterns ───────────────────────────────────────────────────────────────
 
# Destructive SQL — block entirely
_DESTRUCTIVE = [
    re.compile(r"\bdrop\s+table\b",     re.I),
    re.compile(r"\bdelete\s+from\b",    re.I),
    re.compile(r"\btruncate\b",         re.I),
    re.compile(r"\balter\s+table\b",    re.I),
    re.compile(r"\bdrop\s+database\b",  re.I),
]
 
# Prompt injection — block
_INJECTION = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+a",                        re.I),
    re.compile(r"forget\s+(everything|your\s+instructions)",  re.I),
    re.compile(r"jailbreak",                                   re.I),
    re.compile(r"dan\s+mode",                                  re.I),
]
 
# PII — redact but allow the query through
_PII = [
    # US Social Security Number
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),      "[SSN-REDACTED]"),
    # Credit card (Visa / MC / Amex / Discover — 13–16 digits)
    (re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|"
                r"3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
                "[CARD-REDACTED]"),
    # Email
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
                "[EMAIL-REDACTED]"),
    # UK National Insurance
    (re.compile(r"\b[A-Z]{2}\d{6}[A-D]\b", re.I), "[NI-REDACTED]"),
]
 

# ── Result type ────────────────────────────────────────────────────────────
@dataclass
class GuardrailResult:
    passed: bool
    reason: str = ""                   # populated when passed=False
    cleaned_query: str = ""            # PII-scrubbed query (may equal original)
    pii_found: bool = False            # informational flag
    checks_run: list = field(default_factory=list)  # audit trail
 

# ── Main entry point ───────────────────────────────────────────────────────
 
def run_guardrails(query: str) -> GuardrailResult:
    """
    Run all guardrail checks on the raw query string.
 
    Returns GuardrailResult:
      passed=False → pre_hook short-circuits the graph
      passed=True  → cleaned_query (PII removed) forwarded to supervisor
    """
    checks: list[str] = []
 
    # ── 1. Length ───────────────────────────────────────────────────────
    checks.append("length")
    stripped = query.strip()
    if len(stripped) < MIN_LENGTH:
        return GuardrailResult(
            passed=False,
            reason=f"Query too short (min {MIN_LENGTH} characters).",
            checks_run=checks,
        )
    if len(stripped) > MAX_LENGTH:
        return GuardrailResult(
            passed=False,
            reason=f"Query too long (max {MAX_LENGTH} characters).",
            checks_run=checks,
        )
 
    # ── 2. Destructive SQL ──────────────────────────────────────────────
    checks.append("destructive_sql")
    for pattern in _DESTRUCTIVE:
        if pattern.search(stripped):
            return GuardrailResult(
                passed=False,
                reason="Query contains destructive SQL keywords.",
                checks_run=checks,
            )
 
    # ── 3. Prompt injection ─────────────────────────────────────────────
    checks.append("prompt_injection")
    for pattern in _INJECTION:
        if pattern.search(stripped):
            return GuardrailResult(
                passed=False,
                reason="Query appears to contain a prompt-injection attempt.",
                checks_run=checks,
            )
 
    # ── 4. PII redaction (non-blocking) ────────────────────────────────
    checks.append("pii_redaction")
    cleaned = stripped
    pii_found = False
    for pattern, replacement in _PII:
        new_cleaned = pattern.sub(replacement, cleaned)
        if new_cleaned != cleaned:
            pii_found = True
            cleaned = new_cleaned
 
    return GuardrailResult(
        passed=True,
        cleaned_query=cleaned,
        pii_found=pii_found,
        checks_run=checks,
    )
 