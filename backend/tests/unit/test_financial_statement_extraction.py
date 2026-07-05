"""Unit tests for financial-institution revenue via the as-reported income statement (filing 528).

These exercise the pure selection/classification logic in ``instance_extractor`` against fake
statement DataFrames shaped like edgartools' ``income_statement().to_dataframe(view='standard')``
output — no network, no edgartools import.
"""
import pandas as pd
import pytest

from app.services.edgar.instance_extractor import (
    extract_financial_statement_metrics,
    is_financial_institution,
    match_financial_profile,
    _period_marker,
    _statement_period_columns,
    _truthy_flag,
)

pytestmark = pytest.mark.unit

_PERIODS = ("2025-12-31 (FY)", "2024-12-31 (FY)", "2023-12-31 (FY)")


def _stmt_df(rows, periods=_PERIODS):
    """rows: dicts with concept, label, std, values(list), abstract, is_breakdown, dimension."""
    data = []
    for r in rows:
        rec = {
            "concept": r["concept"],
            "label": r.get("label", ""),
            "standard_concept": r.get("std"),
            "abstract": r.get("abstract", False),
            "is_breakdown": r.get("is_breakdown", False),
            "dimension": r.get("dimension", False),
        }
        vals = r.get("values", [None] * len(periods))
        for p, v in zip(periods, vals):
            rec[p] = v
        data.append(rec)
    return pd.DataFrame(data)


class _FakeStatement:
    def __init__(self, df, fail=False):
        self._df, self._fail = df, fail

    def to_dataframe(self, view=None):
        if self._fail:
            raise RuntimeError("statement render failed")
        return self._df


class _FakeStatements:
    def __init__(self, df, fail=False, no_stmt=False):
        self._df, self._fail, self._no = df, fail, no_stmt

    def income_statement(self):
        return None if self._no else _FakeStatement(self._df, self._fail)


class _FakeXBRL:
    def __init__(self, df=None, fail=False, no_stmt=False, raise_stmts=False):
        self._df, self._fail, self._no, self._raise = df, fail, no_stmt, raise_stmts

    @property
    def statements(self):
        if self._raise:
            raise RuntimeError("no statements attr")
        return _FakeStatements(self._df, self._fail, self._no)


class _FakeCompany:
    def __init__(self, is_fin=True, sic="6022", raise_fin=False):
        self._is_fin, self.sic, self._raise = is_fin, sic, raise_fin

    def is_financial_institution(self):
        if self._raise:
            raise RuntimeError("probe failed")
        return self._is_fin


_BANK_ROWS = [
    {"concept": "us-gaap_NoninterestIncomeAbstract", "label": "Non-interest income", "abstract": True},
    {"concept": "us-gaap_InterestIncomeExpenseNet", "label": "Net interest income",
     "std": "NetInterestIncome", "values": [303235000, 253084000, 222836000]},
    # Dimensional "Parent Company" variant of the same concept must be ignored.
    {"concept": "us-gaap_InterestIncomeExpenseNet", "label": "Parent Company", "dimension": True,
     "values": [-1294000, -1488000, -1000000]},
    {"concept": "us-gaap_NoninterestIncome", "label": "Total non-interest income",
     "std": "NonInterestIncome", "values": [11871000, 23829000, 20000000]},
    # The ASC-606 fee-income trap: a DIFFERENT concept, tagged standard_concept="Revenue".
    {"concept": "us-gaap_RevenueFromContractWithCustomerIncludingAssessedTax", "label": "Non-interest income",
     "std": "Revenue", "values": [11053000, 23936000, 19000000]},
    {"concept": "us-gaap_NetIncomeLoss", "label": "Net income", "std": "NetIncome",
     "values": [71098000, 66686000, 60000000]},
]


def test_bank_emits_components_and_suppresses_revenue():
    xb = _FakeXBRL(_stmt_df(_BANK_ROWS))
    result = extract_financial_statement_metrics(xb, _FakeCompany(sic="6022"), "6022", "10-K", "2025-12-31")
    assert result is not None
    key, metrics, suppress = result
    assert key == "bank"
    assert suppress == ("revenue",)
    assert set(metrics) == {"net_interest_income", "noninterest_income"}
    nii_series, nii_tag = metrics["net_interest_income"]
    assert nii_tag == "us-gaap:InterestIncomeExpenseNet"
    assert nii_series[0] == ("2025-12-31", 303235000.0)
    assert len(nii_series) == 3  # all three FY comparatives
    noni_series, noni_tag = metrics["noninterest_income"]
    assert noni_tag == "us-gaap:NoninterestIncome"
    assert noni_series[0] == ("2025-12-31", 11871000.0)


