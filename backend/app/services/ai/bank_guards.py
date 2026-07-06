"""Deterministic bank-revenue guards for AI-authored financial highlights (roadmap S2 façade split).

A financial institution that reports no single revenue line must not have an LLM-synthesized
"Revenue" row persisted or rendered. These helpers make that guarantee deterministic (the grounding
directive that asks the model not to do it is only advisory). Extracted verbatim from
``openai_service`` and re-exported there for existing callers.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _is_no_total_bank(xbrl_metrics: Optional[dict]) -> bool:
    """True when the filer is a bank that reports NO single revenue line — i.e. the standardized
    metrics carry net/non-interest income components but NO populated ``revenue`` total. This is the
    only case where an LLM-authored single "Revenue" row is illegitimate (a bank WITH a reported
    total, e.g. JPM, keeps ``revenue`` populated, so its row is legitimate and left alone)."""
    if not isinstance(xbrl_metrics, dict):
        return False
    has_components = any(
        isinstance(xbrl_metrics.get(k), dict) for k in ("net_interest_income", "noninterest_income")
    )
    rev = xbrl_metrics.get("revenue")
    has_revenue = (
        isinstance(rev, dict)
        and isinstance(rev.get("current"), dict)
        and rev["current"].get("value") is not None
    )
    return has_components and not has_revenue


def _sanitize_bank_financial_highlights(
    financial_section: Any, xbrl_metrics: Optional[dict]
) -> Any:
    """Drop any LLM-authored highlights row that maps to a ``revenue`` metric when the filer is a
    no-total bank (:func:`_is_no_total_bank`). The AI is *asked* not to synthesize a single bank
    revenue (grounding directive), but that is advisory; this makes it deterministic so a conflated
    or fabricated number can never be persisted or rendered in prose. No-op for every other filer,
    and for banks that legitimately report a total (their ``revenue`` is populated → not a no-total
    bank → this returns the section untouched)."""
    if not isinstance(financial_section, dict) or not _is_no_total_bank(xbrl_metrics):
        return financial_section
    table = financial_section.get("table")
    if not isinstance(table, list):
        return financial_section
    # Local import avoids any import-time cycle; the mapper is the same one provenance uses, so the
    # generation guard and the read-time provenance net evolve together.
    from app.services.provenance_service import map_metric_to_xbrl_key

    kept = []
    for row in table:
        metric = row.get("metric") if isinstance(row, dict) else None
        mapped = map_metric_to_xbrl_key(metric)
        if mapped and mapped[0] == "revenue":
            logger.info("Dropped conflated bank 'revenue' highlights row: %r", metric)
            continue
        kept.append(row)
    return {**financial_section, "table": kept}
