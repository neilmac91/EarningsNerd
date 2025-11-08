import pathlib

import pytest

from backend.pipeline.extract import extract_ixbrl_metrics
from backend.pipeline.validate import validate_summary

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "aapl-20250329.htm"


def test_extracts_key_metrics_from_ixbrl():
    html = FIXTURE.read_text()
    summary = extract_ixbrl_metrics(
        html,
        cik="0000320193",
        symbol="AAPL",
        company_name="Apple Inc.",
        filing_type="10-Q",
        filing_date="2025-05-02",
        period_end="2025-03-29",
    )
    assert summary.financials.revenue is not None
    assert summary.financials.revenue.current == pytest.approx(94_836_000_000)
    assert summary.financials.revenue.prior == pytest.approx(90_753_000_000)

    assert summary.financials.net_income is not None
    assert summary.financials.net_income.current == pytest.approx(25_903_000_000)
    assert summary.financials.net_income.prior == pytest.approx(24_160_000_000)

    assert summary.financials.eps_diluted is not None
    assert summary.financials.eps_diluted.current == pytest.approx(1.65)
    assert summary.financials.eps_diluted.prior == pytest.approx(1.52)


def test_validation_sets_has_prior_and_material_flags():
    html = FIXTURE.read_text()
    summary = extract_ixbrl_metrics(
        html,
        cik="0000320193",
        symbol="AAPL",
        company_name="Apple Inc.",
        filing_type="10-Q",
        filing_date="2025-05-02",
        period_end="2025-03-29",
    )
    validated, meta = validate_summary(summary)
    assert validated.financials.has_prior is True
    assert any(metric.material for metric in [
        validated.financials.revenue,
        validated.financials.net_income,
        validated.financials.eps_diluted,
    ] if metric)
    assert meta["has_prior"] is True
