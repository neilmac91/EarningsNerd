"""Advisory replay of the production figure tracer on actual v2 prose, with honest availability."""
from __future__ import annotations

import math
import statistics

from app.services.ai.figure_trace import excerpt_values, untraceable_figures, xbrl_values


def measure_figures(summary: dict, xbrl: dict, excerpt: str) -> dict:
    raw = summary.get("raw_summary")
    sections = raw.get("sections") if isinstance(raw, dict) else None
    if not isinstance(sections, dict) or not sections:
        return {"status": "unavailable", "reason": "raw v2 sections missing", "count": None, "figures": []}
    values = xbrl_values(xbrl) + excerpt_values(excerpt)
    if not any(math.isfinite(value) for value in values):
        return {"status": "unavailable", "reason": "numeric grounding missing", "count": None, "figures": []}
    figures = untraceable_figures(sections, xbrl, excerpt)
    return {"status": "measured", "reason": "", "count": len(figures), "figures": figures}


def summarize_figures(results: list[dict]) -> dict:
    measured = [r["figure_trace"]["count"] for r in results
                if not r.get("error") and (r.get("figure_trace") or {}).get("status") == "measured"]
    errors = sum(bool(r.get("error")) for r in results)
    return {
        "mean_untraceable_dollar_figures": round(statistics.mean(measured), 4) if measured else None,
        "figure_trace_measured": len(measured),
        "figure_trace_unavailable": len(results) - len(measured) - errors,
        "figure_trace_errors": errors,
    }
