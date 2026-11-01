"""Unit tests for the A5 "What Changed" change-report service (pure logic)."""

from types import SimpleNamespace
from datetime import datetime

import pytest

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

    def test_global_best_first_beats_list_order_greedy(self):
        # cur[0] matches the prior at ~0.6; cur[1] matches it at 1.0. A naive list-order greedy would
        # let cur[0] consume the prior and mark the stronger cur[1] "new". Global best-first must pair
        # the prior with cur[1] and leave the weaker cur[0] as the "new" one.
        current = [
            {"title": "Supply chain constraints overview"},
            {"title": "Supply chain constraints and logistics"},
        ]
        prior = [{"title": "Supply chain constraints and logistics"}]
        out = svc.diff_risk_factors(current, prior)
        assert out["carried_count"] == 1
        assert out["resolved"] == []
        assert out["new"] == ["Supply chain constraints overview"]

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
        assert out["risks"] is None
        # T1.6: key_changes is deprecated — no longer surfaced (the lead is metrics.headline).
        assert out["key_changes"] is None
        assert out["has_changes"] is True
        # The Item 1A wording diff is a separate block, null unless the caller supplies one.
        assert out["section_changes"] is None

    def test_no_prior_filing_has_no_risks_and_marks_no_prior(self):
        current_summary = SimpleNamespace(risk_factors=[{"title": "x risk"}], raw_summary=None, key_changes=None)
        out = svc.assemble_report(self.CURRENT_FILING, None, current_summary, None)
        assert out["has_prior"] is False
        assert out["prior_filing"] is None
        assert out["risks"] is None  # cannot diff without a prior summary
        # metrics may still come from the current filing's in-instance comparative (none here)
        assert out["has_changes"] in (True, False)

    def test_reporting_currency_labels_the_raw_amounts(self):
        # The items carry raw XBRL amounts in the filer's own currency: a yen filer's report must say
        # JPY so the client never prints its amounts as dollars.
        yen = SimpleNamespace(**{**vars(self.CURRENT_FILING), "filing_type": "20-F",
                                 "xbrl_data": {**self.CURRENT_FILING.xbrl_data, "reporting_currency": "jpy"}})
        assert svc.assemble_report(yen, self.PRIOR_FILING, None, None)["reporting_currency"] == "JPY"
        rmb = SimpleNamespace(**{**vars(yen), "xbrl_data": {**yen.xbrl_data, "reporting_currency": "RMB"}})
        assert svc.assemble_report(rmb, None, None, None)["reporting_currency"] == "CNY"

    def test_a_prior_filing_in_another_currency_never_supplies_the_prior_amount(self):
        # reporting_currency labels both columns with the current filing's currency, so a prior filed
        # in another currency is not differenced. These series hold no comparative of their own, so
        # nothing is compared at all.
        eur = SimpleNamespace(**{**vars(self.CURRENT_FILING), "filing_type": "20-F",
                                 "xbrl_data": {**self.CURRENT_FILING.xbrl_data, "reporting_currency": "EUR"}})
        usd_prior = SimpleNamespace(**{**vars(self.PRIOR_FILING), "filing_type": "20-F",
                                       "xbrl_data": {**self.PRIOR_FILING.xbrl_data, "reporting_currency": "USD"}})
        out = svc.assemble_report(eur, usd_prior, None, None)
        assert out["reporting_currency"] == "EUR"
        assert out["metrics"] is None and out["has_changes"] is False
        eur_prior = SimpleNamespace(**{**vars(usd_prior), "xbrl_data": {**usd_prior.xbrl_data, "reporting_currency": "EUR"}})
        rev = next(i for i in svc.assemble_report(eur, eur_prior, None, None)["metrics"]["items"]
                   if i["metric"] == "revenue")
        assert (rev["prior"], rev["current"]) == (80.0, 100.0)

    def test_reporting_currency_is_none_when_unknown_or_malformed(self):
        assert svc.assemble_report(self.CURRENT_FILING, None, None, None)["reporting_currency"] is None
        for bad in ("", "US Dollars", "USD/shares", "pure", 840, None):
            filing = SimpleNamespace(**{**vars(self.CURRENT_FILING),
                                        "xbrl_data": {**self.CURRENT_FILING.xbrl_data, "reporting_currency": bad}})
            assert svc.assemble_report(filing, None, None, None)["reporting_currency"] is None, bad
        no_xbrl = SimpleNamespace(id=5, filing_type="10-K", filing_date=None, period_end_date=None, xbrl_data=None)
        assert svc.assemble_report(no_xbrl, None, None, None)["reporting_currency"] is None

    def test_10k_is_year_over_year(self):
        cf = SimpleNamespace(id=5, filing_type="10-K", filing_date=None, period_end_date=None, xbrl_data=None)
        out = svc.assemble_report(cf, None, None, None)
        assert out["comparison_basis"] == "Year over year"
        assert out["has_changes"] is False

    def test_key_changes_is_deprecated_and_always_none(self):
        # T1.6: key_changes is deprecated-in-place — never surfaced as the What-changed lead, even
        # when the summary carries a real narrative (the lead is now the deterministic headline).
        cs = SimpleNamespace(risk_factors=[], raw_summary=None, key_changes="Revenue accelerated materially.")
        out = svc.assemble_report(self.CURRENT_FILING, None, cs, None)
        assert out["key_changes"] is None

    def test_model_risks_are_omitted_from_change_report(self):
        current_summary = SimpleNamespace(
            risk_factors=None,
            raw_summary={"sections": {"risk_factors": [{"title": "Raw-section sourced risk"}]}},
            key_changes=None,
        )
        prior_summary = SimpleNamespace(risk_factors=[], raw_summary=None, key_changes=None)
        out = svc.assemble_report(self.CURRENT_FILING, self.PRIOR_FILING, current_summary, prior_summary)
        assert out["risks"] is None


