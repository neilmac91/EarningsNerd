"""A quarterly report's year that holds only part of one never reaches a reader (E291, E292; ``facts/fiscal_naming``).

CBAN's and FIX's Q1 2026 10-Qs tag their Q1 2025 comparatives with the full-year span 2025-01-01..2025-12-31, and,
filed after the 10-Ks, won FY2025 wherever the latest filed item wins; WAL's 2015 10-Qs tag their own six and nine
months' EPS as calendar 2012. ``without_partial_years`` drops such an item
for every reader that picks a figure from companyfacts duration items: the collector's admission
(``currency.admitted_items``), the backfill cross-check's authority (``reconcile.extract_authoritative_values``) and
the per-filing fallback (``edgar/xbrl_companyfacts.py``). The restatement census's evidence index, which reads every
tag, keeps every item, and the gate below pins every reader. A dropped year whose dates are no fiscal year stays on
the calendar's record, the quarterly repair's evidence. The fixtures are trimmed from SEC's payloads (CBAN's, WAL's
and STT's of 2026-11-02, FIX's, ARTW's and LMB's of 2026-11-01) to the tags and years their tests read.
"""
import ast
import json
from datetime import date
from pathlib import Path

import pytest

from app.services.edgar.xbrl_companyfacts import parse_company_facts
from app.services.facts.companyfacts import normalize_companyfacts
from app.services.facts.fiscal_naming import QUARTERLY_FORMS, without_partial_years
from app.services.facts.reconcile import extract_authoritative_values

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures" / "companyfacts_partial_years"
END = date(2025, 12, 31)
CBAN_10K, CBAN_10Q = "0000711669-26-000007", "0001104659-26-057671"
FIX_10K, FIX_10Q = "0001104659-26-017530", "0001104659-26-047689"


def _item(start, end, val, form="10-Q", accn="0000000000-26-000001", filed="2026-05-08"):
    return {"start": start, "end": end, "val": val, "form": form, "accn": accn, "filed": filed}


QUARTER = _item("2025-01-01", "2025-03-31", 20952000, accn="q1-2025", filed="2025-05-09")
ANNUAL = _item("2025-01-01", "2025-12-31", 91901000, form="10-K", accn="10k-2025", filed="2026-03-13")


# --- the rule --------------------------------------------------------------------------------------------------------

def test_a_10q_year_equal_to_another_filings_first_quarter_is_dropped():
    # CBAN's shape: the quarter is the Q1 2025 10-Q's own, and the year sits only in the Q1 2026 10-Q.
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    assert without_partial_years([QUARTER, ANNUAL, year]) == [QUARTER, ANNUAL]


def test_the_10q_carrying_the_quarter_too_loses_only_the_year():
    # FIX's shape: one 10-Q tags the comparative twice, with the quarter's span and with the year's.
    quarter, year = (_item("2025-01-01", end, 1831286000, accn="q1-2026") for end in ("2025-03-31", "2025-12-31"))
    assert without_partial_years([quarter, year]) == [quarter]


@pytest.mark.parametrize("end", ["2025-06-30", "2025-09-30"])
def test_a_year_equal_to_six_or_nine_months_from_the_same_start_is_dropped(end):
    # HP's FY2016 revenue was its first half; STX's FY2021 operating cash flow its nine months, in another filing.
    to_date = _item("2025-01-01", end, 3000000, accn="ytd")
    year = _item("2025-01-01", "2025-12-31", 3000000, accn="q-later")
    assert without_partial_years([to_date, year]) == [to_date]


@pytest.mark.parametrize("form", ["10-K", "8-K"])
def test_a_part_from_any_filing_marks_the_year(form):
    # RNGR's FY2017 profit in a 10-Q equals its first quarter as a 10-K reports it: a part counts from any filing.
    quarter = _item("2025-01-01", "2025-03-31", 20952000, form=form, accn="annual")
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    assert without_partial_years([quarter, year]) == [quarter]


def test_a_recast_year_matching_no_shorter_item_stays():
    # Macy's restated FY2021 in a December 2024 10-Q: 1,419M against the 10-K's 1,430M, no quarter of either.
    recast = _item("2025-01-01", "2025-12-31", 90000000, accn="restating-10q")
    assert without_partial_years([QUARTER, ANNUAL, recast]) == [QUARTER, ANNUAL, recast]


@pytest.mark.parametrize("value", [20952001, 20953000, 20900000, -20952000])
def test_only_the_very_figure_marks_a_partial_year(value):
    # Estee Lauder's FY2023 operating income, 1,509M in its 10-K and again in two 10-Qs, sits 0.3% below its nine
    # months' 1,514M: a real year whose fourth quarter lost money. A tolerance of 0.5% would drop it, and DLR's and
    # TRC's real years with it.
    year = _item("2025-01-01", "2025-12-31", value, accn="q1-2026")
    assert without_partial_years([QUARTER, year]) == [QUARTER, year]


@pytest.mark.parametrize("end", ["2025-05-15", "2025-08-31"])
def test_a_span_neither_a_quarter_nor_six_or_nine_months_never_drops_the_year(end):
    # 134 and 242 days from the year's start, in the year's own filing: no class of _classify_duration, so no part.
    span = _item("2025-01-01", end, 20952000, accn="q1-2026")
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    assert without_partial_years([span, year]) == [span, year]


def test_an_annual_reports_year_equal_to_its_first_quarter_stays():
    # BMY's FY2011 investing cash flow equals its Q1 2011's: a 10-K's year is never second-guessed.
    year = _item("2025-01-01", "2025-12-31", 20952000, form="10-K", accn="10k")
    assert without_partial_years([QUARTER, year]) == [QUARTER, year]


def test_a_zero_year_stays():
    # LIFD's FY2019 revenue is zero in its 10-K and its 10-Q alike: the rest of a year can be exactly nothing then.
    quarter, year = _item("2025-01-01", "2025-03-31", 0), _item("2025-01-01", "2025-12-31", 0, accn="q-later")
    assert without_partial_years([quarter, year]) == [quarter, year]


@pytest.mark.parametrize("start", ["2025-04-01", "2024-12-31", "2025-01-02"])
def test_another_filings_part_from_another_start_never_drops_the_year(start):
    # Macy's FY2023 EPS equals its Q3's by coincidence: from another start, only the year's own filing ties a part.
    part = _item(start, "2025-06-30" if start == "2025-04-01" else "2025-03-31", 20952000, accn="q")
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q-later")
    assert without_partial_years([part, year]) == [part, year]


@pytest.mark.parametrize("form", ["10-Q", "10-Q/A", "10-QT", "10-QT/A"])
def test_every_quarterly_form_is_read_so(form):
    # AIRJ's FY2023 ProfitLoss, its Q1 2023's, sits in a 10-Q and again in its 10-Q/A.
    year = _item("2025-01-01", "2025-12-31", 20952000, form=form, accn="q1-2026")
    assert without_partial_years([QUARTER, year]) == [QUARTER]
    assert QUARTERLY_FORMS == {"10-Q", "10-Q/A", "10-QT", "10-QT/A"}


