"""Copilot envelope extracted without changing admission behavior."""
from __future__ import annotations

import json
import re
from typing import Any

from app.services.copilot.exceptions import _RegenerableEvidenceMismatch, _UnpublishableAnswer
from app.services.copilot.quotations import _QUOTE_MARK_RE
from app.services.provenance_service import (
    _MIN_VERIFIABLE_LEN,
    build_text_fragment_url,
    normalize_for_match,
    strip_wrapping_quotes,
    verify_whole_excerpt_in_text,
)

try:
    from json_repair import repair_json as _repair_json
    _HAS_JSON_REPAIR = True
except ImportError:  # pragma: no cover - json_repair is a declared dependency
    _HAS_JSON_REPAIR = False
    _repair_json = None

_FOLLOWUPS_RE = re.compile(r"===\s*FOLLOW-?UPS\s*===", re.IGNORECASE)


def _parse_citations(raw: str) -> tuple[list[dict], list[str]]:
    """Admit one complete citation array, then the optional followups envelope.

    Decode before looking for FOLLOWUPS: sentinel text inside a JSON excerpt is data.
    Never repair incomplete JSON or discard a malformed declaration as if it were absent.
    """
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*\n", text, re.IGNORECASE)
    if fenced:
        text = text[fenced.end():].lstrip()

    def unique_fields(pairs: list[tuple[str, Any]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise _UnpublishableAnswer("Duplicate citation field")
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise _UnpublishableAnswer("Non-JSON citation value")

    try:
        data, end = json.JSONDecoder(
            object_pairs_hook=unique_fields, parse_constant=reject_constant,
        ).raw_decode(text)
    except (ValueError, TypeError) as exc:
        raise _UnpublishableAnswer("Incomplete citation array") from exc
    trailer = text[end:].strip()
    if fenced:
        if not trailer.startswith("```"):
            raise _UnpublishableAnswer("Unclosed citation fence")
        trailer = trailer[3:].strip()
    followups: list[str] = []
    if trailer:
        followups_match = _FOLLOWUPS_RE.match(trailer)
        if not followups_match:
            raise _UnpublishableAnswer("Unexpected citation trailer")
        followups = _parse_followups(trailer[followups_match.end():])
    if not isinstance(data, list):
        raise _UnpublishableAnswer("Citation declaration is not an array")
    for item in data:
        if (not isinstance(item, dict)
                or type(item.get("n")) is not int or item["n"] <= 0
                or not isinstance(item.get("excerpt"), str)
                or any(item.get(key) is not None and not isinstance(item[key], str)
                       for key in ("section", "section_ref"))):
            raise _UnpublishableAnswer("Invalid citation declaration")
    return data, followups


def _parse_followups(raw: str) -> list[str]:
    """Parse the optional follow-up-questions trailer (a JSON array of short strings); max 3."""
    text = (raw or "").strip()
    if not text:
        return []
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        if _HAS_JSON_REPAIR and _repair_json is not None:
            try:
                data = json.loads(_repair_json(text))
            except (ValueError, TypeError):
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:140])
        if len(out) >= 3:
            break
    return out


# A section label is published as-is and never matched against the filing (most legitimate labels
# are not filing text), so a label carrying a double quote mark would present an unverified
# quotation beside "Source match found"; its citation is unverified (the founder's section_ref rule).
# The marks are decision F's, read from its one definition (_QUOTE_MARK_RE in quotations.py) so the two rules
# cannot drift; a label displays as plain text, so a character reference is not a mark. The Copilot
# eval's CITATION scorer reads this predicate too.
def section_label_is_quoted(label: object) -> bool:
    """Whether a citation's section label carries one of decision F's double quote marks."""
    return isinstance(label, str) and _QUOTE_MARK_RE.search(label) is not None


def _verify_citations(
    citations: list[dict], filing: Any, normalized_source: str, referenced: set[str],
) -> dict[str, dict]:
    """Verify original declarations before duplicate IDs can overwrite rejected evidence.

    Unused valid declarations remain a candidate pool only. A referenced ID must have an
    unambiguous declaration and every declaration for it must pass the whole-excerpt verifier
    (the Sources panel displays the whole excerpt as filing text) with a quote-free section label.
    The published excerpt is the declared one, never trimmed or substituted.
    """
    base_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""
    by_marker: dict[str, dict] = {}
    declared: dict[str, dict] = {}
    failed = False
    excerpt_mismatch_only = len(normalized_source) >= _MIN_VERIFIABLE_LEN
    for cite in citations:
        excerpt = cite["excerpt"].strip()
        section_ref = cite.get("section") or cite.get("section_ref")
        key = str(cite["n"])
        quoted_label = section_label_is_quoted(section_ref)
        verified = verify_whole_excerpt_in_text(excerpt, normalized_source) and not quoted_label
        colliding = key in declared and declared[key] != cite
        if key in referenced and (
            not verified or colliding
        ):
            failed = True
            excerpt_mismatch_only = (excerpt_mismatch_only and not quoted_label and not colliding
                                    and len(normalize_for_match(strip_wrapping_quotes(excerpt))) >= _MIN_VERIFIABLE_LEN)
        declared[key] = cite
        fragment_url = (
            build_text_fragment_url(base_url, strip_wrapping_quotes(excerpt), source_span=True)
            if verified and base_url else base_url
        )
        by_marker[key] = {
            "excerpt": excerpt,
            "section_ref": section_ref,
            "verified": verified,
            "fragment_url": fragment_url,
        }
    if failed:
        # Check all referenced declarations before classifying an excerpt-only mismatch. A later
        # identity collision, quoted label or missing literal must never buy another generation.
        required_text = {key for key in referenced if not key.startswith("F")}
        excerpt_mismatch_only = excerpt_mismatch_only and required_text <= declared.keys()
        failure = _RegenerableEvidenceMismatch if excerpt_mismatch_only else _UnpublishableAnswer
        raise failure("Unverified or ambiguous referenced citation")
    return by_marker
