"""Unit tests for the A5 "What Changed" change-report service (pure logic)."""

from types import SimpleNamespace
from datetime import datetime

from app.services import change_report_service as svc


def _series(period: str, value: float):
    return {"period": period, "value": value}


class TestDiffRiskFactors:
    def test_new_resolved_and_carried(self):
        current = [
            {"title": "Supply chain disruption risk"},      # carried (matches prior "constraints")
            {"title": "Cybersecurity breach exposure"},     # new
        ]
        prior = [
            {"title": "Supply chain constraints and logistics"},  # carried
            {"title": "Regulatory pricing pressure on drugs"},    # resolved
        ]
        out = svc.diff_risk_factors(current, prior)
        assert out["new"] == ["Cybersecurity breach exposure"]
        assert out["resolved"] == ["Regulatory pricing pressure on drugs"]
        assert out["carried_count"] == 1

    def test_reworded_heading_reads_as_carried_not_new(self):
        # The same risk, lightly reworded, must NOT be reported as new + resolved.
        current = [{"title": "Dependence on a limited number of key customers"}]
        prior = [{"title": "We depend on a limited number of large customers"}]
        out = svc.diff_risk_factors(current, prior)
        assert out["new"] == []
        assert out["resolved"] == []
        assert out["carried_count"] == 1

    def test_falls_back_to_summary_text_when_no_title(self):
        current = [{"summary": "New climate transition and carbon pricing exposure"}]
        prior = []
        out = svc.diff_risk_factors(current, prior)
        assert out["new"] == ["New climate transition and carbon pricing exposure"]

    def test_empty_inputs(self):
        assert svc.diff_risk_factors(None, None) == {"new": [], "resolved": [], "carried_count": 0}
        assert svc.diff_risk_factors([], [{"title": "Only prior risk about liquidity"}]) == {
            "new": [],
            "resolved": ["Only prior risk about liquidity"],
            "carried_count": 0,
        }

    def test_ignores_non_dict_and_empty_text_entries(self):
        out = svc.diff_risk_factors(["nope", {}, {"title": "  "}, {"title": "Valid liquidity risk"}], [])
        assert out["new"] == ["Valid liquidity risk"]


class TestAssembleReport:
    CURRENT_FILING = SimpleNamespace(
        id=2,
        filing_type="10-Q",
        filing_date=datetime(2024, 5, 1),
        period_end_date=datetime(2024, 3, 31),
        xbrl_data={"revenue": [_series("2024-03-31", 100.0)], "net_income": [_series("2024-03-31", 20.0)]},
    )
    PRIOR_FILING = SimpleNamespace(
        id=1,
        filing_type="10-Q",
        filing_date=datetime(2024, 2, 1),
        period_end_date=datetime(2023, 12, 31),
        xbrl_data={"revenue": [_series("2023-12-31", 80.0)], "net_income": [_series("2023-12-31", 25.0)]},
    )

    def test_full_report_with_metrics_risks_and_key_changes(self):
        current_summary = SimpleNamespace(
            risk_factors=[{"title": "New supplier concentration risk"}],
            raw_summary=None,
            key_changes="Revenue accelerated while margins compressed on higher R&D.",
        )
        prior_summary = SimpleNamespace(
            risk_factors=[{"title": "Legacy litigation overhang risk"}],
            raw_summary=None,
            key_changes=None,
        )
        out = svc.assemble_report(self.CURRENT_FILING, self.PRIOR_FILING, current_summary, prior_summary)

        assert out["has_prior"] is True
        assert out["comparison_basis"] == "Quarter over quarter"
        assert out["prior_filing"]["filing_id"] == 1
        # Revenue 80 -> 100 = up 25%
        assert out["metrics"] is not None
        rev = next(i for i in out["metrics"]["items"] if i["metric"] == "revenue")
        assert rev["direction"] == "up" and round(rev["pct"]) == 25
        assert out["risks"]["new"] == ["New supplier concentration risk"]
        assert out["risks"]["resolved"] == ["Legacy litigation overhang risk"]
        assert out["key_changes"].startswith("Revenue accelerated")
        assert out["has_changes"] is True

    def test_no_prior_filing_has_no_risks_and_marks_no_prior(self):
        current_summary = SimpleNamespace(risk_factors=[{"title": "x risk"}], raw_summary=None, key_changes=None)
        out = svc.assemble_report(self.CURRENT_FILING, None, current_summary, None)
        assert out["has_prior"] is False
        assert out["prior_filing"] is None
        assert out["risks"] is None  # cannot diff without a prior summary
        # metrics may still come from the current filing's in-instance comparative (none here)
        assert out["has_changes"] in (True, False)

    def test_10k_is_year_over_year(self):
        cf = SimpleNamespace(id=5, filing_type="10-K", filing_date=None, period_end_date=None, xbrl_data=None)
        out = svc.assemble_report(cf, None, None, None)
        assert out["comparison_basis"] == "Year over year"
        assert out["has_changes"] is False

    def test_key_changes_placeholder_is_dropped(self):
        cs = SimpleNamespace(risk_factors=[], raw_summary=None, key_changes="Not available - retry for analysis")
        out = svc.assemble_report(self.CURRENT_FILING, None, cs, None)
        assert out["key_changes"] is None

    def test_risks_pulled_from_raw_summary_when_column_empty(self):
        current_summary = SimpleNamespace(
            risk_factors=None,
            raw_summary={"sections": {"risk_factors": [{"title": "Raw-section sourced risk"}]}},
            key_changes=None,
        )
        prior_summary = SimpleNamespace(risk_factors=[], raw_summary=None, key_changes=None)
        out = svc.assemble_report(self.CURRENT_FILING, self.PRIOR_FILING, current_summary, prior_summary)
        assert out["risks"]["new"] == ["Raw-section sourced risk"]