@pytest.mark.parametrize("form", ["10-K", "10-K/A", "10-KT", "20-F", "40-F", "8-K", "6-K", "S-1", "S-4", None])
def test_no_other_form_is_dropped(form):
    # WMB's 2018 8-K recast puts FY2015 operating income at its Q1's 227M against the 10-Ks' 226M: a real recast.
    year = _item("2025-01-01", "2025-12-31", 20952000, form=form, accn="other")
    assert without_partial_years([QUARTER, year]) == [QUARTER, year]


def test_order_identity_and_every_unreadable_item_are_kept():
    unreadable = ["not an item", {"val": 20952000, "form": "10-Q"}, {**QUARTER, "start": "bad"},
                  {**QUARTER, "val": True}, {**QUARTER, "val": "20952000"}, {**QUARTER, "end": None}]
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    kept = without_partial_years([*unreadable, QUARTER, year, ANNUAL])
    assert kept == [*unreadable, QUARTER, ANNUAL] and all(a is b for a, b in zip(kept, [*unreadable, QUARTER, ANNUAL]))
    assert without_partial_years([]) == []


# --- a part from any start in the year's own filing (E292) ------------------------------------------------------------

WAL_10K, WAL_Q2, WAL_Q3 = "0001212545-15-000090", "0001212545-15-000188", "0001212545-15-000211"
STT_Q1_2019 = "0000093751-19-000387"


def test_a_10q_year_equal_to_a_period_the_same_10q_reports_is_dropped():
    # WAL's Q2 2015 10-Q tags its own six months' EPS, 0.85, as calendar 2012, whose EPS its 10-K put at 0.84.
    half = _item("2015-01-01", "2015-06-30", 0.85, accn=WAL_Q2, filed="2015-08-07")
    year = _item("2012-01-01", "2012-12-31", 0.85, accn=WAL_Q2, filed="2015-08-07")
    annual = _item("2012-01-01", "2012-12-31", 0.84, form="10-K", accn=WAL_10K, filed="2015-02-17")
    assert without_partial_years([half, year, annual]) == [half, annual]


@pytest.mark.parametrize("end", ["2019-03-31", "2019-06-30", "2019-09-30"])
def test_a_quarter_six_or_nine_months_the_same_filing_reports_marks_its_year(end):
    # STT's Q1 2019 10-Q tags its first quarters of 2018 and 2019 as FY2017 and FY2018; UDR's 2014 10-Qs tag their
    # quarter, six and nine months of 2013 as FY2012.
    part = _item("2019-01-01", end, 673000000, accn="q-2019")
    year = _item("2018-01-01", "2018-12-31", 673000000, accn="q-2019")
    assert without_partial_years([part, year]) == [part]


def test_a_part_from_another_start_in_another_filing_never_drops_the_year():
    # WAL's figures, the half year in another filing: across filings a part from another start is a coincidence.
    half = _item("2015-01-01", "2015-06-30", 0.85, accn="another-10q")
    year = _item("2012-01-01", "2012-12-31", 0.85, accn=WAL_Q2)
    assert without_partial_years([half, year]) == [half, year]


@pytest.mark.parametrize("value", [0.84, 0.86, 0.8501, -0.85])
def test_only_the_very_figure_the_filing_reports_marks_its_year(value):
    # exactly, as from the same start: a part from any start has more room for a near coincidence, and a sign is part
    # of the figure
    half = _item("2015-01-01", "2015-06-30", 0.85, accn=WAL_Q2)
    year = _item("2012-01-01", "2012-12-31", value, accn=WAL_Q2)
    assert without_partial_years([half, year]) == [half, year]


def test_a_dollar_off_its_own_filings_part_the_year_stays():
    # at a bank's scale, so the same filing's exactness holds to about 1.5e-9 of the figure, as the same start's does
    part = _item("2019-01-01", "2019-03-31", 673000000, accn=STT_Q1_2019)
    year = _item("2018-01-01", "2018-12-31", 673000001, accn=STT_Q1_2019)
    assert without_partial_years([part, year]) == [part, year]


def test_a_zero_year_its_own_filing_reports_as_a_part_stays():
    # UEC's FY2018 revenue is zero in its 10-Qs, which no 10-K tags, beside a zero half year in the same filing.
    half = _item("2018-08-01", "2019-01-31", 0, accn="0001437749-19-004590", filed="2019-03-12")
    year = _item("2017-08-01", "2018-07-31", 0, accn="0001437749-19-004590", filed="2019-03-12")
    assert without_partial_years([half, year]) == [half, year]


@pytest.mark.parametrize("accn", [None, ["0001212545-15-000188"], {"accn": "x"}, 12])
def test_an_accession_that_is_no_string_ties_no_year_to_its_filing(accn):
    # SEC's accessions are strings; any other value, or none, marks no filing (one built from a filing's instance
    # facts is "", which does).
    part = {**_item("2019-01-01", "2019-03-31", 673000000), "accn": accn}
    year = {**_item("2018-01-01", "2018-12-31", 673000000), "accn": accn}
    assert without_partial_years([part, year]) == [part, year]
    assert without_partial_years([{**part, "accn": ""}, {**year, "accn": ""}]) == [{**part, "accn": ""}]


@pytest.mark.parametrize("form", ["10-K", "10-K/A", "20-F", "8-K", None])
def test_no_other_forms_year_equal_to_its_own_part_is_dropped(form):
    part = _item("2019-01-01", "2019-03-31", 673000000, form=form, accn="one-filing")
    year = _item("2018-01-01", "2018-12-31", 673000000, form=form, accn="one-filing")
    assert without_partial_years([part, year]) == [part, year]


@pytest.mark.parametrize("form", sorted(QUARTERLY_FORMS))
def test_every_quarterly_form_marks_a_year_with_its_own_part(form):
    # a 10-Q/A or a transition report re-tagging its own half year as a past year, as WAL's 10-Q did
    half = _item("2015-01-01", "2015-06-30", 0.85, form=form, accn=WAL_Q2)
    year = _item("2012-01-01", "2012-12-31", 0.85, form=form, accn=WAL_Q2)
    assert without_partial_years([half, year]) == [half]


# --- the readers, on SEC's own payloads -------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def payloads():
    names = ("CBAN", "FIX", "WAL", "STT", "ARTW", "LMB")
    return {name: json.loads((FIXTURES / f"{name}.json").read_text()) for name in names}


def _fy2025(facts):
    return {fact["concept"]: (fact["value"], fact["accession"]) for fact in facts
            if fact["period_end"] == END and fact["fiscal_period"] == "FY"}


