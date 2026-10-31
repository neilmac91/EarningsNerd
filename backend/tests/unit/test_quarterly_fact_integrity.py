"""Regression evidence for cumulative cash flows and reported-only quarterly EPS."""
from copy import deepcopy
from datetime import date

import pytest

from app.services import facts_service as svc

OCF = "NetCashProvidedByUsedInOperatingActivities"


def _item(value, start, end, accession, filed, *, fp="FY", fy=2024, form="10-Q"):
    return {"val": value, "start": start, "end": end, "accn": accession,
            "filed": filed, "fp": fp, "fy": fy, "form": form}


def _cumulative_payload():
    # Meta's issuer-published 2024 cumulative CFO, dollars. These observations
    # reproduce the prior missing Q2/Q3 and incorrectly flagged Q4 behavior.
    return {"facts": {"us-gaap": {OCF: {"units": {"USD": [
        _item(19_246_000_000, "2024-01-01", "2024-03-31", "Q1", "2024-04-25", fp="Q1"),
        _item(38_616_000_000, "2024-01-01", "2024-06-30", "Q2", "2024-08-01", fp="Q2"),
        _item(63_340_000_000, "2024-01-01", "2024-09-30", "Q3", "2024-10-31", fp="Q3"),
        _item(91_328_000_000, "2024-01-01", "2024-12-31", "FY", "2025-01-30", form="10-K"),
    ]}}}}}


def _normalize(payload):
    facts, meta = svc.normalize_companyfacts(1, payload)
    return {(f["concept"], f["fiscal_year"], f["fiscal_period"]): f for f in facts}, meta


def test_meta_cash_flows_have_four_quarters_and_traceable_calculations():
    facts, meta = _normalize(_cumulative_payload())
    for quarter, expected, formula in [
        ("Q1", 19_246_000_000, None),
        ("Q2", 19_370_000_000, "YTD6 - Q1"),
        ("Q3", 24_724_000_000, "YTD9 - YTD6"),
        ("Q4", 27_988_000_000, "FY - YTD9"),
    ]:
        fact = facts[("operating_cash_flow", 2024, quarter)]
        assert fact["value"] == expected
        assert fact["reconciled"] is True
        provenance = fact["provenance"]
        assert provenance["formula"] == formula
        assert provenance["validation"] == "passed"
        if formula:
            assert provenance["method"] == "calculated"
            assert provenance["period_calculation"] is True
            assert provenance["calculation_version"] == "quarterly-v2"
            high, low = provenance["inputs"]
            assert high["value"] - low["value"] == expected
            assert high["period_start"] == low["period_start"] == "2024-01-01"
            assert high["raw_tag"] == low["raw_tag"] == "us-gaap:" + OCF
            assert high["filed_at"] and low["filed_at"]
    assert meta["quarterly_excluded_count"] == 0


def test_newer_unchanged_comparative_preserves_compatible_operand_vintage():
    payload = _cumulative_payload()
    items = payload["facts"]["us-gaap"][OCF]["units"]["USD"]
    items.append({**items[-1], "accn": "FY-LATER", "filed": "2026-02-01", "fy": 2025})
    facts, _ = _normalize(payload)
    q4 = facts[("operating_cash_flow", 2024, "Q4")]
    assert q4["value"] == 27_988_000_000
    assert q4["accession"] == "FY-LATER"  # latest selected observation remains the identity
    assert q4["provenance"]["inputs"][0]["accession"] == "FY"  # actual compatible evidence


def test_independently_restated_annual_operand_is_withheld():
    payload = _cumulative_payload()
    items = payload["facts"]["us-gaap"][OCF]["units"]["USD"]
    items.append({**items[-1], "val": 100_000_000_000, "accn": "FY-A", "filed": "2025-02-03"})
    facts, meta = _normalize(payload)
    assert ("operating_cash_flow", 2024, "Q4") not in facts
    excluded = next(e for e in meta["quarterly_exclusions"] if e["fiscal_period"] == "Q4")
    assert excluded["reason"] == "incompatible_vintages"
    assert len(excluded["inputs"]) == 2
    assert facts[("operating_cash_flow", 2024, "FY")]["value"] == 100_000_000_000


