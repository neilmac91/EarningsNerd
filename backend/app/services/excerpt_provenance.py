"""Bounded observations about an excerpt; never a completeness certificate.

The record is the excerpt source contract (E80-C1, schema_version 2). Its producer is the one excerpt builder,
``summary_generation_service.get_or_cache_excerpt``, which logs at most one per call ("Excerpt provenance: ...") and
hands that one to an ``on_provenance`` callback; a call that returns early (no text and no sections, no filing)
records none, which a reader treats as no excerpt. An evaluation harness reads the producer's fields rather than
re-deriving them. Fields:

- ``accession``, ``filing_type``: the filing the excerpt was built for.
- ``source``: ``edgartools`` (native sections), ``regex_fallback``, or ``legacy_cached_excerpt`` (a stored excerpt,
  whose build cannot be known now); eval-baseline's runner also writes ``raw_filing_fallback``.
- ``outcome``: ``native``, ``fallback``, ``cached``, or ``unavailable`` (no excerpt was built).
- ``fallback_reason``: why a fallback or unavailable excerpt did not come from native sections:
  ``native_sections_disabled`` (``USE_EDGARTOOLS_SECTIONS`` off), ``sections_not_supplied`` (no section text reached
  the builder: the parser was unavailable, timed out, failed or did not run, which this layer cannot tell apart),
  ``native_excerpt_thin`` (the native assembly was empty or under its floor), or ``unrecorded`` (a caller that names
  none). ``None`` for a native or cached excerpt.
- ``excerpt_sha256``, ``excerpt_chars``: the exact returned string.
- ``document_sha256``, ``sections_sha256``: the document text and the section mapping the builder was given, hashed as
  the Copilot evaluation's preparation artifacts hash them (UTF-8 text; JSON with sorted keys), for a caller that asks
  (``hash_inputs``: the builder asks when a caller takes the record; the summary pipeline's own log carries ``None``,
  which keeps the whole-document hash off its hot path); also ``None`` when not supplied, and for a cached excerpt,
  whose build inputs are unknown. A reader compares ``sections_sha256`` only where it is set: ``None`` means not
  supplied, where the Copilot preparation still writes and hashes ``null`` or ``{}``.
- ``supplied_sections``: each canonical section supplied, with its length; ``missing_sections``: the canonical
  sections (``NATIVE_SECTION_KEYS``) supplied blank or not at all, or ``None`` for a cached excerpt, whose sections
  are unknown. The native assembler also skips a section under 200 characters, which the section parser never
  returns (``edgar/xbrl_sections.py``), so the two agree on real inputs.
- ``coverage_status``: ``unknown`` for a cached excerpt, else ``observed_partial``; no record certifies completeness.
"""

import hashlib
import json
from typing import Any, Mapping, Optional

# The canonical sections the native excerpt is assembled from, for every form (extraction._SECTION_LAYOUT).
NATIVE_SECTION_KEYS = ("financials", "mda", "risk")

FALLBACK_REASONS = frozenset({
    "native_sections_disabled", "sections_not_supplied", "native_excerpt_thin", "unrecorded",
})


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def excerpt_provenance(
    excerpt: str,
    *,
    accession: str,
    source: str,
    sections: Optional[Mapping[str, str]] = None,
    filing_type: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    document_text: Optional[str] = None,
    hash_inputs: bool = False,
) -> dict[str, Any]:
    """Hash the exact returned string and count only supplied canonical sections.

    Current inputs cannot establish how a persisted excerpt was originally built.
    No source text, topic inference, truncation guess, or fetch belongs here.
    """
    cached = source == "legacy_cached_excerpt"
    if cached:
        outcome = "cached"
    elif not excerpt:
        outcome = "unavailable"
    elif source == "edgartools":
        outcome = "native"
    else:
        outcome = "fallback"
    observed, supplied = [], set()
    if not cached and sections:
        for key in NATIVE_SECTION_KEYS:
            text = sections.get(key)
            if isinstance(text, str):
                observed.append({"key": key, "supplied_chars": len(text)})
                if text.strip():
                    supplied.add(key)
    return {
        "schema_version": 2,
        "accession": accession,
        "filing_type": filing_type,
        "source": source,
        "outcome": outcome,
        "fallback_reason": (fallback_reason or "unrecorded") if outcome in ("fallback", "unavailable") else None,
        "coverage_status": "unknown" if cached else "observed_partial",
        "excerpt_sha256": _sha256(excerpt),
        "excerpt_chars": len(excerpt),
        "document_sha256": _sha256(document_text) if hash_inputs and document_text and not cached else None,
        "sections_sha256": (
            _sha256(json.dumps(dict(sections), sort_keys=True, default=str))
            if hash_inputs and sections and not cached else None
        ),
        "supplied_sections": observed,
        "missing_sections": None if cached else [key for key in NATIVE_SECTION_KEYS if key not in supplied],
    }
