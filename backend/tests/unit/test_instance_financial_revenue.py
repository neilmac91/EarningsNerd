"""E278: a financial filer's per-filing revenue is E264's choice, read from the filing's own facts.

``edgar/instance/financial_revenue.financial_revenue_concepts`` applies ``facts/fi_revenue.financial_revenue_tags`` to
the chosen filing's own undimensioned facts. ``xbrl_instance`` passes the tags to the statement reader, whose bank and
catch-all revenue selectors read only them, and makes them the generic list's only revenue candidates. The matrix
drives the whole per-filing extraction (``_extract_from_filing_instance_sync``) over instances that carry real filings'
own figures. Each case states the revenue a route reads with the choice and, as its control, without it (the choice
patched to None, the reading before E278), so a case that cannot tell the two apart says so. The insurer and BDC
profiles, IFRS filers, non-financial filers and the flag's off state keep their reading. The conversion check feeds
every filing of the E264 fixtures (``tests/fixtures/companyfacts_fi``), restricted to its own items, through the
instance path and gets E264's choice on the same items; one real edgartools parse reads the library's own columns.
"""
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.config import settings
from app.services.edgar import xbrl_instance
from app.services.edgar.instance import financial_revenue
from app.services.edgar.instance.concepts import DURATION_CONCEPTS
from app.services.edgar.instance.financial_profiles import FINANCIAL_PROFILES
from app.services.edgar.instance.financial_revenue import FILING_REVENUE_PROFILES, financial_revenue_concepts
from app.services.facts import fi_revenue
from tests.unit.test_financing_source import instance_xml, parsed_filing

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "companyfacts_fi"
RNOIE, REV, FEE = "RevenuesNetOfInterestExpense", "Revenues", fi_revenue.FEE_TAG
NII, NONII, GII = "InterestIncomeExpenseNet", "NoninterestIncome", "GrossInvestmentIncomeOperating"
RULE_TAGS = (*fi_revenue.TOTAL_TAGS, FEE, *fi_revenue.NON_606_TAGS)
M = 1_000_000  # figures in whole millions, so each is an exact float
FINANCIAL = SimpleNamespace(sic="6211")  # no edgartools probe: the SIC band decides


# ---------------------------------------------------------------------------
# Fakes of the parsed instance: the fact-query seam and the as-reported income statement.

class _Query:
    def __init__(self, frames, log):
        self._frames, self._log, self._rows = frames, log, None

    def by_concept(self, concept, exact=False):
        # edgartools matches by regex unless exact=True is passed, so a call that drops the flag fails here.
        assert exact is True, f"by_concept({concept!r}) without exact=True matches by regex in edgartools"
        self._log.append(concept)
        self._rows = self._frames.get(concept)
        return self

    def to_dataframe(self):
        return pd.DataFrame(self._rows) if self._rows else pd.DataFrame()


class _Instance:
    """Facts ``{qualified concept: [row]}``, and statement rows over ``columns``; no rows: no readable statement."""

    def __init__(self, facts, statement=None, columns=None, query=_Query):
        self.queried = []
        self.facts = SimpleNamespace(query=lambda: query(facts, self.queried))
        self._statement, self._columns = statement, columns

    @property
    def statements(self):
        if self._statement is None:
            return SimpleNamespace(income_statement=lambda: None)
        frame = pd.DataFrame([
            {"concept": f"us-gaap_{concept}", "label": label, "standard_concept": std, "abstract": False,
             "is_breakdown": False, "dimension": False, **dict(zip(self._columns, values))}
            for concept, label, std, values in self._statement])
        return SimpleNamespace(income_statement=lambda: SimpleNamespace(to_dataframe=lambda view=None: frame))


def _rows(periods, currency="USD"):
    """Undimensioned duration facts from ``[(start, end, value)]``."""
    return [{"is_dimensioned": False, "period_start": start, "period_end": end, "numeric_value": value,
             "decimals": -6, "currency": currency} for start, end, value in periods]