def test_same_accession_restated_pair_remains_eligible():
    payload = _cumulative_payload()
    items = payload["facts"]["us-gaap"][OCF]["units"]["USD"]
    items.extend([
        {**items[-1], "val": 100_000_000_000, "accn": "RESTATED", "filed": "2025-02-03"},
        {**items[-2], "val": 70_000_000_000, "accn": "RESTATED", "filed": "2025-02-03"},
    ])
    facts, _ = _normalize(payload)
    q4 = facts[("operating_cash_flow", 2024, "Q4")]
    assert q4["value"] == 30_000_000_000
    assert q4["reconciled"] is True
    assert {i["accession"] for i in q4["provenance"]["inputs"]} == {"RESTATED"}


@pytest.mark.parametrize("change", ["scope", "start", "filing_date", "future_prior"])
def test_incompatible_cumulative_operands_never_create_q2(change):
    payload = _cumulative_payload()
    items = payload["facts"]["us-gaap"][OCF]["units"]["USD"]
    if change == "scope":
        prior = items.pop(0)
        payload["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"] = {
            "units": {"USD": [prior]}}
    elif change == "start":
        items[1]["start"] = "2024-01-02"
    elif change == "filing_date":
        items[0]["filed"] = "unknown"
    else:
        items[0]["filed"] = "2025-01-15"
    facts, _ = _normalize(payload)
    assert ("operating_cash_flow", 2024, "Q2") not in facts


def test_reported_quarter_wins_and_fcf_keeps_the_full_calculation_chain():
    payload = _cumulative_payload()
    gaap = payload["facts"]["us-gaap"]
    gaap[OCF]["units"]["USD"].append(
        _item(27_989_000_000, "2024-10-01", "2024-12-31", "RELEASE", "2025-01-30", form="8-K")
    )
    gaap["PaymentsToAcquirePropertyPlantAndEquipment"] = {"units": {"USD": [
        _item(22_831_000_000, "2024-01-01", "2024-09-30", "Q3", "2024-10-31", fp="Q3"),
        _item(37_256_000_000, "2024-01-01", "2024-12-31", "FY", "2025-01-30", form="10-K"),
    ]}}
    facts, _ = _normalize(payload)
    assert facts[("operating_cash_flow", 2024, "Q4")]["source"] == "companyfacts"
    fcf = facts[("free_cash_flow", 2024, "Q4")]
    assert fcf["value"] == 13_564_000_000
    assert fcf["reconciled"] is True
    assert fcf["provenance"]["period_calculation"] is True
    capex_input = fcf["provenance"]["inputs"][1]
    assert capex_input["provenance"]["formula"] == "FY - YTD9"
    assert len(capex_input["provenance"]["inputs"]) == 2


def test_53_week_noncalendar_year_uses_fiscal_windows():
    payload = {"facts": {"us-gaap": {OCF: {"units": {"USD": [
        _item(10, "2023-01-29", "2023-04-29", "Q1", "2023-05-20", fp="Q1", fy=2024),
        _item(30, "2023-01-29", "2023-07-29", "Q2", "2023-08-20", fp="Q2", fy=2024),
        _item(60, "2023-01-29", "2023-10-28", "Q3", "2023-11-20", fp="Q3", fy=2024),
        _item(100, "2023-01-29", "2024-02-03", "FY", "2024-03-10", fy=2024, form="10-K"),
    ]}}}}}
    facts, _ = _normalize(payload)
    assert [facts[("operating_cash_flow", 2024, q)]["value"] for q in ("Q1", "Q2", "Q3", "Q4")] == [10, 20, 30, 40]
    assert facts[("operating_cash_flow", 2024, "Q4")]["period_start"] == date(2023, 10, 29)


