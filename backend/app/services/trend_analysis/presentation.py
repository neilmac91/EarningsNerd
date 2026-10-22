"""Code-owned narrative display/evidence, independent of the selector's prompt version."""
from __future__ import annotations

from copy import deepcopy
import re
from types import SimpleNamespace
from typing import Any

from app.services.trend_analysis.cache import NARRATIVE_FORMAT_VERSION
from app.services.trend_analysis.citations import resolve_narrative_citations
from app.services.trend_analysis.data_notes import (
    DATA_NOTES_VERSION, citation_data_notes, resolve_data_notes,
)
from app.services.trend_analysis.fidelity import scan_numeric_fidelity
from app.services.trend_analysis.narrative_display import (
    compact_narrative_text, currency_precision_plan,
)
from app.services.trend_analysis.observations import (
    TrendObservation, _point_value, render_observation_selection,
)
from app.services.trend_analysis.source_documents import current_links, folder_links
from app.services.trend_analysis.stream_events import analysis_completion


_OPERANDS_PREFIX = " Source operands: "
_MARKER = re.compile(r"\[(F\d+)\]")


def presentation_is_current(dataset: dict[str, Any]) -> bool:
    """One compatibility check for persisted cache reads and PDF admission.

    These are application-owned saved envelopes, not a second data-validation boundary.
    Missing/old presentation cannot be silently re-served under current display semantics.
    """
    presentation = dataset.get("narrative_presentation")
    notes = dataset.get("data_notes")
    if not isinstance(presentation, dict) or not isinstance(notes, dict):
        return False
    combined = presentation.get("notes")
    return (
        presentation.get("format_version") == NARRATIVE_FORMAT_VERSION
        and bool(dataset.get("snapshot_id"))
        and presentation.get("snapshot_id") == dataset["snapshot_id"]
        and type(presentation.get("data_notes_version")) is int
        and presentation["data_notes_version"] == DATA_NOTES_VERSION
        and type(notes.get("version")) is int and notes["version"] == DATA_NOTES_VERSION
        and isinstance(combined, dict)
        and type(combined.get("version")) is int and combined["version"] == DATA_NOTES_VERSION
        and presentation.get("offset_encoding") == "utf-16"
        and isinstance(presentation.get("evidence"), list)
    )


def _display_unit(point: dict[str, Any]) -> str | None:
    if point.get("kind") == "cagr":
        return "growth fraction"
    if point.get("kind") == "window_pp":
        return "percentage points"
    return "percent" if point.get("percent") else point.get("unit")


def cached_analysis_completion(dataset: dict[str, Any], cached: Any) -> dict[str, Any]:
    from app.services.trend_analysis.dataset import marker_index

    index = marker_index(dataset)
    citations = cached.citations_json or []
    mismatched = scan_numeric_fidelity(cached.narrative_md, citations, index)
    # The saved row stays as it is; the response's links follow the rebuilt dataset (current_links).
    presentation = deepcopy(cached.dataset_json["narrative_presentation"])
    for entry in presentation["evidence"]:
        entry["operands"] = current_links(entry["operands"], index)
    return analysis_completion(
        {**dataset, "narrative_presentation": presentation},
        analysis_id=cached.id, narrative=cached.narrative_md, citations=current_links(citations, index),
        grounded=cached.grounded, unverified=cached.unverified, mismatched=len(mismatched),
        cached=True, invalidated=False, usage={},
    )


def cached_analysis_export(dataset: dict[str, Any], cached: Any) -> SimpleNamespace:
    """A copy of a saved analysis for its PDF, with the links a re-serve gives it.

    The export's checks hold the saved and rebuilt datasets to one snapshot. Where ``folder_links``
    reads the rebuilt series as it reads the saved ones (so each link, operands' included, stays in
    the folder it saved), the copy takes the rebuilt series; its citations go through ``current_links``.
    The saved row is not touched; the copy is the renderer's.
    """
    from app.services.trend_analysis.dataset import marker_index

    saved = cached.dataset_json or {}
    alike = folder_links(dataset["series"]) == folder_links(saved.get("series"))
    return SimpleNamespace(**{
        **{key: value for key, value in vars(cached).items() if not key.startswith("_")},
        "dataset_json": {**saved, "series": dataset["series"]} if alike else saved,
        "citations_json": current_links(cached.citations_json or [], marker_index(dataset)),
    })