def _years(last, millions):
    """Calendar years ending in ``last``, newest first, from figures in millions."""
    return [(f"{last - i}-01-01", f"{last - i}-12-31", v * M) for i, v in enumerate(millions)]


def _facts(**tags):
    return {f"us-gaap:{tag}": _rows(periods) for tag, periods in tags.items()}


def _face(*rows):
    """Statement rows ``(concept, label, standard concept, figures in millions)``."""
    return [(concept, label, std, [v * M for v in values]) for concept, label, std, values in rows]


def _fy_columns(last):
    return [f"{last - i}-12-31 (FY)" for i in range(3)]


def _extract(monkeypatch, instance, *, por, form="10-K", financial=True, sic="6211"):
    company = SimpleNamespace(sic=sic, is_financial_institution=lambda: financial)
    filing = SimpleNamespace(form=form, period_of_report=por, xbrl=lambda: instance)
    monkeypatch.setattr(xbrl_instance, "resolve_filing_by_accession", lambda cik, accession: (company, [filing]))
    monkeypatch.setattr(settings, "USE_STATEMENT_FINANCIALS", True)
    return xbrl_instance._extract_from_filing_instance_sync("0000000001", "0000000001-26-000001")


def _revenue(result):
    """(tag, value) of the filing's own-period revenue; None for none."""
    points = result["revenue"]
    return (points[0]["raw_tag"].split(":", 1)[1], points[0]["value"]) if points else None


def _e264(facts, por):
    """E264's rule over the same facts as companyfacts items: its first chosen tag with a figure at ``por``."""
    usgaap = {concept.split(":", 1)[1]: {"units": {"USD": [
        {"form": "10-K", "val": r["numeric_value"], "start": r["period_start"], "end": r["period_end"],
         "accn": "", "filed": ""} for r in rows]}} for concept, rows in facts.items()}
    tags = fi_revenue.financial_revenue_tags(usgaap, "USD")
    return next((t for t in tags if any(r["period_end"] == por for r in facts.get(f"us-gaap:{t}", []))), None)


# ---------------------------------------------------------------------------
# Real filings' own figures (SEC companyfacts, in millions), and the faces their statements show or could show. Run
# through the product's extractor on SEC's filings (PR body), IBKR's FY2016-19 10-Ks move on the statement route, and
# AXP, IBKR, BLK's FY2024, GS and PNC's FY2019 10-Ks move only where the generic list reads (no readable statement).

# IBKR's FY2019 10-K: gross "Total revenues" (Revenues) above its "Total net revenues", and no interest components,
# so its statement takes the catch-all profile, whose anchors read Revenues first.
IBKR_2019 = _facts(**{RNOIE: _years(2019, [1937, 1903, 1702]), REV: _years(2019, [2580, 2366, 1927]),
                      FEE: _years(2019, [847, 925])})
IBKR_2019_FACE = _face((REV, "Total revenues", "Revenue", [2580, 2366, 1927]),
                       (RNOIE, "Total net revenues", "Revenue", [1937, 1903, 1702]))
# The same totals on a bank face (IBKR tags its interest components from FY2020 on): the bank anchors read Revenues
# first. The components are illustrative.
IBKR_2019_BANK_FACE = [*_face((NII, "Net interest income", "NetInterestIncome", [1000, 900, 800]),
                             (NONII, "Total non-interest income", "NonInterestIncome", [937, 1003, 902])),
                       *IBKR_2019_FACE]
# BLK's FY2024 10-K: a Revenues line of 12,794 under its 20,407 total, which it tags with the ASC 606 element. Its own
# face does not show that line, so the catch-all already reads the total there; the generic list reads the line first.
BLK_2024 = _facts(**{REV: _years(2024, [12794, 11012, 11061]), FEE: _years(2024, [20407, 17859, 17873])})
BLK_2024_FACE = _face((FEE, "Total revenue", "Revenue", [20407, 17859, 17873]),
                      (REV, "Investment advisory, administration fees and securities lending revenue", None,
                       [12794, 11012, 11061]))