def _q4_2025(facts):
    return {fact["concept"]: fact["value"] for fact in facts
            if fact["period_end"] == END and fact["fiscal_period"] == "Q4"}


def test_the_collector_reads_cbans_fy2025_from_its_10k_and_derives_its_q4(payloads):
    facts, _meta = normalize_companyfacts(1, payloads["CBAN"], financial_sic=True)
    assert {concept: fy for concept, fy in _fy2025(facts).items() if concept in (
        "net_income", "net_interest_income", "noninterest_income", "eps_diluted")} == {
        "net_income": (28253000.0, CBAN_10K), "net_interest_income": (91901000.0, CBAN_10K),
        "noninterest_income": (40280000.0, CBAN_10K), "eps_diluted": (1.59, CBAN_10K)}  # the 10-Q read 0.38
    assert {k: v for k, v in _q4_2025(facts).items() if k in ("net_income", "net_interest_income")} == {
        "net_income": 7843000.0, "net_interest_income": 25865000.0}  # incompatible vintages withheld both


def test_the_collector_reads_fixs_fy2025_from_its_10k_and_derives_its_q4(payloads):
    facts, _meta = normalize_companyfacts(2, payloads["FIX"])
    fy = _fy2025(facts)
    assert {concept: fy[concept] for concept in ("revenue", "gross_profit", "operating_income")} == {
        "revenue": (9101641000.0, FIX_10K), "gross_profit": (2195899000.0, FIX_10K),
        "operating_income": (1314589000.0, FIX_10K)}  # the 10-Q read 1,831,286,000 / 403,416,000 / 209,098,000
    assert round(fy["net_margin"][0], 4) == 11.2349  # not 55.8382: the 10-K's net income over the 10-Q's revenue
    assert _q4_2025(facts)["revenue"] == 2646067000.0


@pytest.mark.parametrize("name, financial, expected", [
    ("CBAN", True, {"net_income": 28253000.0}),  # the 10-Q's 6,613,000 would replace a fresh 10-K parse
    ("FIX", False, {"revenue": 9101641000.0, "net_income": 1022558000.0}),  # the 10-Q's revenue: 1,831,286,000
])
def test_the_cross_checks_authority_is_the_10ks(payloads, name, financial, expected):
    authority = extract_authoritative_values(payloads[name], financial=financial)
    assert {concept: value for (concept, end), value in authority.items() if end == END} == expected


def test_the_per_filing_fallback_drops_the_year_against_another_filings_quarter():
    # CBAN's net interest income shape: the Q1 2026 10-Q carries Q1 2025 only as a year; the quarter is the Q1 2025
    # 10-Q's own. So the rule runs before the fallback narrows the items to the filing it reads.
    items = [_item("2025-01-01", "2025-03-31", 100, accn="0000000000-25-000001", filed="2025-05-09"),
             _item("2025-01-01", "2025-12-31", 400, form="10-K", accn="0000000000-26-000002", filed="2026-03-13"),
             _item("2026-01-01", "2026-03-31", 120, accn="0000000000-26-000003"),
             _item("2025-01-01", "2025-12-31", 100, accn="0000000000-26-000003")]
    payload = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": items}}}}}
    points = parse_company_facts(payload, "0000000000-26-000003")["net_income"]
    assert [(point["period"], point["value"]) for point in points] == [("2026-03-31", 120)]


@pytest.mark.parametrize("name, accession, metric", [("CBAN", CBAN_10Q, "net_income"), ("FIX", FIX_10Q, "revenue")])
def test_the_per_filing_fallback_reads_no_year_from_the_10q(payloads, name, accession, metric):
    points = parse_company_facts(payloads[name], accession)[metric]
    assert points and all(point["period"] != "2025-12-31" for point in points)  # was a Q4-labelled Q1 value
    assert {point.get("period_start") for point in points if point["period"] == "2025-03-31"} == {"2025-01-01"}


def test_the_collector_reads_wals_fy2012_eps_from_its_10k(payloads):
    facts, _meta = normalize_companyfacts(3, payloads["WAL"], financial_sic=True)
    fy = {fact["concept"]: (fact["value"], fact["accession"]) for fact in facts
          if fact["period_end"] == date(2012, 12, 31) and fact["fiscal_period"] == "FY"}
    assert fy == {"earnings_per_share": (0.84, WAL_10K), "eps_diluted": (0.83, WAL_10K)}  # the Q3 10-Q read 1.45, 1.44


def test_the_collector_derives_stts_q4_net_interest_income(payloads):
    facts, _meta = normalize_companyfacts(4, payloads["STT"], financial_sic=True)
    q4 = {fact["period_end"]: fact["value"] for fact in facts
          if fact["concept"] == "net_interest_income" and fact["fiscal_period"] == "Q4"}
    # withheld while the Q1 2019 10-Q's 643M and 673M stood as FY2017 and FY2018 candidates
    assert (q4.get(date(2017, 12, 31)), q4.get(date(2018, 12, 31))) == (616000000.0, 697000000.0)


def test_the_cross_checks_authority_takes_no_year_artws_10q_made_of_its_quarters(payloads):
    # ARTW's Q1 2023 10-Q tags its December-February quarters of 2022 and 2023 as March-February years.
    ends = {end.isoformat() for (concept, end) in extract_authoritative_values(payloads["ARTW"])}
    assert ends == {"2021-11-30", "2022-11-30", "2023-11-30"}  # not 2022-02-28 (-406,489) nor 2023-02-28 (342,210)


@pytest.mark.parametrize("accession", [WAL_Q2, WAL_Q3])
def test_the_per_filing_fallback_reads_no_2012_eps_from_wals_2015_10qs(payloads, accession):
    points = parse_company_facts(payloads["WAL"], accession)
    assert points["earnings_per_share"] and points["eps_diluted"]
    assert all(point["period"] != "2012-12-31" for metric in ("earnings_per_share", "eps_diluted")
               for point in points[metric])


def test_the_instance_paths_choice_ties_one_filings_facts(monkeypatch):
    # E278's per-filing revenue choice reads one filing's instance facts, each under the accession "": the same-filing
    # clause ties them, so a 10-Q's year equal to its own quarter never reaches the choice.
    from app.services.edgar.instance import financial_revenue
    from app.services.facts.currency import admitted_items
    from tests.unit.test_instance_financial_revenue import FINANCIAL, M, _facts, _Instance

    handed = {}
    monkeypatch.setattr(financial_revenue, "financial_revenue_tags", lambda usgaap, unit: handed.update(usgaap) or ())
    facts = _facts(Revenues=[("2025-01-01", "2025-03-31", 5 * M), ("2024-01-01", "2024-12-31", 5 * M)])
    financial_revenue.financial_revenue_concepts(_Instance(facts), FINANCIAL, "6211", "10-Q", "2025-03-31")
    (items,) = handed["Revenues"]["units"].values()
    assert [(start, end) for (end, _klass), start, _value, _item in admitted_items(items, instant=False)] == [
        (date(2025, 1, 1), date(2025, 3, 31))]


