from backend.pipeline.schema import Financials, FilingSummary, Liquidity, Metric, Outlook, Risks
from backend.pipeline.schema import Financials, FilingSummary, Liquidity, Metric, Outlook, Risks
from backend.pipeline.validate import validate_summary


def _summary_with_missing_prior() -> FilingSummary:
    financials = Financials(
        revenue=Metric(label="Revenue", unit="USD", current=1_000_000_000, prior=None),
        gross_margin=None,
        operating_income=None,
        net_income=None,
        eps_basic=None,
        eps_diluted=None,
        free_cash_flow=None,
    )
    liquidity = Liquidity()
    return FilingSummary(
        cik="0000000000",
        symbol="TEST",
        company_name="Test Corp",
        filing_type="10-Q",
        filing_date="2025-05-02",
        period_end="2025-03-29",
        financials=financials,
        liquidity=liquidity,
        risks=Risks(),
        outlook=Outlook(),
        sources=[],
    )


def test_missing_prior_sets_has_prior_false_and_no_deltas():
    summary = _summary_with_missing_prior()
    validated, meta = validate_summary(summary)
    assert validated.financials.has_prior is False
    assert validated.financials.revenue.delta_abs is None
    assert validated.financials.revenue.delta_pct is None
    assert meta["has_prior"] is False
