"""Bounded observations about an excerpt; never a completeness certificate."""

import hashlib
from typing import Any, Mapping, Optional


def excerpt_provenance(
    excerpt: str,
    *,
    accession: str,
    source: str,
    sections: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Hash the exact returned string and count only supplied canonical sections.

    Current inputs cannot establish how a persisted excerpt was originally built.
    No source text, topic inference, truncation guess, or fetch belongs here.
    """
    cached = source == "legacy_cached_excerpt"
    observed = []
    if not cached and sections:
        for key in ("financials", "mda", "risk"):
            text = sections.get(key)
            if isinstance(text, str):
                observed.append({"key": key, "supplied_chars": len(text)})
    return {
        "schema_version": 1,
        "accession": accession,
        "source": source,
        "coverage_status": "unknown" if cached else "observed_partial",
        "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        "excerpt_chars": len(excerpt),
        "supplied_sections": observed,
    }