# --- the calendar's record (E292) -------------------------------------------------------------------------------------
#
# The calendar's exclusions (``calendar.fiscal_duration_values``) judge the collector's winners with every partial year
# competing again in its list place, so a rolling year stays on record as before E291: the only evidence
# ``quarterly_fact_repair._calendar_relabels`` quarantines a stored row by. No row, candidate or vote reads a partial
# year; over 696 cached payloads the record is the one the calendar kept with the rule off, entry for entry.

ARTW_Q1_2023, LMB_Q1_2015 = "0001437749-23-010158", "0001144204-15-028842"


def _rolling(meta) -> set:
    return {(e["concept"], e["raw_tag"], e["period_start"], e["period_end"], e["accession"], e["unit"], e["value"])
            for e in meta.get("calendar_exclusions", []) if e["reason"] == "rolling_duration_not_fiscal_year"}


def test_a_rolling_year_its_own_filing_reports_as_a_part_stays_on_the_calendars_record(payloads):
    # ARTW's Q1 2023 10-Q tags its December-February quarters as March-February years (the same-filing clause).
    assert _rolling(normalize_companyfacts(5, payloads["ARTW"])[1]) == {
        ("net_income", "us-gaap:NetIncomeLoss", "2021-03-01", "2022-02-28", ARTW_Q1_2023, "USD", -406489.0),
        ("net_income", "us-gaap:NetIncomeLoss", "2022-03-01", "2023-02-28", ARTW_Q1_2023, "USD", 342210.0)}


def test_a_rolling_year_equal_to_its_part_from_the_same_start_stays_on_the_calendars_record(payloads):
    # LMB's Q1 2015 10-Q carries its financing cash flow from its inception, 2014-04-15, equal to its first nine
    # months (the same-start clause, E291).
    assert _rolling(normalize_companyfacts(6, payloads["LMB"])[1]) == {(
        "financing_cash_flow", "us-gaap:NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
        "2014-04-15", "2015-03-31", LMB_Q1_2015, "USD", 46598316.0)}


def test_the_quarterly_repair_quarantines_a_stored_row_by_that_record(payloads):
    # A row a sync before 2026-10-10 could store from ARTW's first March-February year: no fresh row has its identity,
    # so only the calendar's record proves it rolling.
    from app.services import quarterly_fact_repair

    facts, meta = normalize_companyfacts(5, payloads["ARTW"])
    stored = {"company_id": 5, "filing_id": None, "concept": "net_income", "raw_tag": "us-gaap:NetIncomeLoss",
              "unit": "USD", "period_start": "2021-03-01", "period_end": "2022-02-28", "fiscal_year": 2022,
              "fiscal_period": "FY", "value": -406489.0, "form": "10-Q", "accession": ARTW_Q1_2023,
              "source": "companyfacts", "reconciled": True, "is_latest": True, "provenance": None}
    updates, _inserts = quarterly_fact_repair._calendar_relabels({1: stored}, facts, meta)
    assert (updates[1]["is_latest"], updates[1]["provenance"]["reasons"]) == (
        False, ["rolling_duration_not_fiscal_year"])


def _filing(accn, filed, *spans, form="10-Q", fp="Q1"):
    """One filing's items from ``(start, end, value)``."""
    return [{"start": start, "end": end, "val": val, "form": form, "accn": accn, "filed": filed, "fp": fp}
            for start, end, val in spans]


YEARS = [*_filing("k-2024", "2025-02-14", ("2024-01-01", "2024-12-31", 100), form="10-K", fp="FY"),
         *_filing("k-2025", "2026-02-13", ("2025-01-01", "2025-12-31", 110), form="10-K", fp="FY")]


def _record(*usd, units=None, tags=None) -> set:
    """The calendar's record from the 10-Ks' years, ``usd`` net income items beside them, and more units or tags."""
    node = {"units": {"USD": [*YEARS, *usd], **(units or {})}}
    return _rolling(normalize_companyfacts(7, {"facts": {"us-gaap": {"NetIncomeLoss": node, **(tags or {})}}})[1])


def test_a_partial_rolling_year_is_on_record_only_where_the_calendar_knows_it_interim():
    # Inside a completed fiscal year, or in the year in progress by its earliest filing's quarter; before every
    # completed year nothing marks it interim, and absence of annual evidence quarantines nothing.
    inside = _filing("q-2025", "2025-05-08", ("2025-01-01", "2025-03-31", 7), ("2024-04-01", "2025-03-31", 7))
    ahead = _filing("q-2026", "2026-05-07", ("2026-01-01", "2026-03-31", 9), ("2025-04-01", "2026-03-31", 9))
    before = _filing("q-2023", "2023-05-09", ("2023-01-01", "2023-03-31", 5), ("2022-04-01", "2023-03-31", 5))
    assert _record(*inside, *ahead, *before) == {
        ("net_income", "us-gaap:NetIncomeLoss", "2024-04-01", "2025-03-31", "q-2025", "USD", 7.0),
        ("net_income", "us-gaap:NetIncomeLoss", "2025-04-01", "2026-03-31", "q-2026", "USD", 9.0)}


def test_a_filing_whose_own_currency_is_another_leaves_no_record():
    # its items in the series currency are convenience translations, which the collector never reads
    # (``filing_currencies``): a rolling year among them is no evidence either
    usd = _filing("q-eur", "2025-05-08", ("2025-01-01", "2025-03-31", 8), ("2024-04-01", "2025-03-31", 8))
    eur = _filing("q-eur", "2025-05-08", ("2025-01-01", "2025-03-31", 7), ("2024-04-01", "2025-03-31", 7))
    revenue = {"Revenues": {"units": {"EUR": _filing("q-eur", "2025-05-08", ("2025-01-01", "2025-03-31", 70))}}}
    assert _record(*usd, units={"EUR": eur}, tags=revenue) == set()


# Another filing's quarter, and a 10-Q's rolling year equal to it from its start (E291's shape)
PART = _filing("q-2024", "2024-08-08", ("2024-04-01", "2024-06-30", 7), fp="Q2")[0]
ROLLING = _filing("q-2025", "2025-05-08", ("2024-04-01", "2025-03-31", 7))[0]


@pytest.mark.parametrize("fp", ["Q1", None])
def test_a_rolling_year_equal_to_another_filings_part_is_on_record(fp):
    assert _record(PART, {**ROLLING, "fp": fp}) == {
        ("net_income", "us-gaap:NetIncomeLoss", "2024-04-01", "2025-03-31", "q-2025", "USD", 7.0)}