# GS's FY2025 10-K: its total is RevenuesNetOfInterestExpense alone, which the generic list never reads.
GS_2025 = _facts(**{RNOIE: _years(2025, [58283, 53512, 46254]), NII: _years(2025, [13559, 8056, 6351]),
                    NONII: _years(2025, [44724, 45456, 39903]), "NetIncomeLoss": _years(2025, [17176, 14276, 8516])})
# PNC's FY2019 10-K: its 17,827 total tagged with the ASC 606 element beside net interest income, and no total tag.
# Without other filings' evidence the rule refuses it, as E264's feed would; PNC's bank face reads no revenue anyway.
PNC_2019 = _facts(**{FEE: _years(2019, [17827, 17132, 16329]), NII: _years(2019, [9965, 9721, 9108]),
                     NONII: _years(2019, [7862, 7411, 7221]), "NetIncomeLoss": _years(2019, [5369, 5301, 5388])})
# AXP's FY2025 10-K: its total is RevenuesNetOfInterestExpense, and its 41,304 of discount revenue the ASC 606 element.
AXP_2025 = _facts(**{RNOIE: _years(2025, [72229, 65949, 60515]), FEE: _years(2025, [41304, 38825, 37218]),
                     NII: _years(2025, [17364, 15543, 13134]), NONII: _years(2025, [54865, 50406, 47381])})
# AXP's figures on a face with no non-interest total (AXP's own face has one, so it takes the bank route): the
# catch-all anchors cannot read RevenuesNetOfInterestExpense, so they read the fee row.
AXP_2025_CATCH_ALL_FACE = _face((NII, "Net interest income", "NetInterestIncome", [17364, 15543, 13134]),
                                (FEE, "Discount revenue", "Revenue", [41304, 38825, 37218]),
                                (RNOIE, "Total revenues net of interest expense", "Revenue", [72229, 65949, 60515]))
# AXP's Q3 2025 10-Q: the quarter and the nine months of both tags.
AXP_Q3_2025 = _facts(**{
    RNOIE: [("2025-07-01", "2025-09-30", 18426 * M), ("2024-07-01", "2024-09-30", 16636 * M),
            ("2025-01-01", "2025-09-30", 53249 * M), ("2024-01-01", "2024-09-30", 48770 * M)],
    FEE: [("2025-07-01", "2025-09-30", 10415 * M), ("2024-07-01", "2024-09-30", 9716 * M),
          ("2025-01-01", "2025-09-30", 30362 * M), ("2024-01-01", "2024-09-30", 28873 * M)]})
# JPM's FY2025 10-K: "Total net revenue" of 182,447, tagged with both totals, beside its two components.
JPM_2025 = _facts(**{RNOIE: _years(2025, [182447, 177556, 158104]), REV: _years(2025, [182447, 177556, 158104]),
                     NII: _years(2025, [95443, 92583, 89267]), NONII: _years(2025, [87004, 84973, 68837])})
JPM_2025_FACE = _face((NII, "Net interest income", "NetInterestIncome", [95443, 92583, 89267]),
                      (NONII, "Total noninterest revenue", "NonInterestIncome", [87004, 84973, 68837]),
                      (RNOIE, "Total net revenue", "Revenue", [182447, 177556, 158104]))
# MET's FY2025 10-K: total revenues beside premiums, net investment income and a fee line of 2,436.
MET_2025 = _facts(**{REV: _years(2025, [77084, 70986, 66905]), FEE: _years(2025, [2436, 2245, 2229]),
                     "PremiumsEarnedNet": _years(2025, [49779, 44945, 44283]),
                     "NetInvestmentIncome": _years(2025, [22559, 21273, 19908])})
MET_2025_FACE = _face(("PremiumsEarnedNet", "Premiums", "Revenue", [49779, 44945, 44283]),
                      ("NetInvestmentIncome", "Net investment income", "Revenue", [22559, 21273, 19908]),
                      (REV, "Total revenues", "Revenue", [77084, 70986, 66905]))
