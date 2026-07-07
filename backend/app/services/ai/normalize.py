"""Placeholder/section/risk normalization helpers for AI summary output (roadmap S2 façade split).

Pure string/collection normalizers used to decide whether a model-authored field carries real
content and to canonicalize the risk-factor list. Leaf module — extracted verbatim from
``openai_service`` and re-exported there for existing callers.
"""
from __future__ import annotations

from typing import Any, Optional


_PLACEHOLDER_STRINGS = {
    "",
    "n/a",
    "na",
    "none",
    "not available",
    "not disclosed",
    "not provided",
    "-",
    "--",
    "—",
    "n.a.",
}

_BOILERPLATE_RISK_PHRASES = {
    "cash flow and debt levels are concerning",
}


def _normalize_simple_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        joined = " ".join(str(v).strip() for v in value if v)
        value = joined
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in _PLACEHOLDER_STRINGS:
        return None
    return text


def _section_has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        if stripped.lower() in _PLACEHOLDER_STRINGS:
            return False
        return True
    if isinstance(value, dict):
        return any(_section_has_content(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_section_has_content(item) for item in value)
    return True


def _normalize_evidence(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("excerpt", "text", "quote", "support", "source", "reference", "tag", "xbrl_tag", "citation"):
            if key in value:
                part = _normalize_evidence(value.get(key))
                if part:
                    parts.append(part)
        combined = " | ".join(parts)
        return _normalize_simple_string(combined) if combined else None
    if isinstance(value, (list, tuple, set)):
        parts = [ev for item in value if (ev := _normalize_evidence(item))]
        # " · " (not "; "): "."-terminated excerpts joined with "; " render the ".;" artifact
        # the P0-2 bullet fix eliminates elsewhere — this inline evidence run is the one list
        # field that legitimately stays inline.
        combined = " · ".join(parts)
        return _normalize_simple_string(combined) if combined else None
    return _normalize_simple_string(value)


def _normalize_risk_factors(raw_risks: Any) -> list[dict[str, str]]:
    if raw_risks is None:
        return []

    raw_items: list[Any] = []
    if isinstance(raw_risks, list):
        raw_items = raw_risks
    elif isinstance(raw_risks, dict):
        # Accept either explicit list container or dict keyed by identifiers
        for value in raw_risks.values():
            if isinstance(value, list):
                raw_items.extend(value)
            else:
                raw_items.append(value)
    else:
        raw_items = [raw_risks]

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for entry in raw_items:
        summary: Optional[str] = None
        description: Optional[str] = None
        title: Optional[str] = None
        evidence: Optional[str] = None

        if isinstance(entry, dict):
            summary = (
                _normalize_simple_string(entry.get("summary"))
                or _normalize_simple_string(entry.get("description"))
                or _normalize_simple_string(entry.get("detail"))
                or _normalize_simple_string(entry.get("text"))
                or _normalize_simple_string(entry.get("title"))
            )
            title = _normalize_simple_string(entry.get("title"))
            description = _normalize_simple_string(entry.get("description"))
            evidence = (
                _normalize_evidence(entry.get("supporting_evidence"))
                or _normalize_evidence(entry.get("supportingEvidence"))
                or _normalize_evidence(entry.get("evidence"))
                or _normalize_evidence(entry.get("source"))
            )
        else:
            summary = _normalize_simple_string(entry)
            evidence = None

        if not summary:
            continue

        normalized_key = summary.lower()
        if normalized_key in _BOILERPLATE_RISK_PHRASES and not evidence:
            continue

        # If no evidence provided, use a default message instead of discarding the risk
        # This preserves legitimate risks that the AI extracted but didn't provide evidence for
        if not evidence:
            evidence = "See SEC filing for full details."

        dedupe_key = (normalized_key, evidence.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        normalized_entry: dict[str, str] = {
            "summary": summary,
            "supporting_evidence": evidence,
        }
        if title:
            normalized_entry["title"] = title
        if description and description != summary:
            normalized_entry["description"] = description

        normalized.append(normalized_entry)

    return normalized