@pytest.mark.parametrize("field, value", [
    ("accn", ["q-2025"]), ("accn", {"accn": "q-2025"}), ("accn", None), ("accn", 2025), ("fp", ["Q1"]),
    ("fp", {"fp": "Q1"}), ("fp", 1), pytest.param("val", 10**400, id="val-past-float"),
    pytest.param("val", -10**400, id="val-past-float-negative"), ("val", float("inf")), ("val", float("nan"))])
def test_a_partial_year_in_a_shape_sec_never_sends_leaves_no_record_and_breaks_no_read(field, value):
    # No check reads a partial year before the collector puts it back for the calendar, which takes only a string
    # accession, a string fp or none, and a value a float holds: the payload reads as it does without the year. A
    # value rides its part, here a proxy's quarter, which admission skips unread too.
    part = {**PART, "val": value, "form": "DEF 14A"} if field == "val" else PART

    def payload(*usd):
        return {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [*YEARS, *usd]}}}}}

    year = {**ROLLING, field: value}
    assert normalize_companyfacts(7, payload(part, year)) == normalize_companyfacts(7, payload(part))


# The year in progress (2026): its Q1 10-Q's copy of a rolling year is partial (its own quarter); a later filing's
# copy competes, is partial too (its own six months), or ties the first on its filing date, listed after it
FIRST = _filing("q1-2026", "2026-05-07", ("2026-01-01", "2026-03-31", 9), ("2025-04-01", "2026-03-31", 9))
LATER = {"admitted": _filing("q2-2026", "2026-08-06", ("2025-04-01", "2026-03-31", 9), fp="Q2"),
         "partial": _filing("q2-2026", "2026-08-06", ("2025-04-01", "2026-03-31", 9), ("2026-01-01", "2026-06-30", 9),
                            fp="Q2"),
         "filed the same day": _filing("qa-2026", "2026-05-07", ("2025-04-01", "2026-03-31", 9), form="10-Q/A",
                                       fp="Q2")}
# A rolling year whose only copy under NetIncomeLoss, the first tag, is partial (its own filing's quarter), beside a
# copy under ProfitLoss that competes
FIRST_TAG = _filing("q-2025", "2025-05-08", ("2025-01-01", "2025-03-31", 7), ("2024-04-01", "2025-03-31", 7))
PROFIT = {"ProfitLoss": {"units": {"USD": _filing("p-2025", "2025-05-09", ("2024-04-01", "2025-03-31", 8))}}}


@pytest.mark.parametrize("later", sorted(LATER))
def test_a_rolling_year_two_10qs_carry_stays_on_record_as_one_year(later):
    # Before the rule both copies competed as one year, interim by its earliest filing's quarter (a tie on the date
    # going by list order), so both are on record, and the repair quarantines the latest-filed one, the winner: the
    # row a sync before 2026-10-10 stored.
    from app.services import quarterly_fact_repair

    payload = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [*YEARS, *FIRST, *LATER[later]]}}}}}
    facts, meta = normalize_companyfacts(7, payload)
    winner = LATER[later][0]["accn"]
    assert _rolling(meta) == {("net_income", "us-gaap:NetIncomeLoss", "2025-04-01", "2026-03-31", accession, "USD", 9.0)
                              for accession in ("q1-2026", winner)}
    stored = {"company_id": 7, "filing_id": None, "concept": "net_income", "raw_tag": "us-gaap:NetIncomeLoss",
              "unit": "USD", "period_start": "2025-04-01", "period_end": "2026-03-31", "fiscal_year": 2026,
              "fiscal_period": "FY", "value": 9.0, "form": "10-Q", "accession": winner,
              "source": "companyfacts", "reconciled": True, "is_latest": True, "provenance": None}
    updates, _inserts = quarterly_fact_repair._calendar_relabels({1: stored}, facts, meta)
    assert updates[1]["is_latest"] is False


def test_the_first_tag_with_a_copy_holds_the_year_on_record_as_before_the_rule():
    # ProfitLoss's copy wins the year's row-less key now, but before the rule NetIncomeLoss held it: only its copy is
    # the record, as only its copy was a row a sync could store
    assert _record(*FIRST_TAG, tags=PROFIT) == {
        ("net_income", "us-gaap:NetIncomeLoss", "2024-04-01", "2025-03-31", "q-2025", "USD", 7.0)}


def test_the_calendars_record_is_the_one_the_rule_never_touched(payloads, monkeypatch):
    # every cached payload and every shape above: the exclusions, entry for entry and in order, are those the
    # calendar keeps with the partial-year rule off
    from app.services.facts import companyfacts, currency

    def net_income(*usd, tags=None):
        return {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [*YEARS, *usd]}}, **(tags or {})}}}

    shapes = {**payloads, "another filing's part": net_income(PART, ROLLING),
              "the first tag's year": net_income(*FIRST_TAG, tags=PROFIT),
              **{f"two 10-Qs, the later {later}": net_income(*FIRST, *LATER[later]) for later in LATER},
              "the interim edges": net_income(
                  *_filing("q-2025", "2025-05-08", ("2025-01-01", "2025-03-31", 7), ("2024-04-01", "2025-03-31", 7)),
                  *_filing("q-2023", "2023-05-09", ("2023-01-01", "2023-03-31", 5), ("2022-04-01", "2023-03-31", 5)))}
    def record():
        return {name: normalize_companyfacts(9, payload)[1].get("calendar_exclusions")
                for name, payload in shapes.items()}

    ruled = record()
    monkeypatch.setattr(currency, "without_partial_years", lambda items: list(items))
    monkeypatch.setattr(companyfacts, "partial_years", lambda items: [])
    assert record() == ruled and all(ruled[name] for name in ("ARTW", "LMB", "another filing's part"))


def test_the_calendars_record_moves_no_row(payloads, monkeypatch):
    # handed no partial year, the collector gives every payload the same rows and the same meta but the record
    from app.services.facts import companyfacts

    def read(payload):
        facts, meta = normalize_companyfacts(8, payload)
        return facts, {key: value for key, value in meta.items() if key != "calendar_exclusions"}

    with_record = {name: read(payload) for name, payload in payloads.items()}
    monkeypatch.setattr(companyfacts, "partial_years", lambda items: [])
    assert {name: read(payload) for name, payload in payloads.items()} == with_record