@pytest.mark.parametrize("year,ni,eps,shares,reported", [
    (2023, [39098, 5709, 7788, 11583], [14.87, 2.20, 2.98, 4.39], [2629, 2596, 2612, 2641], 5.33),
    (2024, [62360, 12369, 13465, 15688], [23.86, 4.71, 5.16, 6.03], [2614, 2625, 2610, 2600], 8.02),
])
def test_meta_dilution_regression_has_no_synthetic_eps(year, ni, eps, shares, reported):
    periods = [("FY", "01-01", "12-31", f"{year+1}-02-01"),
               ("Q1", "01-01", "03-31", f"{year}-05-01"),
               ("Q2", "04-01", "06-30", f"{year}-08-01"),
               ("Q3", "07-01", "09-30", f"{year}-11-01")]
    gaap = {}
    for tag, unit, values in [("NetIncomeLoss", "USD", ni), ("EarningsPerShareDiluted", "USD/shares", eps),
                              ("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", shares)]:
        gaap[tag] = {"units": {unit: [
            _item(value, f"{year}-{start}", f"{year}-{end}", fp, filed, fp=fp, fy=year,
                  form="10-K" if fp == "FY" else "10-Q")
            for value, (fp, start, end, filed) in zip(values, periods)
        ]}}
    payload = {"facts": {"us-gaap": gaap}}
    facts, _ = _normalize(payload)
    assert ("eps_diluted", year, "Q4") not in facts
    assert ("net_income", year, "Q4") in facts
    gaap["EarningsPerShareDiluted"]["units"]["USD/shares"].append(
        _item(reported, f"{year}-10-01", f"{year}-12-31", "RELEASE", f"{year+1}-02-01", fy=year)
    )
    facts, _ = _normalize(payload)
    assert facts[("eps_diluted", year, "Q4")]["value"] == reported


def test_metrics_reject_different_duration_and_preserve_operand_reasons():
    facts, _ = _normalize(_cumulative_payload())
    ocf = facts[("operating_cash_flow", 2024, "Q4")]
    capex = {**deepcopy(ocf), "concept": "capital_expenditures", "value": 14_425_000_000,
             "period_start": date(2024, 1, 1)}
    assert svc.derive_same_period_metrics([ocf, capex]) == []
    capex["period_start"] = ocf["period_start"]
    capex["provenance"].update(validation="needs_review", reasons=["scope_conflict"])
    capex["reconciled"] = False
    fcf = svc.derive_same_period_metrics([ocf, capex])[0]
    assert fcf["reconciled"] is False
    assert fcf["provenance"]["validation"] == "needs_review"
    assert fcf["provenance"]["reasons"] == ["scope_conflict"]


def test_original_fiscal_year_controls_cash_calculations_and_year_end_instants():
    annual = _item(100, "2022-01-03", "2023-01-01", "FY22", "2023-02-16", fy=2022, form="10-K")
    later = {**annual, "accn": "FY23", "filed": "2024-02-16", "fy": 2023}
    payload = {"facts": {"us-gaap": {
        OCF: {"units": {"USD": [
            _item(60, "2022-01-03", "2022-10-02", "Q322", "2022-11-03", fp="Q3", fy=2022),
            annual, later,
            _item(30, "2023-01-02", "2023-04-02", "Q123", "2023-05-04", fp="Q1", fy=2023),
        ]}},
        "Assets": {"units": {"USD": [{**annual, "start": None, "val": 1000}]}},
    }}}
    facts, _ = _normalize(payload)
    assert facts[("operating_cash_flow", 2022, "FY")]["value"] == 100
    assert facts[("operating_cash_flow", 2022, "Q4")]["value"] == 40
    assert facts[("operating_cash_flow", 2023, "Q1")]["value"] == 30
    assert facts[("total_assets", 2022, "FY")]["value"] == 1000