def _operand(
    marker: str, point: dict[str, Any], citation_id: int,
    precision: frozenset[tuple[str, str, bool]],
) -> dict[str, Any]:
    display = _point_value(point, point, ratio_precision=point.get("concept") == "current_ratio")
    provenance = point.get("provenance") or {}
    return {
        "marker": marker, "concept": point["concept"], "label": point["label"],
        "value": point["value"], "unit": _display_unit(point),
        "percent": bool(point.get("percent")), "period": point["period"],
        "citation_id": citation_id, "derived": bool(point.get("derived")),
        "display_value": compact_narrative_text(display, precision),
        "provenance": deepcopy(point.get("provenance")),
        "source_url": point.get("source_url") or provenance.get("source_url"),
    }


def _evidence(
    selected: list[tuple[TrendObservation, str]], narrative: str,
    numbers: dict[str, int], index: dict[str, dict[str, Any]],
    precision: frozenset[tuple[str, str, bool]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    cursor = 0
    for observation, display in selected:
        resolved = _MARKER.sub(lambda match: f"[{numbers[match[1]]}]", display)
        start = narrative.index(resolved, cursor)
        cursor = start + len(resolved)
        if observation.section != "red_flags" or _OPERANDS_PREFIX not in observation.markdown:
            continue
        tail_start = start + resolved.index(_OPERANDS_PREFIX)
        tail = narrative[tail_start:cursor]
        original_tail = observation.markdown.split(_OPERANDS_PREFIX, 1)[1]
        markers = _MARKER.findall(original_tail)
        result.append({
            "observation_id": observation.id, "section": observation.section,
            "tail": {"start": len(narrative[:tail_start].encode("utf-16-le")) // 2,
                     "end": len(narrative[:cursor].encode("utf-16-le")) // 2, "text": tail},
            "operands": [_operand(marker, index[marker], numbers[marker], precision)
                         for marker in markers],
        })
    return result


def render_narrative_presentation(
    dataset: dict[str, Any], catalogue: list[TrendObservation],
    selection: dict[str, list[str]], index: dict[str, dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], int, int, dict[str, Any]]:
    """Format only after validated selection; retain inline evidence for non-web exports.

    The renderer owns required/fallback ordering. Its callback records the exact chosen
    observations without copying that policy or parsing arbitrary model-authored prose.
    """
    code_narrative = render_observation_selection(catalogue, selection)
    precision = currency_precision_plan(code_narrative)
    selected: list[tuple[TrendObservation, str]] = []

    def display(item: TrendObservation) -> str:
        lead, separator, tail = item.markdown.partition(_OPERANDS_PREFIX)
        if item.section == "red_flags" and separator:
            # Older open tabs fold this original grammar before formatting it for display.
            # Keep the wire tail intact; modern clients use the exact span and display_value.
            rendered = compact_narrative_text(lead, precision) + separator + tail
        else:
            rendered = compact_narrative_text(item.markdown, precision)
        selected.append((item, rendered))
        return rendered

    formatted = render_observation_selection(catalogue, selection, render_item=display)
    narrative, citations, grounded, unverified = resolve_narrative_citations(formatted, index)
    numbers = {marker: n for n, marker in enumerate(dict.fromkeys(
        marker for marker in _MARKER.findall(formatted) if marker in index
    ), start=1)}
    # The code renderer emits canonical single markers. Enrichment happens after resolution,
    # leaving the general-purpose resolver and its legacy citation contract unchanged.
    for marker, number in numbers.items():
        citations[number - 1].update(marker=marker, unit=_display_unit(index[marker]),
                                     percent=bool(index[marker].get("percent")))
    presentation = {
        "format_version": NARRATIVE_FORMAT_VERSION, "snapshot_id": dataset.get("snapshot_id"),
        "data_notes_version": DATA_NOTES_VERSION, "offset_encoding": "utf-16",
        "notes": citation_data_notes(citations, resolve_data_notes(dataset)),
        "evidence": _evidence(selected, narrative, numbers, index, precision) if not unverified else [],
    }
    return narrative, citations, grounded, unverified, presentation