def test_comparison_basis_covers_fpi_forms():
    """Phase 4/5: FPI forms get a basis label too (20-F/40-F annual; 6-K semi-annual interim)."""
    from app.services.change_report_service import _comparison_basis

    assert _comparison_basis("10-K") == "Year over year"
    assert _comparison_basis("10-Q") == "Quarter over quarter"
    assert _comparison_basis("20-F") == "Year over year"
    assert _comparison_basis("40-F") == "Year over year"
    assert _comparison_basis("6-K") == "Period over period"
    # Amended forms normalize to their base label.
    assert _comparison_basis("20-F/A") == "Year over year"
    assert _comparison_basis("6-K/A") == "Period over period"
    # Genuinely unknown forms still have no basis.
    assert _comparison_basis("S-1") is None


# --------------------------------------------------------------------------- E261: one comparison period per report
# Every What changed line compares the filing's own period with the one period the basis line names: the prior
# filing's period of report ("against the 10-Q for the quarter ended ..."), or with no prior filing the year before
# where the basis reads "Year over year", and nothing where it does not.

def _lines(*pairs, form="10-Q"):
    return [{"period": p, "value": v, "form": form, "accn": "x"} for p, v in pairs]


def _filing(fid, form, period_end, xbrl):
    return SimpleNamespace(id=fid, filing_type=form, filing_date=datetime(2027, 1, 1),
                           period_end_date=datetime.fromisoformat(period_end) if period_end else None, xbrl_data=xbrl)


def _compared(report):
    """(metric, prior, current) for each line, or None when the report compares nothing."""
    metrics = report["metrics"]
    return None if metrics is None else [(i["metric"], i["prior"], i["current"]) for i in metrics["items"]]


# A 10-Q for the quarter ended 2026-06-30 as the instance extractor stores it: each series holds the quarter and its
# year-ago comparative. Its prior 10-Q is for the quarter ended 2026-03-31.
_Q2 = {
    "revenue": _lines(("2026-06-30", 110.0), ("2025-06-30", 90.0)),
    "net_income": _lines(("2026-06-30", 12.0), ("2025-06-30", 8.0)),
    "earnings_per_share": _lines(("2026-06-30", 1.02), ("2025-06-30", 0.81)),
    "eps_diluted": _lines(("2026-06-30", 1.00), ("2025-06-30", 0.80)),
}
_Q1 = {
    "revenue": _lines(("2026-03-31", 100.0)),
    "net_income": _lines(("2026-03-31", 10.0)),
    "earnings_per_share": _lines(("2026-03-31", 0.92)),
    "eps_diluted": _lines(("2026-03-31", 0.90)),
}


