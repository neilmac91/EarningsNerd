"""Resolve dataset markers into source-backed narrative citations."""
from __future__ import annotations

from typing import Any

from app.services import citation_markers
from app.services.trend_analysis.formatting import _format_value, _pct_str, _ratio_threshold_value


# --- AI narrative pipeline (M3) ----------------------------------------------------------------

# Citation-group classification (what makes a bracket group a citation vs prose, and the
# linear-regex discipline behind it) lives in the shared citation_markers module — the copilot
# resolver's multi-ref pre-pass consumes the same knowledge.
_MARKER_GROUP_RE = citation_markers.MARKER_GROUP_RE


_MARKER_REF_RE = citation_markers.MARKER_REF_RE


_is_citation_group = citation_markers.is_citation_group


def _point_citation(n: int, point: dict[str, Any]) -> dict[str, Any]:
    """Render a dataset point as a citation dict in the Copilot citation shape ({n, excerpt,
    section_ref, verified, fragment_url}) so the existing frontend citation UI renders it as-is.

    ``kind == "cagr"`` entries are series-level CAGR markers: the value is a growth fraction over
    the selected window, not an XBRL level, so only their excerpt/attribution differ — the dict
    shape is ONE literal so the citation contract with the frontend can't fork per kind."""
    provenance = point.get("provenance") or {}
    if point.get("kind") == "cagr":
        excerpt = f"{point['label']} CAGR = {_pct_str(point['value'])} ({point['period']})"
        section_ref = "Computed · CAGR"
    else:
        value_str = (
            _ratio_threshold_value(point["value"])
            if point.get("concept") == "current_ratio" and point.get("unit") == "pure"
            else _format_value(
                point["value"], point.get("unit") or "USD", bool(point.get("percent"))
            )
        )
        excerpt = f"{point['label']} = {value_str} ({point['period']})"
        if point.get("derived"):
            excerpt += " — derived Q4"
        section_ref = (
            "Calculated · " + str(provenance.get("formula") or point["concept"])
            if provenance.get("method") == "calculated"
            else f"XBRL · {point['raw_tag']}" if point.get("raw_tag")
            else f"Reported filing · {point['concept']}"
        )
    return {
        "n": n,
        "excerpt": excerpt,
        "section_ref": section_ref,
        "verified": True,
        "fragment_url": None,
        "concept": point["concept"],
        "value": point["value"],
        "period": point["period"],
        "derived": bool(point.get("derived")),
        "reconciled": point.get("reconciled"),
        "provenance": point.get("provenance"),
        "source_url": point.get("source_url") or provenance.get("source_url"),
    }


def resolve_narrative_citations(
    text: str, index: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], int, int]:
    """One left-to-right pass over the narrative: every ``[F#]`` reference resolves against the
    dataset's marker index and is renumbered ``[1]``, ``[2]``, ... in first-appearance order
    (repeat mentions reuse their number). Multi-reference groups a model may emit despite the
    prompt contract — ``[F1, F2]``, ``[F1..F10]``, ``[F1 vs F2]`` — resolve as a chain
    (``[1][2]``; ranges resolve their written endpoints). A reference the dataset never issued
    can ONLY be a model artifact — it is dropped (a group that loses every reference is stripped,
    swallowing the space before it, the ``_resolve_citations`` contract from Copilot) and counted
    in ``unverified`` so callers can surface how many references could not be verified.
    Returns (final_text, citations, grounded, unverified).
    """
    citations: list[dict[str, Any]] = []
    assigned: dict[str, int] = {}
    unverified = 0
    pieces: list[str] = []
    cursor = 0
    for match in _MARKER_GROUP_RE.finditer(text):
        content = match.group(1)
        if not _MARKER_REF_RE.search(content):
            continue  # no F-reference at all — ordinary prose brackets / markdown link labels
        if not _is_citation_group(content):
            continue  # prose that happens to contain an F-token — not a citation group
        numbers: list[int] = []
        for ref in _MARKER_REF_RE.findall(content):
            key = f"F{int(ref)}"
            point = index.get(key)
            if point is None:
                unverified += 1
                continue
            n = assigned.get(key)
            if n is None:
                n = len(citations) + 1
                assigned[key] = n
                citations.append(_point_citation(n, point))
            if n not in numbers:
                numbers.append(n)
        if numbers:
            pieces.append(text[cursor:match.start()])
            pieces.append("".join(f"[{n}]" for n in numbers))
        else:
            pieces.append(text[cursor:match.start()].rstrip(" "))
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces), citations, len(citations), unverified
