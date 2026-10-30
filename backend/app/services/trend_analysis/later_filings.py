"""Where an analysis carries later-filing evidence: the places the data notes' later-filing line names (MPA WP5a, D8).

The backend twin of the page's ``laterFilingPlaces`` (``frontend/features/analysis/lib/laterFilings.ts``), for the
exports' line (WP5a-X). It reads the points the producer (``trend_analysis/first_reports.py``) gave evidence, not the
data notes envelope, so the line moves no data notes version and no notes digest, and it lives apart from
``data_notes.py``, whose words and letters that version holds. Both twins compute the places of every case in
``backend/tests/fixtures/analysis_later_filings.json``: ``tests/unit/test_later_filings.py`` here,
``frontend/tests/unit/later-filings.spec.tsx`` on the page.

- ``values``: the figures that carry their own ``first_reported``. They are reported figures (a calculated figure's
  evidence sits on its inputs), each opening a dialog that gives both filings.
- ``comparisons``: the YoY changes that read n/m across a change of basis, the ones that carry
  ``yoy_first_reported`` (null included: the n/m fired and the own reports give no growth); a sign change's n/m
  carries none.

Over the dataset's periods only, in series order, then period order.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.trend_analysis.formatting import NOT_MEANINGFUL


def _truthy(value: Any) -> bool:
    """JavaScript's truth, which the page's ``if (point.first_reported)`` reads: an object counts, even an empty one."""
    return isinstance(value, (dict, list)) or bool(value)


def later_filing_places(dataset: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    """The later-filing line's places: ``{"values": [...], "comparisons": [...]}``, each ``{concept, label, period}``."""
    places: dict[str, list[dict[str, str]]] = {"values": [], "comparisons": []}
    for series in dataset["series"]:
        points = {point["period"]: point for point in series["points"]}
        for period in dataset["periods"]:
            point = points.get(period["key"])
            if point is None:
                continue
            ref = {"concept": series["concept"], "label": series["label"], "period": period["key"]}
            if _truthy(point.get("first_reported")):
                places["values"].append(ref)
            if point.get("yoy") == NOT_MEANINGFUL and "yoy_first_reported" in point:
                places["comparisons"].append(dict(ref))
    return places