# Shapes: a lender without a total (E264's SYF case), a BDC beside a small fee line, and a fee-tagged total beside net
# interest income (the reader's July SCHW/KKR test; the real SCHW and KKR tag Revenues). A filing with no revenue stays
# the filing's own through its net income (``_finish_instance``'s anchor).
LENDER = _facts(**{FEE: _years(2025, [50, 48, 45]), NII: _years(2025, [400, 380, 360]),
                   NONII: _years(2025, [60, 55, 50]), "NetIncomeLoss": _years(2025, [90, 85, 80])})
LENDER_FACE = _face((NII, "Net interest income", "NetInterestIncome", [400, 380, 360]),
                    (NONII, "Total noninterest income", "NonInterestIncome", [60, 55, 50]))
BDC = _facts(**{GII: _years(2025, [3000, 2800, 2500]), FEE: _years(2025, [60])})
BDC_FACE = _face((GII, "Total investment income", "Revenue", [3000, 2800, 2500]))
FEE_TOTAL = _facts(**{FEE: _years(2025, [23920, 21000, 18800]), NII: _years(2025, [11750, 10900, 9800]),
                      "NetIncomeLoss": _years(2025, [8000, 7000, 6000])})
FEE_TOTAL_FACE = _face((NII, "Net interest revenue", "NetInterestIncome", [11750, 10900, 9800]),
                       (FEE, "Total net revenues", "Revenue", [23920, 21000, 18800]))

MATRIX = {
    # name: (facts, face, columns, form, period of report, (profile, revenue), (profile, revenue) without the choice)
    "catch-all: the net total, never the gross one above it (IBKR FY2019)": (
        IBKR_2019, IBKR_2019_FACE, _fy_columns(2019), "10-K", "2019-12-31",
        ("financial_generic", (RNOIE, 1937 * M)), ("financial_generic", (REV, 2580 * M))),
    "catch-all: the total, never a partial line under it (BLK FY2024 figures, the line on the face)": (
        BLK_2024, BLK_2024_FACE, _fy_columns(2024), "10-K", "2024-12-31",
        ("financial_generic", (FEE, 20407 * M)), ("financial_generic", (REV, 12794 * M))),
    "catch-all: the net total, never the fee row beside it (AXP FY2025 figures)": (
        AXP_2025, AXP_2025_CATCH_ALL_FACE, _fy_columns(2025), "10-K", "2025-12-31",
        ("financial_generic", (RNOIE, 72229 * M)), ("financial_generic", (FEE, 41304 * M))),
    "catch-all: a fee-tagged total beside net interest income gives none, as E264's feed (shape)": (
        FEE_TOTAL, FEE_TOTAL_FACE, _fy_columns(2025), "10-K", "2025-12-31",
        (None, None), ("financial_generic", (FEE, 23920 * M))),
    "bank: the net total, never the gross one above it (IBKR FY2019 totals)": (
        IBKR_2019, IBKR_2019_BANK_FACE, _fy_columns(2019), "10-K", "2019-12-31",
        ("bank", (RNOIE, 1937 * M)), ("bank", (REV, 2580 * M))),
    "bank: the reported total beside both components, unchanged (JPM FY2025)": (
        JPM_2025, JPM_2025_FACE, _fy_columns(2025), "10-K", "2025-12-31",
        ("bank", (RNOIE, 182447 * M)), ("bank", (RNOIE, 182447 * M))),
    "bank: a lender without a total has none, unchanged (shape)": (
        LENDER, LENDER_FACE, _fy_columns(2025), "10-K", "2025-12-31", ("bank", None), ("bank", None)),
    "generic: the net total, never the fee line (AXP FY2025, no statement)": (
        AXP_2025, None, None, "10-K", "2025-12-31", (None, (RNOIE, 72229 * M)), (None, (FEE, 41304 * M))),
    "generic: the quarter's net total, never its fee line (AXP Q3 2025, no statement)": (
        AXP_Q3_2025, None, None, "10-Q", "2025-09-30", (None, (RNOIE, 18426 * M)), (None, (FEE, 10415 * M))),
    "generic: a lender without a total has none, never its fee line (shape)": (
        LENDER, None, None, "10-K", "2025-12-31", (None, None), (None, (FEE, 50 * M))),
    "generic: the total, never the partial line (BLK FY2024, no statement)": (
        BLK_2024, None, None, "10-K", "2024-12-31", (None, (FEE, 20407 * M)), (None, (REV, 12794 * M))),
    "generic: the net total the generic list cannot read (GS FY2025, no statement)": (
        GS_2025, None, None, "10-K", "2025-12-31", (None, (RNOIE, 58283 * M)), (None, None)),
    "generic: a fee-tagged total beside net interest income gives none (PNC FY2019, no statement)": (
        PNC_2019, None, None, "10-K", "2019-12-31", (None, None), (None, (FEE, 17827 * M))),
    "insurer: its own total, unchanged (MET FY2025)": (
        MET_2025, MET_2025_FACE, _fy_columns(2025), "10-K", "2025-12-31",
        ("insurer", (REV, 77084 * M)), ("insurer", (REV, 77084 * M))),
    "bdc: its total investment income, which the choice would empty, unchanged (shape)": (
        BDC, BDC_FACE, _fy_columns(2025), "10-K", "2025-12-31", ("bdc", (GII, 3000 * M)), ("bdc", (GII, 3000 * M))),
}


