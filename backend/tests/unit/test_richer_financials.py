"""Unit tests for roadmap 2.6 (Phase A): richer cited financials.

Covers the *standardization* and *normalization* layers (the extraction layer — that the new
INSTANT/DURATION concepts are only pulled behind ``RICHER_FINANCIALS_ENABLED`` — is proved in
``test_accession_xbrl_extraction.py::test_richer_financials_extracted_only_behind_the_flag``).

These tests are pure/offline and prove:
  1. ``extract_standardized_metrics`` surfaces the new statement lines (investing/financing CF,
     current assets/liabilities) and derives working_capital + current_ratio per period.
  2. The derived liquidity ratios self-gate (no working_capital/current_ratio without BOTH
     current assets and current liabilities), so a flag-off filing carries none of them.
  3. The normalizer assigns the right units (USD for the statement lines, ``pure`` for the
     ratio) and the reconciliation gate treats the new balance-sheet totals as non-negative.
"""

from datetime import date

from app.services import facts_service as svc
from app.services.edgar.xbrl_service import edgar_xbrl_service


def _line(period, value, *, form="10-K", currency=None):
    return {"period": period, "value": value, "form": form, "currency": currency}


def _richer_xbrl_data():
    """Two annual periods with the full cash-flow + working-capital lines (as the flagged
    extraction would emit them). 2024 is the latest period."""
    return {
        "current_assets": [_line("2024-09-28", 300_000.0), _line("2023-09-30", 250_000.0)],
        "current_liabilities": [_line("2024-09-28", 120_000.0), _line("2023-09-30", 125_000.0)],
        "investing_cash_flow": [_line("2024-09-28", -15_000.0), _line("2023-09-30", -9_000.0)],
        "financing_cash_flow": [_line("2024-09-28", -40_000.0), _line("2023-09-30", -30_000.0)],
    }


class TestStandardize:
    def test_surfaces_new_statement_lines(self):
        metrics = edgar_xbrl_service.extract_standardized_metrics(_richer_xbrl_data())
        for key in ("current_assets", "current_liabilities", "investing_cash_flow", "financing_cash_flow"):
            assert key in metrics, f"{key} missing"
            assert metrics[key]["current"]["value"] is not None
        # the investing/financing flows can be (and here are) negative — surfaced unchanged
        assert metrics["investing_cash_flow"]["current"]["value"] == -15_000.0
        assert metrics["financing_cash_flow"]["current"]["value"] == -40_000.0

    def test_derives_working_capital_and_current_ratio_per_period(self):
        metrics = edgar_xbrl_service.extract_standardized_metrics(_richer_xbrl_data())
        # assert via the per-period series (avoids current/prior ordering assumptions)
        wc = {p["period"]: p["value"] for p in metrics["working_capital"]["series"]}
        cr = {p["period"]: p["value"] for p in metrics["current_ratio"]["series"]}
        assert wc["2024-09-28"] == 180_000.0  # 300k − 120k
        assert wc["2023-09-30"] == 125_000.0  # 250k − 125k
        assert cr["2024-09-28"] == 2.5         # 300k ÷ 120k
        assert cr["2023-09-30"] == 2.0         # 250k ÷ 125k

    def test_liquidity_self_gates_without_current_liabilities(self):
        # current_assets present but current_liabilities absent → no derived liquidity at all.
        data = {"current_assets": [_line("2024-09-28", 300_000.0)]}
        metrics = edgar_xbrl_service.extract_standardized_metrics(data)
        assert "current_assets" in metrics
        assert "working_capital" not in metrics
        assert "current_ratio" not in metrics

    def test_no_derived_liquidity_from_negative_components(self):
        # A negative current-assets/liabilities total is a parse error (the base fact is hard-rejected
        # by reconcile). The derived metrics run BEFORE reconcile and aren't all non-negative, so guard
        # them at the source: a corrupt component must not persist an invalid working_capital / a
        # physically-impossible negative current_ratio.
        data = {
            "current_assets": [_line("2024-09-28", -300_000.0)],
            "current_liabilities": [_line("2024-09-28", 120_000.0)],
        }
        metrics = edgar_xbrl_service.extract_standardized_metrics(data)
        assert "working_capital" not in metrics
        assert "current_ratio" not in metrics

    def test_current_ratio_skips_period_with_zero_liabilities(self):
        # A zero-liabilities period must not divide-by-zero; working_capital still computes.
        data = {
            "current_assets": [_line("2024-09-28", 300_000.0)],
            "current_liabilities": [_line("2024-09-28", 0.0)],
        }
        metrics = edgar_xbrl_service.extract_standardized_metrics(data)
        assert metrics["working_capital"]["current"]["value"] == 300_000.0
        assert "current_ratio" not in metrics  # no period survived the divide-by-zero guard

    def test_absent_when_no_richer_data(self):
        # A "flag-off" filing (none of the 2.6 lines extracted) carries none of the new metrics.
        metrics = edgar_xbrl_service.extract_standardized_metrics(
            {"revenue": [_line("2024-09-28", 391_035_000_000.0)]}
        )
        for key in ("current_assets", "current_liabilities", "investing_cash_flow",
                    "financing_cash_flow", "working_capital", "current_ratio"):
            assert key not in metrics


