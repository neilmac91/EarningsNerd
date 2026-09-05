"""Deterministic bank-revenue guards for AI-authored financial highlights (roadmap S2 façade split).

A financial institution that reports no single revenue line must not have an LLM-synthesized
"Revenue" row persisted or rendered. These helpers make that guarantee deterministic (the grounding
directive that asks the model not to do it is only advisory). Extracted verbatim from
``openai_service`` and re-exported there for existing callers.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.ai.fi_signals import fi_components_present

logger = logging.getLogger(__name__)


def _is_no_total_bank(xbrl_metrics: Optional[dict]) -> bool:
    """True when the filer is a bank that reports NO single revenue line — i.e. the standardized
    metrics carry net/non-interest income components but NO populated ``revenue`` total. This is the
    only case where an LLM-authored single "Revenue" row is illegitimate (a bank WITH a reported
    total, e.g. JPM, keeps ``revenue`` populated, so its row is legitimate and left alone)."""
    if not isinstance(xbrl_metrics, dict):
        return False
    has_components = fi_components_present(xbrl_metrics)
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


def ground_bank_component_rows(financial_section: Any, xbrl_metrics: Optional[dict]) -> Any:
    """Own available component rows from same-period, same-currency filing XBRL.

    Replace model component rows completely: their commentary/evidence may describe different
    figures. A machine-authored row has XBRL provenance, never an invented verbatim SEC quote.
    Keep legitimate totals and unrelated analysis. Reapplying this function is idempotent.
    """
    import math
    from datetime import date
    from app.services.provenance_service import map_metric_to_xbrl_key

    if not fi_components_present(xbrl_metrics):
        return financial_section
    currency = str(xbrl_metrics.get("reporting_currency") or "USD").upper()

    def point(key: str, which: str) -> Optional[dict]:
        metric = xbrl_metrics.get(key)
        item = metric.get(which) if isinstance(metric, dict) else None
        if not isinstance(item, dict):
            return None
        value = item.get("value")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            return None
        try:
            date.fromisoformat(item.get("period", ""))
        except (TypeError, ValueError):
            return None
        if str(item.get("currency") or currency).upper() != currency:
            return None
        return item

    # Prefer the filing's reported total/income period; component-only banks anchor on their
    # available component. Never juxtapose a stale component with a newer headline period.
    anchor_key = next((key for key in (
        "revenue", "net_income", "net_interest_income", "noninterest_income"
    ) if point(key, "current") is not None), None)
    if anchor_key is None:
        return financial_section
    current_period = point(anchor_key, "current")["period"]
    prior_anchor = point(anchor_key, "prior")
    prefix = "$" if currency == "USD" else f"{currency} "

    def display(item: dict) -> str:
        # Exact values retain small/negative components and avoid precision loss near rounding
        # boundaries; read-time provenance verifies these against the same standardized concept.
        return f"{prefix}{item['value']:,.0f} ({item['period']})"

    rows = []
    replaced = set()
    for key, label in (("net_interest_income", "Net Interest Income"),
                       ("noninterest_income", "Non-Interest Income")):
        current = point(key, "current")
        if current is None or current["period"] != current_period:
            continue
        prior = point(key, "prior")
        if not (prior and prior_anchor and prior["period"] == prior_anchor["period"]
                and prior["period"] < current_period):
            prior = None
        rows.append({
            "metric": label, "current_period": display(current),
            "prior_period": display(prior) if prior else "", "change": "",
            "commentary": "", "supporting_evidence": "",
            "source_basis": "standardized_xbrl", "raw_tag": current.get("raw_tag"),
            "period_end": current_period, "currency": currency,
        })
        replaced.add(key)
    if not rows:
        return financial_section
    section = financial_section if isinstance(financial_section, dict) else {}
    existing = section.get("table")
    existing = existing if isinstance(existing, list) else []
    kept = []
    for row in existing:
        mapped = map_metric_to_xbrl_key(row.get("metric")) if isinstance(row, dict) else None
        if not mapped or mapped[0] not in replaced:
            kept.append(row)
    return {**section, "table": rows + kept}