@pytest.mark.parametrize("name", MATRIX)
def test_each_route_reads_a_financial_filers_revenue_from_its_own_choice(monkeypatch, name):
    facts, face, columns, form, por, (profile, revenue), (before_profile, before) = MATRIX[name]
    result = _extract(monkeypatch, _Instance(facts, face, columns), por=por, form=form)
    assert (result["financial_classification"]["profile"], _revenue(result)) == (profile, revenue)
    if profile not in ("insurer", "bdc"):  # the routes that read the choice: E264's first tag with a figure
        assert _e264(facts, por) == (revenue[0] if revenue else None)
    monkeypatch.setattr(xbrl_instance, "financial_revenue_concepts", lambda *args, **kwargs: None)
    control = _extract(monkeypatch, _Instance(facts, face, columns), por=por, form=form)
    assert (control["financial_classification"]["profile"], _revenue(control)) == (before_profile, before)


def test_the_generic_route_keeps_the_figures_currency_start_and_comparatives(monkeypatch):
    result = _extract(monkeypatch, _Instance(AXP_2025), por="2025-12-31")
    point = result["revenue"][0]
    assert {key: point[key] for key in ("period", "value", "currency", "raw_tag", "period_start")} == {
        "period": "2025-12-31", "value": 72229 * M, "currency": "USD", "raw_tag": f"us-gaap:{RNOIE}",
        "period_start": "2025-01-01"}
    assert [(p["period"], p["value"]) for p in result["revenue"]] == [
        ("2025-12-31", 72229 * M), ("2024-12-31", 65949 * M), ("2023-12-31", 60515 * M)]


def test_bank_components_stay_beside_the_chosen_total(monkeypatch):
    result = _extract(monkeypatch, _Instance(JPM_2025, JPM_2025_FACE, _fy_columns(2025)), por="2025-12-31")
    assert result["net_interest_income"][0]["value"] == 95443 * M
    assert result["noninterest_income"][0]["value"] == 87004 * M


def test_an_ifrs_financial_filer_reads_as_before(monkeypatch):
    frames = {"ifrs-full:Revenue": _rows(_years(2025, [9000, 8000]))}
    assert financial_revenue_concepts(_Instance(frames), FINANCIAL, "6211", "10-K", "2025-12-31") is None
    result = _extract(monkeypatch, _Instance(frames), por="2025-12-31")
    assert _revenue(result) == ("Revenue", 9000 * M)


