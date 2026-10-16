"""The AI-timeout fallback labels money in the filer's reporting currency, by the primary path's rule.

``generate_xbrl_summary`` is the summary the pipeline persists when the AI step times out. Standardized
XBRL values are in the filer's reporting currency, so a hardcoded "$" turned a CNY filer's
CNY 941.2B revenue into "$941.2B" (about 7x too large), and the read path then matched the number
and served it as SEC-verified. The primary path's deterministic filler (``ai/markdown_render.py``)
already labelled these figures "CNY 941.2B"; both producers now share one rule, and the parity test
below fails if either drifts from the other.
"""
import copy
import json
from types import SimpleNamespace

import pytest

from app.services.fallback_summary import generate_xbrl_summary
from app.services.openai_service import openai_service
from app.services.provenance_service import build_metric_source


def _metrics(currency=None, **extra):
    metrics = {
        "revenue": {"current": {"value": 941_168_000_000.0, "period": "2025-03-31"},
                    "prior": {"value": 868_687_000_000.0, "period": "2024-03-31"}},
        "net_income": {"current": {"value": 12_480_000.0, "period": "2025-03-31"},
                       "prior": {"value": 950_000.0, "period": "2024-03-31"}},
        "earnings_per_share": {"current": {"value": 6.42, "period": "2025-03-31"},
                               "prior": {"value": -0.5, "period": "2024-03-31"}},
        **extra,
    }
    if currency is not None:
        metrics["reporting_currency"] = currency
    return metrics


def _table(out):
    return [(r["metric"], r["current_period"], r["prior_period"]) for r in out["financial_highlights"]["table"]]


def test_a_cny_filer_reads_in_cny_and_never_in_dollars():
    out = generate_xbrl_summary(_metrics("CNY"), "Example FPI Ltd", filing_type="20-F")

    assert "- **Revenue**: CNY 941.2B (Period: 2025-03-31)" in out["business_overview"]
    assert "- **Net Income**: CNY 12.5M (Period: 2025-03-31)" in out["business_overview"]
    assert _table(out) == [
        ("Revenue", "CNY 941.2B", "CNY 868.7B"),
        ("Net Income", "CNY 12.5M", "CNY 950,000"),
        ("EPS (Basic)", "CNY 6.42", "CNY -0.50"),
    ]
    # The persisted v2 table is the same object; no "$" anywhere in what the pipeline stores.
    assert out["raw_summary"]["sections"]["results_that_matter"] is out["financial_highlights"]
    assert "$" not in json.dumps(out)


def test_a_eur_filer_eps_cells_carry_no_dollar_sign():
    out = generate_xbrl_summary(_metrics("EUR"), "Example SE", filing_type="20-F")

    eps_row = out["financial_highlights"]["table"][-1]
    assert (eps_row["metric"], eps_row["current_period"], eps_row["prior_period"]) == (
        "EPS (Basic)", "EUR 6.42", "EUR -0.50")
    assert "$" not in json.dumps(out)


USD_OVERVIEW = (
    "## Example Ltd 10-K Summary\n\n### Financial Snapshot (XBRL)\n"
    "- **Revenue**: $941.2B (Period: 2025-03-31)\n"
    "- **Net Income**: $12.5M (Period: 2025-03-31)\n"
    "- **EPS**: 6.42 (Period: 2025-03-31)\n\n"
    "_Click 'Regenerate Analysis' for the full AI-powered insights._"
)


@pytest.mark.parametrize("currency", [None, "USD", "usd"])
def test_usd_and_unlabelled_filers_keep_the_dollar_output_unchanged(currency):
    out = generate_xbrl_summary(_metrics(currency), "Example Ltd", "2025-06-01", filing_type="10-K")

    # Pinned from main before the fix: a domestic filer's fallback is byte-identical.
    assert out["business_overview"] == USD_OVERVIEW
    assert _table(out) == [
        ("Revenue", "$941.2B", "$868.7B"),
        ("Net Income", "$12.5M", "$950,000"),
        ("EPS (Basic)", "$6.42", "$-0.50"),
    ]
    unlabelled = generate_xbrl_summary(_metrics(), "Example Ltd", "2025-06-01", filing_type="10-K")
    assert out == unlabelled


@pytest.mark.parametrize("currency", [None, "USD", "usd", "EUR", "CNY", "jpy"])
def test_the_fallback_labels_money_by_the_primary_path_rule(currency):
    """Rule 12 gate: one money-label rule for both producers of a summary's P&L figures."""
    metrics = _metrics(currency)
    sections: dict = {}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, copy.deepcopy(metrics))
    primary = {r["metric"].lower(): (r["current_period"], r["prior_period"])
               for r in sections["results_that_matter"]["table"]}

    fallback = generate_xbrl_summary(metrics, "X", filing_type="20-F")
    revenue = fallback["financial_highlights"]["table"][0]

    assert (revenue["current_period"], revenue["prior_period"]) == primary["revenue"]


def test_the_read_path_verifies_the_relabelled_figure():
    """GET /api/summaries/filing/{id} matches the number only; the verified chip now sits on a figure
    whose label is the filer's own currency."""
    metrics = _metrics("CNY")
    row = generate_xbrl_summary(metrics, "Example FPI Ltd", filing_type="20-F")["financial_highlights"]["table"][0]
    filing = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/1/000000000025000001/",
                             sec_url=None)

    source = build_metric_source(row, filing, metrics, "Standardized XBRL financial data")

    assert row["current_period"] == "CNY 941.2B"
    assert source["source_verified"] is True