class TestNormalizeUnits:
    def test_new_concepts_get_correct_units(self):
        standardized = edgar_xbrl_service.extract_standardized_metrics(_richer_xbrl_data())
        facts = svc.normalize_standardized_to_facts(
            1, 10, "0000320193-24-000123", "10-K", standardized
        )
        by_concept = {}
        for f in facts:
            by_concept.setdefault(f["concept"], f)
        assert by_concept["current_assets"]["unit"] == "USD"
        assert by_concept["current_liabilities"]["unit"] == "USD"
        assert by_concept["investing_cash_flow"]["unit"] == "USD"
        assert by_concept["financing_cash_flow"]["unit"] == "USD"
        assert by_concept["working_capital"]["unit"] == "USD"
        assert by_concept["current_ratio"]["unit"] == "pure"


def _gatefact(concept, value, period_end=date(2024, 9, 28)):
    return {
        "company_id": 1,
        "filing_id": None,
        "concept": concept,
        "unit": "USD",
        "period_end": period_end,
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "value": value,
        "form": "10-K",
        "accession": "ACC",
        "source": "edgar_xbrl",
    }


class TestReconcileGate:
    def test_negative_current_assets_hard_rejected(self):
        # A current-assets total can't be negative — that's a parse error, not a datum. Reject it.
        # The investing cash flow on the same period legitimately can be negative — keep it.
        accepted, rejected = svc.reconcile_facts(
            [_gatefact("current_assets", -5.0), _gatefact("investing_cash_flow", -2.0)]
        )
        assert [f["concept"] for f in rejected] == ["current_assets"]
        assert [f["concept"] for f in accepted] == ["investing_cash_flow"]

    def test_negative_current_liabilities_hard_rejected(self):
        accepted, rejected = svc.reconcile_facts([_gatefact("current_liabilities", -1.0)])
        assert [f["concept"] for f in rejected] == ["current_liabilities"]
        assert accepted == []

    def test_negative_current_ratio_hard_rejected(self):
        # A current ratio is current_assets ÷ current_liabilities — both non-negative — so it can
        # never be negative. Defense-in-depth: hard-reject if one ever slips through.
        accepted, rejected = svc.reconcile_facts([_gatefact("current_ratio", -1.5)])
        assert [f["concept"] for f in rejected] == ["current_ratio"]
        assert accepted == []

    def test_negative_financing_cash_flow_kept(self):
        # Financing outflows (buybacks, debt repayment, dividends) are routinely negative — keep.
        accepted, rejected = svc.reconcile_facts([_gatefact("financing_cash_flow", -50_000.0)])
        assert rejected == []
        assert accepted[0]["reconciled"] is True