def test_a_non_financial_filer_never_computes_the_choice(monkeypatch):
    calls = []
    monkeypatch.setattr(financial_revenue, "financial_revenue_tags", lambda *args: calls.append(args) or ())
    instance = _Instance(IBKR_2019)
    result = _extract(monkeypatch, instance, por="2019-12-31", financial=False, sic="7372")
    assert _revenue(result) == (REV, 2580 * M)  # the generic list reads Revenues first, as for every operating filer
    rule_only = {f"us-gaap:{tag}" for tag in RULE_TAGS} - {f"us-gaap:{tag}" for tag in DURATION_CONCEPTS["revenue"]}
    assert calls == [] and rule_only.isdisjoint(instance.queried)


def test_the_flag_off_reads_as_before(monkeypatch):
    company = SimpleNamespace(sic="6211", is_financial_institution=lambda: True)
    filing = SimpleNamespace(form="10-K", period_of_report="2025-12-31", xbrl=lambda: _Instance(AXP_2025))
    monkeypatch.setattr(xbrl_instance, "resolve_filing_by_accession", lambda cik, accession: (company, [filing]))
    monkeypatch.setattr(settings, "USE_STATEMENT_FINANCIALS", False)
    result = xbrl_instance._extract_from_filing_instance_sync("0000000001", "0000000001-26-000001")
    assert _revenue(result) == (FEE, 41304 * M)


def test_a_failed_choice_reads_as_before_and_is_logged(monkeypatch, caplog):
    def broken(*args):
        raise RuntimeError("rule failed")

    monkeypatch.setattr(financial_revenue, "financial_revenue_tags", broken)
    with caplog.at_level(logging.WARNING, logger="app.services.edgar.instance_extractor"):
        result = _extract(monkeypatch, _Instance(AXP_2025), por="2025-12-31")
    assert _revenue(result) == (FEE, 41304 * M)
    assert "Financial revenue choice failed: rule failed" in caplog.text


def test_a_failed_query_reads_as_no_facts_for_its_tag():
    class Failing(_Query):
        def by_concept(self, concept, exact=False):
            if concept == f"us-gaap:{RNOIE}":
                raise RuntimeError("query failed")
            return super().by_concept(concept, exact)

    # Without its total, the filing's fee line beside net interest income is refused: no revenue, not the fee line.
    instance = _Instance(AXP_2025, query=Failing)
    assert financial_revenue_concepts(instance, FINANCIAL, "6211", "10-K", "2025-12-31") == ()


def test_the_choice_queries_each_rule_tag_once_from_the_filings_own_instance():
    instance = _Instance(AXP_2025)
    assert financial_revenue_concepts(instance, FINANCIAL, "6211", "10-K", "2025-12-31") == (RNOIE,)
    assert instance.queried == [f"us-gaap:{tag}" for tag in RULE_TAGS]


def test_the_choice_reads_the_reporting_currency_and_nothing_after_the_period():
    # The fee element is the filer's total in CNY. A USD convenience translation of its year would read as a fee line
    # below the total; a year after the period, whose figures disagree, would be the latest shared year.
    facts = {f"us-gaap:{RNOIE}": _rows(_years(2025, [72000, 66000, 60000]) + _years(2026, [80000]), "CNY"),
             f"us-gaap:{FEE}": _rows(_years(2025, [72000, 66000, 60000]) + _years(2026, [5000]), "CNY")
             + _rows(_years(2025, [10300]), "USD")}
    assert financial_revenue_concepts(_Instance(facts), FINANCIAL, "6211", "10-K", "2025-12-31") == (RNOIE, FEE)


def test_dimensioned_facts_are_not_the_filings_own():
    facts = {f"us-gaap:{FEE}": _rows(_years(2025, [41000, 38000])),
             f"us-gaap:{RNOIE}": [dict(row, is_dimensioned=True) for row in _rows(_years(2025, [72000, 66000]))]}
    assert financial_revenue_concepts(_Instance(facts), FINANCIAL, "6211", "10-K", "2025-12-31") == (FEE,)