def test_insurer_emits_reported_total_and_components():
    rows = [
        {"concept": "us-gaap_PremiumsEarnedNet", "label": "Premiums", "std": "Revenue",
         "values": [49779000000, 47000000000, 45000000000]},
        {"concept": "us-gaap_PremiumsEarnedNet", "label": "Life insurance", "values": [31556000000, None, None]},
        {"concept": "us-gaap_NetInvestmentIncome", "label": "Net investment income", "std": "Revenue",
         "values": [22559000000, 21000000000, 20000000000]},
        {"concept": "us-gaap_Revenues", "label": "Total revenues", "std": "Revenue",
         "values": [77084000000, 72000000000, 70000000000]},
    ]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic="6311"), "6311", "10-K", "2025-12-31"
    )
    assert result is not None
    key, metrics, suppress = result
    assert key == "insurer"
    assert suppress == ()
    assert metrics["revenue"][0][0] == ("2025-12-31", 77084000000.0)
    assert metrics["revenue"][1] == "us-gaap:Revenues"
    assert metrics["premiums_earned"][0][0] == ("2025-12-31", 49779000000.0)
    assert metrics["net_investment_income"][0][0] == ("2025-12-31", 22559000000.0)


def test_bdc_uses_gross_investment_income_not_net():
    rows = [
        {"concept": "us-gaap_GrossInvestmentIncomeOperating", "label": "Total investment income",
         "std": "NonoperatingIncomeExpense", "values": [3052000000, 2800000000, 2500000000]},
        # Net investment income is misleadingly tagged standard_concept="Revenue" — must NOT win.
        {"concept": "us-gaap_NetInvestmentIncome", "label": "Net investment income", "std": "Revenue",
         "values": [1458000000, 1400000000, 1300000000]},
    ]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic=None), None, "10-K", "2025-12-31"
    )
    assert result is not None
    key, metrics, _ = result
    assert key == "bdc"
    assert metrics["revenue"][0][0] == ("2025-12-31", 3052000000.0)
    assert metrics["revenue"][1] == "us-gaap:GrossInvestmentIncomeOperating"


def test_asset_manager_picks_total_revenue_row_over_disaggregation():
    rows = [
        {"concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "label": "Total revenue",
         "std": "Revenue", "values": [24216000000, 22000000000, 20000000000]},
        {"concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "label": "Advisory fees",
         "values": [18474000000, None, None]},
        {"concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "label": "Performance fees",
         "values": [1424000000, None, None]},
    ]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic="6211"), "6211", "10-K", "2025-12-31"
    )
    assert result is not None
    key, metrics, _ = result
    assert key == "financial_generic"
    assert metrics["revenue"][0][0] == ("2025-12-31", 24216000000.0)


def test_non_financial_returns_none():
    xb = _FakeXBRL(_stmt_df([
        {"concept": "us-gaap_Revenues", "label": "Total revenue", "std": "Revenue", "values": [1, 2, 3]},
    ]))
    assert extract_financial_statement_metrics(xb, _FakeCompany(is_fin=False, sic="3571"), "3571",
                                               "10-K", "2025-12-31") is None


def test_statement_render_failure_falls_back_to_none():
    xb = _FakeXBRL(_stmt_df(_BANK_ROWS), fail=True)
    assert extract_financial_statement_metrics(xb, _FakeCompany(sic="6022"), "6022", "10-K",
                                               "2025-12-31") is None
    # Missing statements attribute entirely is also survived.
    assert extract_financial_statement_metrics(_FakeXBRL(raise_stmts=True), _FakeCompany(sic="6022"),
                                               "6022", "10-K", "2025-12-31") is None


def test_ambiguous_concept_without_marker_is_skipped():
    # Two face rows share the concept and neither carries the expected standard marker → don't guess.
    rows = [
        {"concept": "us-gaap_Revenues", "label": "Segment A", "values": [10, 9, 8]},
        {"concept": "us-gaap_Revenues", "label": "Segment B", "values": [20, 19, 18]},
    ]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic="6311"), "6311", "10-K", "2025-12-31"
    )
    # insurer profile matched only if PremiumsEarnedNet present — here it's financial_generic, whose
    # single revenue selector is ambiguous → no metrics → None (caller falls back to generic path).
    assert result is None