def test_the_restatement_census_indexes_every_item():
    """Its evidence index reads every tag, where a real year can equal its part: AMT's Q1 2020 10-Q
    (0001053507-20-000093) reports the 425.7M it paid for a redeemable noncontrolling interest in Q1 2019 as that
    quarter and as FY2019, as its 10-K does. Across every tag of 696 cached payloads the rule drops 3,157 items, 2,392
    of them such years at 297 companies (none on the collector's duration tags), so the index keeps every item."""
    from scripts.restatement_census import _accession_index

    accn = "0001053507-20-000093"
    items = [_item("2019-01-01", "2019-03-31", 425700000, accn=accn),
             _item("2019-01-01", "2019-12-31", 425700000, accn=accn)]
    assert without_partial_years(items) == items[:1]
    usgaap = {"PaymentsForRepurchaseOfRedeemableNoncontrollingInterest": {"units": {"USD": items}}}
    assert [entry[2:] for entry in _accession_index(usgaap, {accn})[accn]] == [
        ("2019-01-01", "2019-03-31", 425700000), ("2019-01-01", "2019-12-31", 425700000)]


# --- the gate (CLAUDE.md rule 12): every companyfacts reader goes through the rule ------------------------------------
#
# A read of a ``units`` map in backend/app and backend/scripts is the string "units" anywhere but a dict display's key
# (``x["units"]``, ``x.get("units")``, ``itemgetter("units")``, ``case {"units": ...}``, a record path, a local alias),
# a name bound to "units" at module or class level in any scanned module, wherever it is used (``UNITS``,
# ``Keys.UNITS``, imported or annotated), or an attribute named ``units``. READERS pins each scope's count of them
# (Class.method, outer.inner, or <module> for module-level code and its lambdas) and the shape of its code:
# - "rule": it calls admitted_items or without_partial_years;
# - "proxy": it calls is_proxy_form, which tests/unit/test_quarterly_proxy_repair.py holds to keeping proxies alone;
# - "no value": a function that, nested code included, reads no item's "val" (the string, a name bound to it, or an
#   attribute so named), nor does any scope that names it (a function with its nested code, a module or class body in
#   its own code): in its own module, or in a module importing it by any form (``from m import f [as g]``,
#   ``import m [as a]``, ``from p import m``, relative) or importing the package whose ``__init__`` imports it;
# - "raw": none of these, pinned only with the reason it reads every item.
# A new scope, a new read in a pinned scope, or a pinned scope that changes shape fails. Named blind spots: a key or a
# name built at run time; items handed on to code that reads the value without naming the scope (a helper called with
# them, a caller's caller); a read swapped for another in a pinned scope, which keeps its count; a "rule" scope that
# passes instant=True for a duration list, or reads one list raw beside the one it rules; which way a "proxy" scope
# uses is_proxy_form; items whose ``accn`` names no filing, or one filing for many, in a "rule" scope (E278's instance
# items carry "" for their one filing: test_the_instance_paths_choice_ties_one_filings_facts). The collector, authority
# and fallback tests above hold the three readers that choose a winner.

RULE = {"admitted_items", "without_partial_years"}
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
READERS = {  # (path, scope): (reads, shape)
    ("app/services/edgar/instance/financial_revenue.py", "_choose"): (1, "no value"),
    ("app/services/edgar/xbrl_companyfacts.py", "select_fact_data_with_concept"): (2, "rule"),
    ("app/services/facts/companyfacts.py", "_collect_companyfacts_values"): (1, "rule"),
    ("app/services/facts/currency.py", "_filing_pick"): (1, "rule"),
    ("app/services/facts/currency.py", "payload_view"): (2, "no value"),  # each filing's accession and filed date
    ("app/services/facts/fi_revenue.py", "_by_filing"): (1, "rule"),
    ("app/services/facts/fi_revenue.py", "_items"): (1, "rule"),
    ("app/services/facts/reconcile.py", "extract_authoritative_values"): (1, "rule"),
    ("app/services/facts/reporting_basis.py", "_items"): (1, "no value"),  # its callers count items by form
    ("app/services/proxy_fact_repair.py", "proxy_items"): (1, "proxy"),
    ("scripts/financial_revenue_preview.py", "deployed_rule"): (1, "rule"),
    ("scripts/native_delivery_probe.py", "plan"): (1, "no value"),  # an eval unit manifest's units
    ("scripts/native_delivery_probe.py", "run"): (1, "no value"),
    ("scripts/restatement_census.py", "_accession_index"): (1, "raw"),  # evidence of every tag, as the test above
}


def _bound(trees) -> dict[str, set[str]]:
    """Each string's names, bound at module or class level (in an if or a try block too) in any of ``trees``."""
    names: dict[str, set[str]] = {}
    for tree in trees:
        todo = list(tree.body)
        while todo:
            node = todo.pop()
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant):
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    if isinstance(target, ast.Name) and isinstance(node.value.value, str):
                        names.setdefault(node.value.value, set()).add(target.id)
            elif not isinstance(node, FUNCTIONS):
                todo.extend(ast.iter_child_nodes(node))
    return names


def _key(node, key: str, names: set[str]) -> bool:
    """``node`` is ``key``: the string, a name bound to it, or an attribute so named."""
    return (isinstance(node, ast.Constant) and node.value == key) or (
        isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names) or (
        isinstance(node, ast.Attribute) and node.attr in names | {key})


class _Reads(ast.NodeVisitor):
    """One module's reads of a ``units`` map per scope, each scope's definitions, and the scopes naming each name."""

    def __init__(self, tree: ast.Module, names: set[str]):
        self.names, self.stack, self.depth = names, [], 0
        self.reads: dict[str, int] = {}
        self.scopes: dict[str, list[ast.AST]] = {"<module>": [tree]}
        self.refs: dict[str, set[str]] = {}
        self.visit(tree)

    def _here(self) -> str:
        return ".".join(self.stack) or "<module>"

    def _scope(self, node):
        self.stack.append(node.name)
        self.scopes.setdefault(self._here(), []).append(node)
        self.depth += isinstance(node, FUNCTIONS)
        self.generic_visit(node)
        self.depth -= isinstance(node, FUNCTIONS)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def _read(self):
        self.reads[self._here()] = self.reads.get(self._here(), 0) + 1

    def _constant(self, node, targets) -> bool:  # a module or class constant: each use of its name is the read
        return not self.depth and isinstance(node.value, ast.Constant) and all(
            isinstance(target, ast.Name) for target in targets)

    def visit_Assign(self, node):
        if not self._constant(node, node.targets):
            self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if not self._constant(node, [node.target]):
            self.generic_visit(node)

    def visit_Dict(self, node):  # a dict display's keys build a payload
        for child in ast.iter_child_nodes(node):
            if not (any(child is key for key in node.keys) and _key(child, "units", self.names)):
                self.visit(child)

    def visit_Constant(self, node):
        if node.value == "units":
            self._read()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.refs.setdefault(node.id, set()).add(self._here())
            if node.id in self.names:
                self._read()

    def visit_Attribute(self, node):
        self.refs.setdefault(node.attr, set()).add(self._here())
        if node.attr in self.names | {"units"}:
            self._read()
        self.generic_visit(node)