class TestOneComparisonPeriod:
    def test_a_quarter_compares_the_prior_quarter_or_nothing(self):
        current = _filing(2, "10-Q", "2026-06-30", _Q2)
        # The prior 10-Q was never summarized, so it has no stored XBRL. This filing's own comparatives are the
        # year-ago quarter, never the quarter ended Mar 31 the basis line names, so nothing is compared.
        report = svc.assemble_report(current, _filing(1, "10-Q", "2026-03-31", None), None, None)
        assert report["comparison_basis"] == "Quarter over quarter" and report["prior_filing"]["filing_id"] == 1
        assert _compared(report) is None and report["has_changes"] is False
        # No prior filing: "Quarter over quarter" still names the quarter before, which a 10-Q never reports.
        assert _compared(svc.assemble_report(current, None, None, None)) is None
        # With the prior quarter's figures, every line compares the quarter ended Mar 31.
        assert _compared(svc.assemble_report(current, _filing(1, "10-Q", "2026-03-31", _Q1), None, None)) == [
            ("revenue", 100.0, 110.0), ("net_income", 10.0, 12.0), ("eps_diluted", 0.90, 1.00),
        ]

    def test_a_quarter_shows_only_the_lines_its_prior_quarter_reports(self):
        # The prior blob holds revenue only. Net income used to take the year-ago quarter beside revenue against the
        # prior quarter; now it is withheld, and nothing is marked partial, since no figure was distrusted.
        prior = _filing(1, "10-Q", "2026-03-31", {"revenue": _Q1["revenue"]})
        report = svc.assemble_report(_filing(2, "10-Q", "2026-06-30", _Q2), prior, None, None)
        assert _compared(report) == [("revenue", 100.0, 110.0)] and report["metrics"]["data_quality"] == "ok"

    def test_the_prior_period_is_the_date_the_basis_line_prints(self):
        # The prior row says Mar 31, but its stored XBRL holds only an older quarter: nothing is that quarter.
        current = _filing(2, "10-Q", "2026-06-30", _Q2)
        stale = _filing(1, "10-Q", "2026-03-31", {"revenue": _lines(("2025-12-31", 95.0))})
        assert _compared(svc.assemble_report(current, stale, None, None)) is None
        # A line whose prior figure is for another quarter is withheld beside one that matches.
        mixed = _filing(1, "10-Q", "2026-03-31", {"revenue": _Q1["revenue"], "net_income": _lines(("2025-12-31", 9.0))})
        assert _compared(svc.assemble_report(current, mixed, None, None)) == [("revenue", 100.0, 110.0)]

    def test_an_annual_companyfacts_blob_compares_its_year_never_its_quarterly_note(self):
        # A companyfacts 10-K blob keeps its quarterly-data note's quarters between its years (parse_company_facts
        # keeps the five newest period ends). "Year over year" compares FY2025 with FY2024, with or without a prior
        # 10-K, never with the third quarter.
        k = {
            "revenue": _lines(("2025-12-31", 400.0), ("2025-09-30", 105.0), ("2025-06-30", 100.0),
                              ("2025-03-31", 95.0), ("2024-12-31", 360.0), form="10-K"),
            "net_income": _lines(("2025-12-31", 40.0), ("2025-09-30", 11.0), ("2025-06-30", 10.0),
                                 ("2025-03-31", 9.0), ("2024-12-31", 36.0), form="10-K"),
        }
        current = _filing(4, "10-K", "2025-12-31", k)
        for prior in (_filing(3, "10-K", "2024-12-31", None), None):
            assert _compared(svc.assemble_report(current, prior, None, None)) == [
                ("revenue", 360.0, 400.0), ("net_income", 36.0, 40.0),
            ], prior

    def test_a_period_of_report_matches_its_context_end_a_few_days_apart(self):
        # A period of report and an XBRL context can name one period end a few days apart (a 52/53-week calendar;
        # DRIFT_DAYS, as facts/filing_scope.py allows). A Sep 30 period of report matches a Sep 28 context ...
        current = _filing(4, "10-K", "2025-09-27", {"revenue": _lines(("2025-09-27", 400.0), ("2024-09-28", 360.0), form="10-K")})
        assert _compared(svc.assemble_report(current, _filing(3, "10-K", "2024-09-30", None), None, None)) == [
            ("revenue", 360.0, 400.0),
        ]
        # ... and a 10-Q whose prior blob is dated 3 days off its period of report still compares.
        drifted = _filing(1, "10-Q", "2026-03-31", {"revenue": _lines(("2026-03-28", 100.0))})
        assert _compared(svc.assemble_report(_filing(2, "10-Q", "2026-06-30", _Q2), drifted, None, None)) == [
            ("revenue", 100.0, 110.0),
        ]
        # A prior period of report that the filing's own comparatives do not reach compares nothing.
        assert _compared(svc.assemble_report(current, _filing(3, "10-K", "2024-06-30", None), None, None)) is None

    @pytest.mark.parametrize("form", ["10-K", "10-K/A", "10-k", "20-F", "20-F/A", "40-F", "40-F/A", "10-Q", "10-Q/A",
                                      "6-K", "6-K/A", "8-K", "10-KT", "S-1", None])
    def test_with_no_prior_filing_its_own_prior_year_stands_in_only_under_year_over_year(self, form):
        # With no prior filing, a filing's own prior year stands in exactly where the basis reads "Year over year",
        # and nothing does anywhere else, so the basis line and the comparison never disagree.
        own_prior_year = {"revenue": _lines(("2025-12-31", 400.0), ("2024-12-31", 360.0), form=str(form))}
        report = svc.assemble_report(_filing(4, form, "2025-12-31", own_prior_year), None, None, None)
        assert (report["metrics"] is not None) is (report["comparison_basis"] == "Year over year")