def test_requires_anchor_at_period_of_report():
    # Newest column (2025) has no value for the anchor → series doesn't anchor → nothing emitted.
    rows = [{"concept": "us-gaap_InterestIncomeExpenseNet", "label": "Net interest income",
             "std": "NetInterestIncome", "values": [None, 253084000, 222836000]},
            {"concept": "us-gaap_NoninterestIncome", "label": "Total non-interest income",
             "std": "NonInterestIncome", "values": [None, 23829000, 20000000]}]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic="6022"), "6022", "10-K", "2025-12-31"
    )
    assert result is None


def test_match_financial_profile_by_concept_presence():
    assert match_financial_profile(_stmt_df(_BANK_ROWS))["key"] == "bank"
    assert match_financial_profile(_stmt_df([
        {"concept": "us-gaap_PremiumsEarnedNet", "label": "Premiums", "std": "Revenue", "values": [1, 2, 3]},
    ]))["key"] == "insurer"


def test_is_financial_institution_gate():
    # Method True wins even with a blank SIC (ARCC-like).
    assert is_financial_institution(_FakeCompany(is_fin=True, sic=None), None) is True
    # Method raising falls back to the SIC band.
    assert is_financial_institution(_FakeCompany(raise_fin=True), "6022") is True
    assert is_financial_institution(_FakeCompany(is_fin=False), "3571") is False
    # No method, only SIC.
    assert is_financial_institution(object(), "6311") is True
    assert is_financial_institution(object(), "2911") is False


def test_truthy_flag_handles_bool_nan_string():
    assert _truthy_flag(False) is False
    assert _truthy_flag(True) is True
    assert _truthy_flag(float("nan")) is False
    assert _truthy_flag(None) is False
    assert _truthy_flag("") is False
    assert _truthy_flag("SomeAxis") is True


# --------------------------------------------------------------------------- integration glue
# `_extract_from_filing_instance_sync`, with the flag on, must route a bank to the statement path:
# suppress the generic "revenue" and emit net/non-interest income (with raw_tag), while other
# metrics (net income) still come from the generic fact-query path.

def _facts_df(rows):
    return pd.DataFrame(
        rows, columns=["is_dimensioned", "period_start", "period_end", "numeric_value", "decimals", "currency"]
    )


class _FactQuery:
    def __init__(self, frames):
        self._frames, self._sel = frames, pd.DataFrame()

    def by_concept(self, concept, exact=True):
        self._sel = self._frames.get(concept.split(":", 1)[1], pd.DataFrame())
        return self

    def to_dataframe(self):
        return self._sel


class _Facts:
    def __init__(self, frames):
        self._frames = frames

    def query(self):
        return _FactQuery(self._frames)


class _XBRLWithFacts(_FakeXBRL):
    def __init__(self, stmt_df, fact_frames):
        super().__init__(stmt_df)
        self.facts = _Facts(fact_frames)


class _Filing:
    def __init__(self, xb):
        self.form = "10-K"
        self.period_of_report = "2025-12-31"
        self._xb = xb

    def xbrl(self):
        return self._xb


class _Company:
    def __init__(self, filing):
        self.cik = "1476034"
        self.sic = "6022"
        self._filing = filing

    def is_financial_institution(self):
        return True

    def get_filings(self, accession_number=None):
        return [self._filing]


def test_sync_extraction_routes_bank_to_statement_path(monkeypatch):
    from app.services.edgar import xbrl_service as xs
    from app.config import settings

    monkeypatch.setattr(settings, "USE_STATEMENT_FINANCIALS", True)
    # Net income comes from the generic fact-query path; a 10-K FY duration (365d) at the anchor.
    fact_frames = {"NetIncomeLoss": _facts_df([(False, "2025-01-01", "2025-12-31", 71098000, -3, None)])}
    xb = _XBRLWithFacts(_stmt_df(_BANK_ROWS), fact_frames)
    monkeypatch.setattr(xs, "EdgarCompany", lambda cik: _Company(_Filing(xb)))

    result = xs._extract_from_filing_instance_sync("0001476034", "acc-1")
    assert result is not None
    assert result["revenue"] == []  # suppressed for a bank
    assert result["net_interest_income"][0]["value"] == 303235000.0
    assert result["net_interest_income"][0]["raw_tag"] == "us-gaap:InterestIncomeExpenseNet"
    assert result["noninterest_income"][0]["value"] == 11871000.0
    assert result["net_income"][0]["value"] == 71098000.0  # still via the generic path