def _own(scope: ast.AST):
    """A scope's own nodes: its nested functions and classes are scopes of their own, its lambdas are not."""
    todo = list(ast.iter_child_nodes(scope))
    while todo:
        node = todo.pop()
        yield node
        if not isinstance(node, (*FUNCTIONS, ast.ClassDef)):
            todo.extend(ast.iter_child_nodes(node))


def _calls(scope: ast.AST, names: set[str]) -> bool:
    return any(isinstance(node, ast.Call) and (getattr(node.func, "id", None) in names
                                               or getattr(node.func, "attr", None) in names) for node in _own(scope))


def _reads_value(scopes, names: set[str]) -> bool:
    """``scopes`` read an item's "val" anywhere but a dict display's key: a function with its nested code, a module or
    class body in its own code alone."""
    for scope in scopes:
        nodes = list(ast.walk(scope) if isinstance(scope, FUNCTIONS) else _own(scope))
        keys = {id(key) for node in nodes if isinstance(node, ast.Dict) for key in node.keys}
        if any(id(node) not in keys and _key(node, "val", names) for node in nodes):
            return True
    return False


def _shape(scope: ast.AST, names: set[str]) -> str:
    """One definition's shape, before the scopes naming it are read."""
    if _calls(scope, RULE):
        return "rule"
    if _calls(scope, {"is_proxy_form"}):
        return "proxy"
    return "no value" if isinstance(scope, FUNCTIONS) and not _reads_value([scope], names) else "raw"


def _imports(tree: ast.Module, module: str) -> tuple[set[str], set[str]]:
    """The modules ``module`` imports names from, and those it binds to a name, by any form, relative ones resolved."""
    package = module[:-len(".__init__")] if module.endswith(".__init__") else module.rpartition(".")[0]
    sources, bound = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bound |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            parts = package.split(".")[:len(package.split(".")) + 1 - node.level] if node.level else []
            base = ".".join(parts + [node.module] if node.module else parts)
            sources.add(base)
            bound |= {f"{base}.{alias.name}" for alias in node.names}
    return sources, bound


def _reaches(imports: tuple[set[str], set[str]], module: str) -> bool:
    """An import reaches ``module``: names imported from it, it or a package above it bound, or a sibling by name."""
    sources, bound = imports
    return any(module == name or module.endswith(f".{name}") for name in sources) or any(
        module == name or module.startswith(f"{name}.") or module.endswith(f".{name}") for name in bound)


def _scan(root: Path, dirs: tuple[str, ...]) -> dict[tuple[str, str], tuple[int, str]]:
    """{(path, scope): (reads, shape)} over the .py files under ``dirs``."""
    trees = {".".join(path.relative_to(root).with_suffix("").parts): (path, ast.parse(path.read_text()))
             for name in dirs for path in sorted((root / name).rglob("*.py"))}
    names = _bound(tree for _path, tree in trees.values())
    units, val = names.get("units", set()), names.get("val", set())
    reads = {module: _Reads(tree, units) for module, (_path, tree) in trees.items()}
    imports = {module: _imports(tree, module) for module, (_path, tree) in trees.items()}
    found = {}
    for module, (path, _tree) in trees.items():
        for scope, count in reads[module].reads.items():
            shapes = {_shape(node, val) for node in reads[module].scopes[scope]}
            shape = shapes.pop() if len(shapes) == 1 else "raw"
            if shape == "no value":
                name = scope.rpartition(".")[2]
                targets = {module} | {other[:-len(".__init__")] for other in trees
                                      if other.endswith(".__init__") and _reaches(imports[other], module)}
                for other, (_other_path, other_tree) in trees.items():
                    if other != module and not any(_reaches(imports[other], target) for target in targets):
                        continue
                    aliases = {name} | {alias.asname for node in ast.walk(other_tree)
                                        if isinstance(node, ast.ImportFrom)
                                        for alias in node.names if alias.name == name and alias.asname}
                    callers = {caller for alias in aliases for caller in reads[other].refs.get(alias, ())}
                    callers -= {scope} if other == module else set()
                    if any(_reads_value(reads[other].scopes[caller], val) for caller in callers):
                        shape = "raw"
            found[(str(path.relative_to(root)), scope)] = (count, shape)
    return found


def test_every_companyfacts_reader_is_pinned_with_its_shape():
    found = _scan(BACKEND, ("app", "scripts"))
    drift = {key: (found.get(key), READERS.get(key)) for key in found.keys() | READERS.keys()
             if found.get(key) != READERS.get(key)}
    assert not drift, f"route each companyfacts read through admitted_items or without_partial_years, then pin it " \
                      f"in READERS ((found, pinned) per scope): {drift}"


DROPPED = {"partial_years", "_partial"}  # the helper listing the years the rule drops, and the predicate it wraps


