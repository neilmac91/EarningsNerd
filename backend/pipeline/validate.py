from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .schema import FilingSummary, Financials, Liquidity, Metric

MATERIAL_DELTA_PCT = 0.03
MATERIAL_DELTA_ABS = 100_000_000


def compute_deltas(metric: Metric) -> Metric:
    if metric.current is None or metric.prior is None:
        metric.delta_abs = None
        metric.delta_pct = None
        return metric
    metric.delta_abs = metric.current - metric.prior
    if metric.prior != 0:
        metric.delta_pct = (metric.current - metric.prior) / abs(metric.prior)
    else:
        metric.delta_pct = None
    return metric


def _is_material(metric: Metric) -> bool:
    if metric.current is None or metric.prior is None:
        return False
    delta_abs = abs(metric.current - metric.prior)
    delta_pct = None
    if metric.prior:
        delta_pct = abs((metric.current - metric.prior) / abs(metric.prior))
    if metric.unit == "PCT":
        threshold_abs = MATERIAL_DELTA_PCT
    else:
        threshold_abs = MATERIAL_DELTA_ABS
    if delta_pct is not None and delta_pct >= MATERIAL_DELTA_PCT:
        return True
    if delta_abs >= threshold_abs:
        return True
    return False


def _iterate_metrics(financials: Financials, liquidity: Optional[Liquidity]) -> Iterable[Metric]:
    for metric in [
        financials.revenue,
        financials.gross_margin,
        financials.operating_income,
        financials.net_income,
        financials.eps_basic,
        financials.eps_diluted,
        financials.free_cash_flow,
    ]:
        if metric:
            yield metric
    if liquidity:
        for metric in [liquidity.cash, liquidity.debt, liquidity.current_ratio]:
            if metric:
                yield metric


def validate_summary(summary: FilingSummary) -> tuple[FilingSummary, Dict[str, object]]:
    """Apply materiality rules and drop empty sections.

    Returns the validated summary alongside pipeline metadata for the API layer.
    """

    material_metric_labels: List[str] = []
    has_prior = False
    for metric in _iterate_metrics(summary.financials, summary.liquidity):
        compute_deltas(metric)
        if metric.prior is not None:
            has_prior = True
        metric.material = _is_material(metric)
        if metric.material:
            material_metric_labels.append(metric.label)
        if metric.unit == "PCT" and metric.delta_abs is not None:
            # Ensure stored deltas remain as decimals
            metric.delta_abs = metric.delta_abs
    summary.financials.has_prior = has_prior

    # Drop liquidity section if empty
    if summary.liquidity:
        if not any([summary.liquidity.cash, summary.liquidity.debt, summary.liquidity.current_ratio]):
            summary.liquidity = None

    # Drop risks if empty
    if not summary.risks.items:
        summary.risks.items = []
        summary.risks.citations = []

    # Drop outlook if empty
    if not summary.outlook.guidance_summary and not summary.outlook.catalysts:
        summary.outlook.guidance_summary = None
        summary.outlook.catalysts = []

    summary_meta: Dict[str, object] = {
        "has_prior": has_prior,
        "material_metrics": material_metric_labels,
        "footnotes": [],
    }

    if summary.outlook.guidance_summary is None and summary.financials.has_prior is not None:
        summary_meta["footnotes"].append("Quantitative guidance not provided in this filing.")

    summary.sources = list({anchor for metric in _iterate_metrics(summary.financials, summary.liquidity) for anchor in (metric.source_anchors or [])})

    return summary, summary_meta
