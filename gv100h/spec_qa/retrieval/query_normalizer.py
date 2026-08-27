"""Structured query normalization for governed Spec QA retrieval.

Numeric tokens are never a lexical score. Selector values become an exact
lookup key only when the query is about a Hub Class feature selector.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

SECTION_REF_PATTERN = re.compile(r"\d+(?:\.\d+)+")
# Clauses that identify the selector's own id, not any nearby numeric field.
SELECTOR_ID_SYNTAX_RE = re.compile(
    r"(?:feature\s+selector|selector)(?:\s+value)?\s*(?:is|=|:)?\s*(0x[0-9a-f]+|\d+)\b"
    r"|(?:feature\s+selector|selector)\s+has\s+value\s*(?:is|=|:)?\s*(0x[0-9a-f]+|\d+)\b",
    re.IGNORECASE,
)
DETACHED_SELECTOR_VALUE_RE = re.compile(
    r"\b(?:has\s+)?value\s*(?:is|=|:)?\s*(0x[0-9a-f]+|\d+)\b",
    re.IGNORECASE,
)
FEATURE_OR_SELECTOR_RE = re.compile(r"\b(?:feature|selector)\b", re.IGNORECASE)
NAMED_SELECTOR_RE = re.compile(r"\bPORT_[A-Z][A-Z0-9_]*\b", re.IGNORECASE)


def parse_selector_int(token: str) -> Optional[int]:
    text = (token or "").strip().lower()
    if not text or "." in text:
        return None
    try:
        if text.startswith("0x"):
            return int(text, 16)
        return int(text)
    except ValueError:
        return None


def _first_capture(match: re.Match[str]) -> Optional[str]:
    return next((group for group in match.groups() if group), None)


def normalize_feature_selector_query(
    query_text: str,
    target_scope: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return a structured selector lookup, or None.

    Requires a feature/selector cue plus an integer/hex value that is not a
    dotted section reference. Bare numbers (section 5, 5 ms, 5 ports) do not
    qualify. A named selector plus another field value (link-state value 3)
    is not a selector-id lookup.
    """
    raw = query_text or ""
    if not FEATURE_OR_SELECTOR_RE.search(raw):
        return None
    masked = SECTION_REF_PATTERN.sub(" ", raw)
    match = SELECTOR_ID_SYNTAX_RE.search(masked)
    if match is None and NAMED_SELECTOR_RE.search(masked) is None:
        match = DETACHED_SELECTOR_VALUE_RE.search(masked)
    if not match:
        return None
    value_token = _first_capture(match)
    value = parse_selector_int(value_token or "")
    if value is None:
        return None
    return {
        "entity_type": "feature_selector",
        "value": value,
        "scope": target_scope,
    }