def _dropped_year_readers(root: Path) -> set[tuple[str, str, str]]:
    """(path, scope, name) for each name of DROPPED, or an alias of one, in ``root``'s app and scripts: imported
    ("<import>"), named in a scope as READERS names it (a call, a reference handed on, module-level code), or written
    as a string ("<string>")."""
    found = set()
    for path in sorted((root / "app").rglob("*.py")) + sorted((root / "scripts").rglob("*.py")):
        tree, where = ast.parse(path.read_text()), path.relative_to(root).as_posix()
        imports = (node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
        aliases = {alias.asname or alias.name for node in imports for alias in node.names
                   if alias.name.rpartition(".")[2] in DROPPED}
        found |= {(where, "<import>", alias) for alias in aliases}
        found |= {(where, scope, name) for name, scopes in _Reads(tree, set()).refs.items() if name in DROPPED | aliases
                  for scope in scopes}
        found |= {(where, "<string>", node.value) for node in ast.walk(tree)
                  if isinstance(node, ast.Constant) and node.value in DROPPED}
    return found


def test_only_the_collector_reads_the_years_the_rule_drops():
    """``partial_years`` feeds the calendar's record alone, through the collector: any other scope naming it, or
    ``_partial``, which it and ``without_partial_years`` wrap, would read the years every other reader is kept from.
    Named blind spots: a name built at run time, a copy of the predicate under another name, and the complement of
    ``without_partial_years`` (a list less the items it keeps)."""
    assert _dropped_year_readers(BACKEND) == {
        ("app/services/facts/fiscal_naming.py", "without_partial_years", "_partial"),
        ("app/services/facts/fiscal_naming.py", "partial_years", "_partial"),
        ("app/services/facts/companyfacts.py", "<import>", "partial_years"),
        ("app/services/facts/companyfacts.py", "_collect_companyfacts_values", "partial_years")}


DROPPED_READERS = """
from app.services.facts import fiscal_naming
from app.services.facts.fiscal_naming import _partial, partial_years as years

EVERY = fiscal_naming.partial_years([])


def handed_on(lists):
    return map(years, lists)


def predicate(items):
    return _partial(items)


def by_string():
    return getattr(fiscal_naming, "partial_years")
"""


def test_the_dropped_year_gate_reads_each_planted_reader(tmp_path):
    for name in ("app", "scripts"):
        (tmp_path / name).mkdir()
    (tmp_path / "scripts" / "planted.py").write_text(DROPPED_READERS)
    assert _dropped_year_readers(tmp_path) == {
        ("scripts/planted.py", "<import>", "_partial"), ("scripts/planted.py", "<import>", "years"),
        ("scripts/planted.py", "<module>", "partial_years"), ("scripts/planted.py", "handed_on", "years"),
        ("scripts/planted.py", "predicate", "_partial"), ("scripts/planted.py", "<string>", "partial_years")}


PLANTED = """
import operator
from typing import Final

UNITS = "units"
KEY: Final = "units"
VAL = "val"
FAST = False
try:
    TRIED = "units"
except ImportError:
    pass


class Keys:
    CLASS_UNITS = "units"


def mixed(node_a, node_b):  # a rule call beside a raw read
    admitted_items(node_a["units"]["USD"], instant=False)
    return max(node_b["units"]["USD"], key=len)


class Annual:  # two methods of one name
    def values(self, node):
        return node["units"]["USD"][0]["val"]


class Quarterly:
    def values(self, node):
        return without_partial_years(node["units"]["USD"])


if FAST:  # two definitions of one name
    def twice(node):
        return without_partial_years(node["units"]["USD"])
else:
    def twice(node):
        return node["units"]["USD"][0]["val"]


def by_constant(node):
    return node[UNITS]["USD"][0]["val"]


def by_annotated(node):
    return node.get(KEY)["USD"][0][VAL]


def by_class_key(node):
    return node[Keys.CLASS_UNITS]["USD"][0]["val"]


def by_tried(node):
    return node[TRIED]["USD"][0]["val"]


def by_getter(node):
    return operator.itemgetter("units")(node)["USD"][0]["val"]


def by_alias(node):
    key = "units"
    return node[key]["USD"][0]["val"]


def by_attribute(concept):
    return concept.units["USD"][0].val


def popped(node):
    return node.pop("units")["USD"][0].get("val")


def matched(node):
    match node:
        case {"units": {"USD": items}}:
            return items[0]["val"]


peek = lambda node: node.get("units")["USD"][0]["val"]


def payload(items):  # a dict display's key builds a payload, and is no read
    return {"units": {"USD": [{"val": item} for item in items]}}


def _every(node):  # an iterator that reads no value itself
    yield from node["units"]["USD"]


def picks(node):  # but whose caller does
    return max(_every(node), key=lambda item: item["filed"])["val"]


class Reader:
    def _listed(self, node):  # a list, read through self
        return list(node["units"]["USD"])

    def latest(self, node):
        return self._listed(node)[-1]["val"]


def _nested(node):  # its nested function reads the value
    def pick(items):
        return items[0]["val"]
    return pick(node["units"]["USD"])


def _mapped(node):
    return node["units"]["USD"]


def mapped(nodes):  # names it without calling it
    return [item["val"] for items in map(_mapped, nodes) for item in items]


def _counted(node):
    return node["units"]["USD"]


def counts(node):
    return sum(1 for item in _counted(node) if item.get("form") == "10-K")


def by_parameter(node, key):  # a named blind spot: the key held in a parameter
    return node.get(key)["USD"][0]["val"]
"""


def test_the_gate_reads_each_planted_reader(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "planted.py").write_text(PLANTED)
    found = {scope: shape for (_path, scope), shape in _scan(tmp_path, ("scripts",)).items()}
    assert found == {"mixed": (2, "rule"), "Annual.values": (1, "raw"), "Quarterly.values": (1, "rule"),
                     "twice": (2, "raw"), "by_constant": (1, "raw"), "by_annotated": (1, "raw"),
                     "by_class_key": (1, "raw"), "by_tried": (1, "raw"), "by_getter": (1, "raw"),
                     "by_alias": (1, "raw"), "by_attribute": (1, "raw"), "popped": (1, "raw"), "matched": (1, "raw"),
                     "<module>": (1, "raw"), "_every": (1, "raw"), "Reader._listed": (1, "raw"), "_nested": (1, "raw"),
                     "_mapped": (1, "raw"), "_counted": (1, "no value")}  # "mixed" pinned at one read fails its second
    (tmp_path / "scripts" / "planted.py").write_text(PLANTED.replace("    return max(_every(node), key=lambda item: "
                                                                     "item[\"filed\"])[\"val\"]\n", "    pass\n"))
    assert _scan(tmp_path, ("scripts",))[("scripts/planted.py", "_every")] == (1, "no value")


LISTER = "def _every(node):\n    return list(node[\"units\"][\"USD\"])\n"
READS = "\n\n\ndef latest(node):\n    return {}(node)[-1][\"val\"]\n"
COUNTS = "\n\n\ndef count(node):\n    return len({}(node))\n"


@pytest.mark.parametrize("user, code, shape", [
    ("user.py", "from scripts.pkg.lister import _every" + READS.format("_every"), "raw"),
    ("user.py", "from scripts.pkg.lister import _every as every" + READS.format("every"), "raw"),
    ("user.py", "from scripts.pkg import lister" + READS.format("lister._every"), "raw"),
    ("user.py", "import scripts.pkg.lister as basis" + READS.format("basis._every"), "raw"),
    ("user.py", "import scripts.pkg.lister" + READS.format("scripts.pkg.lister._every"), "raw"),
    ("pkg/user.py", "from .lister import _every" + READS.format("_every"), "raw"),
    ("pkg/user.py", "from . import lister" + READS.format("lister._every"), "raw"),
    ("user.py", "from scripts.pkg import _every" + READS.format("_every"), "raw"),  # through the package's __init__
    ("user.py", "from scripts.pkg.lister import _every" + COUNTS.format("_every"), "no value"),
    ("user.py", "from scripts import other" + READS.format("other._every"), "no value"),  # another module's
    ("user.py", "from scripts.pkg.lister import _every\n\nLATEST = _every({})[-1][\"val\"]\n", "raw"),
    ("user.py", "from scripts.pkg.lister import _every\n\nCOUNT = len(_every({}))" + READS.format("max"), "no value"),
])
def test_a_scope_named_from_another_module_by_any_import_form_is_read(tmp_path, user, code, shape):
    (tmp_path / "scripts" / "pkg").mkdir(parents=True)
    (tmp_path / "scripts" / "pkg" / "__init__.py").write_text("from .lister import _every\n")
    (tmp_path / "scripts" / "pkg" / "lister.py").write_text(LISTER)
    (tmp_path / "scripts" / user).write_text(code)
    assert _scan(tmp_path, ("scripts",)) == {("scripts/pkg/lister.py", "_every"): (1, shape)}
