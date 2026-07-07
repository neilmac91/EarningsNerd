"""Shared financial-institution signals for the summary path (data-quality plan P0-2).

One predicate, three consumers — the bank grounding NOTE (``xbrl_narrative``), the deterministic
bank-revenue guard (``bank_guards``), and the quality verdict (``assess_quality``) — so the
instruction the model receives and the checks applied to its output can never drift apart again.
``provenance_service`` keeps its deliberately independent copy (documented there) to avoid
import coupling on the read path.
"""
from __future__ import annotations

from typing import Optional

# SIC band (finance/insurance/real estate). Kept as a LOCAL constant — importing it from
# edgar.instance_extractor would drag the whole edgar package into this deliberately light
# module. test_fi_predicate_single_source.py pins equality with instance_extractor's band so
# the two can never drift.
FINANCIAL_SIC_LOW, FINANCIAL_SIC_HIGH = 6000, 6799

FI_COMPONENT_KEYS = ("net_interest_income", "noninterest_income")


def fi_components_present(xbrl_metrics: Optional[dict]) -> bool:
    """True when the standardized metrics carry either bank revenue component (net interest
    income / noninterest income). The statement-financials extraction emits these for financial
    institutions only, so presence doubles as the runtime bank signal."""
    if not isinstance(xbrl_metrics, dict):
        return False
    return any(isinstance(xbrl_metrics.get(k), dict) for k in FI_COMPONENT_KEYS)


def is_financial_sic(sic: Optional[str]) -> bool:
    """SIC-band FI signal (6000-6799); safe on None/blank/garbage. Belt-and-braces alongside
    :func:`fi_components_present` — prod ``Company.sic`` is currently unpopulated, so this
    branch is dormant until a SIC backfill runs (P1-7's rollout)."""
    if sic in (None, ""):
        return False
    try:
        code = int(str(sic)[:4])
    except (TypeError, ValueError):
        return False
    return FINANCIAL_SIC_LOW <= code <= FINANCIAL_SIC_HIGH