# --------------------------------------------------------------------------- P0 #2/#3 fixes

def test_bank_with_reported_total_emits_revenue_and_components():
    """A large bank (JPM shape) that publishes a consolidated 'Total net revenue' emits the reported
    total AS WELL AS the two components (product decision: components + reported total)."""
    rows = _BANK_ROWS + [
        {"concept": "us-gaap_Revenues", "label": "Total net revenue", "std": "Revenue",
         "values": [182450000000, 158100000000, 128600000000]},
    ]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic="6021"), "6021", "10-K", "2025-12-31"
    )
    assert result is not None
    key, metrics, suppress = result
    assert key == "bank"
    assert suppress == ("revenue",)  # the GENERIC revenue is still never used
    assert set(metrics) == {"net_interest_income", "noninterest_income", "revenue"}
    assert metrics["revenue"][0][0] == ("2025-12-31", 182450000000.0)
    assert metrics["revenue"][1] == "us-gaap:Revenues"


def test_nii_only_filer_falls_through_to_financial_generic():
    """An asset-manager/broker (SCHW/KKR shape) that tags a net-interest line but has NO
    non-interest-income total must NOT stick to the bank profile — it falls through to its reported
    total, and revenue is NOT suppressed."""
    rows = [
        {"concept": "us-gaap_InterestIncomeExpenseNet", "label": "Net interest revenue",
         "std": "NetInterestIncome", "values": [11750000000, 10900000000, 9800000000]},
        {"concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "label": "Total net revenues",
         "std": "Revenue", "values": [23920000000, 21000000000, 18800000000]},
    ]
    result = extract_financial_statement_metrics(
        _FakeXBRL(_stmt_df(rows)), _FakeCompany(sic="6211"), "6211", "10-K", "2025-12-31"
    )
    assert result is not None
    key, metrics, suppress = result
    assert key == "financial_generic"      # not "bank"
    assert suppress == ()
    assert set(metrics) == {"revenue"}
    assert metrics["revenue"][0][0] == ("2025-12-31", 23920000000.0)


# --------------------------------------------------------------------------- P0 #1 fixes

def test_period_marker():
    assert _period_marker("2025-09-30 (Q3)") == "Q3"
    assert _period_marker("2025-12-31 (FY)") == "FY"
    assert _period_marker("2025-09-30 (YTD)") == "YTD"
    assert _period_marker("2025-09-30") == ""


def test_statement_period_columns_10q_keeps_quarter_drops_ytd():
    # A Q3 statement with the YTD column listed FIRST (the ARCC repro) — the quarter must win.
    df = _stmt_df(
        [{"concept": "us-gaap_GrossInvestmentIncomeOperating", "label": "Total investment income",
          "std": "Revenue", "values": [2259000000, 782000000, 2100000000, 763000000]}],
        periods=("2025-09-30 (YTD)", "2025-09-30 (Q3)", "2024-09-30 (YTD)", "2024-09-30 (Q3)"),
    )
    cols = _statement_period_columns(df, "10-Q")
    # Only the (Qn) columns survive, newest first — no YTD leaks in.
    assert [c for _, c in cols] == ["2025-09-30 (Q3)", "2024-09-30 (Q3)"]


def test_10q_reversed_column_order_selects_quarter_not_ytd():
    """End-to-end: a BDC 10-Q whose income statement lists the 9-month YTD column before the quarter
    (ARCC's real ordering) must return the QUARTER ($782M), never the YTD ($2.259B)."""
    df = _stmt_df(
        [{"concept": "us-gaap_GrossInvestmentIncomeOperating", "label": "Total investment income",
          "std": "Revenue", "values": [2259000000, 782000000, 2100000000, 763000000]}],
        periods=("2025-09-30 (YTD)", "2025-09-30 (Q3)", "2024-09-30 (YTD)", "2024-09-30 (Q3)"),
    )
    result = extract_financial_statement_metrics(
        _FakeXBRL(df), _FakeCompany(sic=None), None, "10-Q", "2025-09-30"
    )
    assert result is not None
    _key, metrics, _ = result
    assert metrics["revenue"][0][0] == ("2025-09-30", 782000000.0)  # the quarter, not $2.259B YTD