def test_the_choice_replaces_only_the_bank_and_catch_all_anchors():
    keys = {profile["key"] for profile in FINANCIAL_PROFILES}
    assert FILING_REVENUE_PROFILES == {"bank", "financial_generic"} and FILING_REVENUE_PROFILES <= keys
    for profile in FINANCIAL_PROFILES:
        if profile["key"] in FILING_REVENUE_PROFILES:
            assert [key for key, _anchors, _std in profile["selectors"]].count("revenue") == 1


# ---------------------------------------------------------------------------
# The conversion: a filing's own items, served as instance facts, give E264's choice on the same items.

def _own_filings():
    """Every 10-K and 10-Q of the E264 fixtures: (ticker, accession, form, its own items as companyfacts lists them)."""
    out = []
    for path in sorted(FIXTURES.glob("*.json")):
        usgaap = json.loads(path.read_text())["facts"]["us-gaap"]
        forms = {i["accn"]: i["form"] for node in usgaap.values() for items in node["units"].values() for i in items}
        for accn, form in sorted(forms.items()):
            if form in ("10-K", "10-Q"):
                own = {tag: [i for i in node["units"].get("USD", []) if i["accn"] == accn]
                       for tag, node in usgaap.items()}
                own = {tag: {"units": {"USD": items}} for tag, items in own.items() if items}
                out.append((path.stem, accn, form, own))
    return out


def _as_instance(own):
    return _Instance({f"us-gaap:{tag}": _rows([(i.get("start"), i["end"], i["val"]) for i in node["units"]["USD"]])
                      for tag, node in own.items()})


def _period_of_report(own):
    return max(i["end"] for node in own.values() for i in node["units"]["USD"])


def test_every_fixture_filings_own_items_give_e264s_choice():
    filings = _own_filings()
    assert len(filings) > 300  # the ten fixtures' filings, not a stray few
    mismatches = [
        (ticker, accn, got, want) for ticker, accn, form, own in filings
        if (got := financial_revenue_concepts(_as_instance(own), FINANCIAL, "6211", form, _period_of_report(own)))
        != (want := fi_revenue.financial_revenue_tags(own, "USD"))]
    assert mismatches == []


@pytest.mark.parametrize("ticker,accession,tags", [
    ("IBKR", "0001381197-20-000006", (RNOIE,)),  # FY2019: the net total, not the gross Revenues above it
    ("IBKR", "0001381197-26-000062", (RNOIE,)),  # FY2025: the net total, not the fee line
    ("AXP", "0000004962-26-000080", (RNOIE,)),
    ("BLK", "0000950170-25-026584", (FEE,)),  # FY2024: the fee-tagged total, not the partial Revenues line
    ("MET", "0001099219-26-000013", (REV,)),
    ("PNC", "0000713676-21-000025", (REV, FEE)),  # the fee element matches the total, so it may fill
])
def test_named_filings_choose_their_reported_total(ticker, accession, tags):
    [(form, own)] = [(form, own) for t, accn, form, own in _own_filings() if (t, accn) == (ticker, accession)]
    assert financial_revenue_concepts(_as_instance(own), FINANCIAL, "6211", form, _period_of_report(own)) == tags


def test_a_real_parse_gives_the_choice():
    def fact(concept, ref, value):
        return f'<us-gaap:{concept} contextRef="{ref}" unitRef="usd" decimals="-6">{value}</us-gaap:{concept}>'

    # IBKR's FY2019 shape in the helper's three years (it tags Revenues of 10,000 in the current one): gross Revenues
    # beside the net total, and a fee line.
    extra = "".join([fact(RNOIE, ref, v * M) for ref, v in (("c", 1937), ("p", 1903), ("o", 1702))]
                    + [fact(REV, ref, v * M) for ref, v in (("p", 2366), ("o", 1927))]
                    + [fact(FEE, ref, v * M) for ref, v in (("c", 847), ("p", 925))])
    _filing, xb = parsed_filing(instance_xml(extra=extra))
    assert financial_revenue_concepts(xb, FINANCIAL, "6211", "10-K", "2025-12-31") == (RNOIE,)
