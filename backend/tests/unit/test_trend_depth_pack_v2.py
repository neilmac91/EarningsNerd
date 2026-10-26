"""Evidence pack version 2 (evals/trend_depth/{derived,passages,render,evidence}.py; DEEPSEEK-ERRORS.md §2 fixes 3, 4,
8, 9 and 11).

Pins: the added values (an operating cash flow / net income median and low, a same-year net-minus-operating margin)
and the debt-break checks register after every version-1 ID; the net-debt red flag says "net debt rose" when the
company was in net debt throughout; a long-term debt line that stops, or reads zero, while debt is still evident
is a break, and so is a debt line's onset (DE), a long-term line that already holds the current line total debt adds
to it, by the filer's own noncurrent figure (TGT FY2016-FY2018), and a one-year cash gap or a double count (MSFT, NVDA,
ORCL, COP, TGT), with no false one in the 20; everything built on a broken year is withheld from the render, a peer's broken
year included (a checked peer rank and median replace version 1's), and so is a long-term line reported as zero
there (ORCL); a check names the net-cash peer rank only when it withholds it; a line the filer reports and the pack
maps nowhere (CAT's current portion of long-term debt, KO's short-term investments) is a data check that withholds
nothing, and the net-debt flag then quotes no level; passages in millions carry their unit; a version-2 render puts derived cells in year order and a
legend on net-cash rows; a version-1 pack renders byte for byte as the frozen runs read it; and the committed
version-2 packs keep every version-1 ID and value. The builder is imported over a stub bootstrap, so no database,
settings or SEC call is touched.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib
import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import derived, passages, probes, render

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
YEARS = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023"]
TEN = [f"FY{year}" for year in range(2016, 2026)]

# The sha256 of each committed version-1 pack's render: the user message the frozen runs (eval-v1, dev-v4) sent.
V1_RENDERS = {
    "AMD": "ccdb50d2bed921a7e1f6aca9d6237084472de166b3927c7fb6377efa46e91785",
    "CAT": "6f9e7ba145c47d644fef8c8ad842390d7a0f54a107152b0dae13dc703f03c1be",
    "COP": "26adcb967079cf9656c3af18afb7c490603d625604f43c0c1b36110fd2805412",
    "COST": "9bc45ffb8299a3ef9cadda4a0417735aef2955ce7dea56de2e18361af32d018e",
    "CVX": "62dacffb3f9e19cd80776c739f95f2b5f86cf2ac8ee3427ac5063e12889c7e76",
    "DE": "f07dcacbd067735168fee3b8690b81a8b69bc1bdc92153361e2263600df39df6",
    "DUK": "43084ff3d86e65d03e9f7715698136b49727dcb7ae89c79e694079b7eafd44e6",
    "JPM": "7ed979829fb0274b4ad8db2f63c5c0791b82ba98009080e261bd2f94d79f55c5",
    "KO": "4200adb327ef99c88f804c6721936385be56c8c5b254b1f839e8f8ca002686b8",
    "MSFT": "273d5b77978acf9e0566a01d8cd8cae68069f42ed0207c7daa1ddd2bf7500a88",
    "NEE": "b99c5bf3c0ab027f3441c21ce87be6eb7e54cb96f80b66a91157f70f3b498d73",
    "NVDA": "62db222f3c68fe36278eaa9127c88e9a28c2090e29f5bf7c978385e23dc09b7f",
    "ORCL": "0e37ff2b9f2f7b09d261ab8d101d9c2361976dd1163c84722c18dcb2877b848b",
    "PG": "cf52952b2e29b1f682a89eb8fe5ed7cc7b006e0798e89a4168e2bbc9670abb02",
    "REGN": "1b71bc328376b0adfc5d0b2151380c9b858c687a1be2ae1bf12013f722f4758a",
    "RIVN": "d44ed3fff099ad6b9edd67e5cb0d182828960258a49bc1c24452d477719d5f26",
    "SNAP": "3b650936f5d0d900703cd3f225f04c2e9408144d657c54ea4cbf7e87dd2c3877",
    "TGT": "2865ff0269538fcc71c494a0cd5861c9f3ee016c6e153df51223445a1c85b9e4",
    "USB": "8ee65052bd839a56edd90ec0c8fe0d3e10bff77da1f31f521abcb97a64aaa292",
    "VRTX": "dab8b43e6dbb39a77b748709c767ef02574373f2b57f4f3aeba5ee74bf81b335",
}


def _load(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


def _registry(series: dict[str, dict[str, float]], prefix: str = "X", unit: str = "usd") -> derived.Registry:
    reg = derived.Registry()
    for key, points in series.items():
        for period, value in points.items():
            reg.add(prefix, key, key.replace("_", " "), period, value, unit, source="filed")
    return reg


def _every(value: float, years: list[str] = YEARS) -> dict[str, float]:
    return {year: value for year in years}


def _last_d(reg: derived.Registry) -> int:
    return max((int(vid[1:]) for vid in reg.values if vid.startswith("D")), default=0)


# --- Fix 3 and fix 9: added values, after every existing ID ---------------------------------------------------

def test_ocf_to_ni_window_median_and_low_are_appended_after_every_existing_id() -> None:
    reg = derived.Registry()
    for year, value in zip(YEARS, (1.4, 2.0, 0.9, 1.7, 1.2)):
        reg.add("D", "ocf_to_ni", "Operating cash flow / net income", year, value, "x")
    reg.add("D", "peer_median:net_margin", "Net margin: peer median", "FY2023", 9.0, "pct", source="peer")
    before = _last_d(reg)
    derived.version_two_values(reg, YEARS, "operating")
    low, mid = reg.get("low:ocf_to_ni", "FY2019..FY2023"), reg.get("median:ocf_to_ni", "FY2019..FY2023")
    assert low is not None and mid is not None
    assert (low.value, mid.value) == (0.9, 1.4)
    assert low.label == "Operating cash flow / net income window low (FY2021)" and low.unit == "x"
    assert int(low.id[1:]) > before and int(mid.id[1:]) > before
    assert reg.ref("high:ocf_to_ni", "FY2019..FY2023") is None  # depressed-income years make the high misleading


@pytest.mark.parametrize("profile", ["bank", "insurer"])
def test_ocf_to_ni_window_is_skipped_for_banks_and_insurers(profile: str) -> None:
    reg = derived.Registry()
    for year in YEARS:
        reg.add("D", "ocf_to_ni", "Operating cash flow / net income", year, 0.19, "x")
    derived.version_two_values(reg, YEARS, profile)
    assert reg.ref("median:ocf_to_ni", "FY2019..FY2023") is None and reg.ref("low:ocf_to_ni", "FY2019..FY2023") is None


def test_net_minus_operating_margin_pairs_the_same_year_only() -> None:
    # DE: the operating-margin row ends a year before the net-margin row; no value may pair the two years.
    reg = _registry({"net_margin": {"FY2021": 11.0, "FY2022": 12.5, "FY2023": 11.0},
                     "operating_margin": {"FY2021": 15.0, "FY2022": 17.5}}, prefix="F", unit="pct")
    derived.version_two_values(reg, YEARS, "operating")
    gaps = {p: reg.get("margin_gap:net_minus_operating", p) for p in YEARS}
    assert {p for p, v in gaps.items() if v is not None} == {"FY2021", "FY2022"}
    hit = gaps["FY2022"]
    assert hit.value == pytest.approx(-5.0) and hit.unit == "pp"
    assert hit.inputs == [reg.ref("net_margin", "FY2022"), reg.ref("operating_margin", "FY2022")]


# --- Fix 4: the net-debt red flag ------------------------------------------------------------------------------

def _net_cash_flag(values: list[float]) -> dict[str, Any]:
    reg = derived.Registry()
    for year, value in zip(YEARS, values):
        reg.add("D", "net_cash", "Net cash", year, value, "usd")
    return next(f for f in derived.red_flags(reg, YEARS, "operating", [], []) if f["kind"] == "net_debt_build")


def test_net_debt_flag_says_net_debt_rose_when_in_net_debt_throughout() -> None:
    flag = _net_cash_flag([-20.0e9, -18.0e9, -17.0e9, -24.9e9, -26.23e9])
    assert flag["detail"] == "Net debt rose 2 years in a row to $26.2 billion in FY2023."
    assert flag["persistence"] == 2 and len(flag["evidence"]) == 3


def test_net_debt_flag_keeps_fell_into_net_debt_when_the_run_crosses_zero() -> None:
    flag = _net_cash_flag([1.4e9, 0.2e9, -0.2e9, -0.27e9, -0.6e9])
    assert flag["detail"] == "Net cash fell 4 years in a row into net debt in FY2023."


# --- Fix 8: debt breaks, their checks, and what the render withholds -----------------------------------------

@pytest.mark.parametrize("series, expected", [
    # CVX, DE: the long-term line stops; the current portion goes on.
    ({"debt_noncurrent": _every(25e9, YEARS[:3]), "debt_current": _every(3e9)}, ["FY2022", "FY2023"]),
    # ORCL FY2022: the line reads zero between two years in the tens of billions.
    ({"debt_noncurrent": dict(zip(YEARS, (70e9, 76e9, 0.0, 86e9, 90e9))), "debt_current": _every(3e9)}, ["FY2021"]),
    # COP FY2016: a current portion of long-term debt and no long-term debt.
    ({"debt_noncurrent": _every(22e9, YEARS[1:]), "debt_current": {"FY2019": 1e9}}, ["FY2019"]),
    # REGN, SNAP: not yet borrowing; nothing else is owed, so no break.
    ({"debt_noncurrent": {"FY2019": 0.0, **_every(2e9, YEARS[1:])}}, []),
    # Repaid in full: no other line, interest collapses.
    ({"debt_noncurrent": _every(5e9, YEARS[:2]), "interest_expense": dict(zip(YEARS, (2e8, 2e8, 1e7, 0.0, 0.0)))}, []),
    # No other line, but interest holds: the debt is still there, unmapped.
    ({"debt_noncurrent": _every(5e9, YEARS[:2]), "interest_expense": _every(2e8)}, ["FY2021", "FY2022", "FY2023"]),
])
def test_debt_breaks(series: dict[str, dict[str, float]], expected: list[str]) -> None:
    assert derived.debt_breaks(_registry(series), YEARS) == expected


def test_debt_breaks_read_the_metrics_tables_long_term_debt_when_no_noncurrent_tag() -> None:
    reg = _registry({"short_term_borrowings": _every(15e9)})
    for year in YEARS[:3]:
        reg.add("F", "long_term_debt", "Long-term debt", year, 40e9, "usd", source="filed")
    assert derived.debt_breaks(reg, YEARS) == ["FY2022", "FY2023"]


def _break_detail(series: dict[str, dict[str, float]], profile: str = "operating") -> list[str]:
    reg = _registry(series)
    return [c["detail"] for c in derived.debt_checks(reg, YEARS, profile, derived.debt_breaks(reg, YEARS))]


def test_debt_break_checks_name_the_span() -> None:
    trailing = {"debt_noncurrent": _every(25e9, YEARS[:3]), "debt_current": _every(3e9)}
    assert _break_detail(trailing)[0].startswith(
        "Long-term debt not reported after FY2021; total debt and net cash after that omit it, so this pack leaves them out")
    assert _break_detail(trailing, "bank") == ["Long-term debt not reported after FY2021."]
    hole = {"debt_noncurrent": dict(zip(YEARS, (70e9, 76e9, 0.0, 86e9, 90e9))), "debt_current": _every(3e9)}
    assert _break_detail(hole)[0].startswith("Long-term debt reported as zero in FY2021; total debt and net cash in that year omit it")
    reg = _registry(hole)  # the evidence is the line on either side; the zero line itself is withheld
    assert derived.debt_checks(reg, YEARS, "operating", ["FY2021"])[0]["evidence"] == [
        reg.ref("debt_noncurrent", "FY2020"), reg.ref("debt_noncurrent", "FY2022")]
    leading = {"debt_noncurrent": _every(22e9, YEARS[1:]), "debt_current": {"FY2019": 1e9}}
    assert _break_detail(leading)[0].startswith("Long-term debt not reported before FY2020; total debt and net cash before that omit it")
    reg = _registry(trailing)
    check = derived.debt_checks(reg, YEARS, "operating", derived.debt_breaks(reg, YEARS))[0]
    assert check["kind"] == "debt_break" and check["severity"] == "high" and check["period"] == "FY2022,FY2023"
    assert check["evidence"] == [reg.ref("debt_noncurrent", "FY2021")]  # the last year the line was reported


def _with_total_debt(debt: list[float], interest: list[float]) -> derived.Registry:
    reg = _registry({"interest_expense": dict(zip(YEARS, interest))})
    for year, value in zip(YEARS, debt):
        reg.add("D", "total_debt", "Total debt", year, value, "usd")
    return reg


def test_implied_interest_rate_check_flags_interest_above_twelve_percent_of_average_debt() -> None:
    reg = _with_total_debt([10e9, 10e9, 10e9, 6e9, 6e9], [5e8, 5e8, 2.5e9, 4e8, 5e8])
    checks = derived.debt_checks(reg, YEARS, "operating", [])
    assert [c["kind"] for c in checks] == ["implied_interest_rate"]
    assert "25.0% in FY2021" in checks[0]["detail"] and checks[0]["period"] == "FY2021"  # 2.5bn over (10bn + 10bn) / 2
    assert reg.ref("interest_expense", "FY2021") in checks[0]["evidence"]
    # Inside a broken span the break check already says it; the rate test stays quiet there.
    assert derived.debt_checks(reg, YEARS, "operating", ["FY2021"])[0]["kind"] == "debt_break"
    assert all(c["kind"] != "implied_interest_rate" for c in derived.debt_checks(reg, YEARS, "operating", ["FY2021"]))
    assert derived.debt_checks(_with_total_debt([10e9] * 5, [5e8] * 5), YEARS, "operating", []) == []


def _debt_pack() -> tuple[derived.Registry, list[str], list[dict[str, Any]]]:
    """A CVX-like company through the real derivation: the long-term line stops after FY2021."""
    reg = _registry({"debt_noncurrent": _every(25e9, YEARS[:3]), "debt_current": _every(3e9),
                     "interest_expense": _every(7e8)})
    for year in YEARS:
        reg.add("F", "revenue", "Revenue", year, 200e9, "usd", source="filed")
        reg.add("F", "cash_and_equivalents", "Cash", year, 6e9, "usd", source="filed")
    derived.build_derived(reg, YEARS, "operating", [])
    own = reg.get("net_cash_to_revenue", "FY2023")
    reg.add("D", "peer_pctile:net_cash_to_revenue", "Net cash % of revenue: percentile vs energy peers (n=6)", "FY2023",
            83.3, "pctile", inputs=[own.id], source="peer")
    reg.add("D", "peer_median:net_cash_to_revenue", "Net cash % of revenue: energy peer median (n=6)", "FY2023",
            -7.7, "pct", source="peer")
    margin = reg.add("D", "net_margin_x", "Net margin", "FY2023", 10.0, "pct")
    reg.add("D", "peer_pctile:net_margin", "Net margin: percentile", "FY2023", 50.0, "pctile", inputs=[margin], source="peer")
    reg.add("D", "peer_median:net_margin", "Net margin: peer median", "FY2023", 10.0, "pct", source="peer")
    broken = derived.debt_breaks(reg, YEARS)
    flags = [{"id": "R1", "kind": "debt_build", "evidence": [reg.ref("total_debt", "FY2023"), reg.ref("total_debt", "FY2022")]},
             {"id": "R2", "kind": "revenue_decline", "evidence": [reg.ref("revenue", "FY2023")]}]
    return reg, broken, flags


def test_withheld_covers_every_value_and_flag_built_on_a_broken_year() -> None:
    reg, broken, flags = _debt_pack()
    assert broken == ["FY2022", "FY2023"]
    out = derived.withheld(reg, broken, flags)
    expected = {reg.ref(key, year) for key in ("total_debt", "net_cash", "net_cash_to_revenue") for year in broken}
    expected |= {reg.ref("g:total_debt", "FY2022"), reg.ref("g:total_debt", "FY2023")}  # across and after the break
    expected |= {reg.ref("peer_pctile:net_cash_to_revenue", "FY2023"), reg.ref("peer_median:net_cash_to_revenue", "FY2023")}
    assert set(out) == expected | {"R1"}
    assert set(out.values()) == {"debt_break"}
    for kept in (reg.ref("total_debt", "FY2021"), reg.ref("net_cash", "FY2021"), reg.ref("g:total_debt", "FY2021"),
                 reg.ref("liquidity", "FY2023"), reg.ref("peer_median:net_margin", "FY2023"), "R2"):
        assert kept is not None and kept not in out


def test_a_long_term_line_reported_as_zero_in_a_break_is_withheld() -> None:
    # ORCL's FY2022 long-term debt reads $0.0m [F185, X213] between $76.0bn and $86.4bn: stated, it reads as debt repaid.
    pack = _load("packs-v2", "ORCL")
    reg, years = _pack_registry(pack)
    assert (reg.values["F185"].value, reg.values["X213"].value) == (0.0, 0.0)
    out = derived.withheld(reg, ["FY2022"], [])
    assert out["F185"] == out["X213"] == "debt_break"
    check = next(c for c in pack["data_checks"] if c["kind"] == "debt_break")
    assert check["evidence"] == ["X212", "X214"] and {"F185", "X213"} <= set(pack["withheld"])
    # A positive long-term line of a broken year stays: DE's onset span lacks another line, not this one.
    reg, years = _pack_registry(_load("packs", "DE"))
    out = derived.withheld(reg, years[:4], [])
    assert not {reg.ref(key, year) for key in ("debt_noncurrent", "long_term_debt") for year in years[:4]} & set(out)


def test_net_cash_is_withheld_even_when_no_debt_line_is_left() -> None:
    # Net cash is cash alone when no debt line remains, so it has no total-debt input to follow.
    reg = _registry({"debt_noncurrent": _every(25e9, YEARS[:3]), "interest_expense": _every(7e8)})
    for year in YEARS:
        reg.add("F", "cash_and_equivalents", "Cash", year, 6e9, "usd", source="filed")
    derived.build_derived(reg, YEARS, "operating", [])
    assert reg.ref("total_debt", "FY2023") is None and reg.ref("net_cash", "FY2023") is not None
    assert reg.ref("net_cash", "FY2023") in derived.withheld(reg, derived.debt_breaks(reg, YEARS), [])


def test_appended_flags_number_after_version_1_and_leave_it_alone() -> None:
    flags = [{"id": f"R{n}", "kind": "x", "severity": "low", "persistence": 1, "detail": "", "evidence": []} for n in (1, 2, 3)]
    before = json.loads(json.dumps(flags))
    derived.append_flags(flags, [{"kind": "debt_break", "severity": "high", "detail": "Long-term debt ...", "evidence": ["X9"]}])
    assert flags[:3] == before
    assert flags[3] == {"kind": "data_quality", "severity": "high", "persistence": 1, "detail": "Long-term debt ...",
                        "evidence": ["X9"], "id": "R4"}


def test_a_check_names_the_net_cash_peer_rank_only_when_it_withholds_it() -> None:
    # ORCL: a FY2022 break leaves the FY2026 rank in place, so its check must not say the rank is left out.
    def detail(series: dict[str, dict[str, float]], ranked: bool) -> str:
        reg = _registry(series)
        if ranked:
            reg.add("D", "peer_pctile:net_cash_to_revenue", "Net cash % of revenue: percentile", "FY2023", 0.0, "pctile")
        return derived.debt_checks(reg, YEARS, "operating", derived.debt_breaks(reg, YEARS))[0]["detail"]

    hole = {"debt_noncurrent": dict(zip(YEARS, (70e9, 76e9, 0.0, 86e9, 90e9))), "debt_current": _every(3e9)}
    trailing = {"debt_noncurrent": _every(25e9, YEARS[:3]), "debt_current": _every(3e9)}
    assert "peer rank" not in detail(hole, ranked=True)
    assert detail(trailing, ranked=True).endswith("(net cash % of revenue, debt growth across the break, the net-cash peer rank).")
    assert detail(trailing, ranked=False).endswith("(net cash % of revenue, debt growth across the break).")


# Years the committed version-2 packs name as broken, by check kind: no other company, and no other year, is broken.
BREAKS = {
    "COP": {("debt_break", "FY2016"), ("debt_break", "FY2021,FY2022,FY2023,FY2024,FY2025"), ("liquidity_break", "FY2021")},
    "CVX": {("debt_break", "FY2022,FY2023,FY2024,FY2025")},
    "DE": {("debt_break", "FY2022,FY2023,FY2024,FY2025"), ("debt_break", "FY2016,FY2017,FY2018,FY2019")},
    "KO": {("debt_break", "FY2024,FY2025")},
    "MSFT": {("liquidity_break", "FY2017")},
    "NVDA": {("liquidity_break", "FY2026")},
    "ORCL": {("debt_break", "FY2022"), ("liquidity_break", "FY2017")},
    "TGT": {("liquidity_break", ",".join(TEN)), ("debt_break", "FY2016,FY2017,FY2018")},
    "USB": {("debt_break", "FY2023,FY2024,FY2025")},
}


def _pack_registry(pack: dict[str, Any]) -> tuple[derived.Registry, list[str]]:
    """A committed pack's values back in a registry, under their own IDs and series keys."""
    reg = derived.Registry()
    for series, vid in pack["series_keys"].items():
        key, period = series.split("|", 1)
        value = pack["values"][vid]
        reg.values[vid] = derived.Value(vid, value["label"], value["period"], value["value"], value["unit"],
                                        value.get("formula", ""), value.get("inputs", []), value.get("source", ""))
        reg.by_key[(key, period)] = vid
    return reg, [p["key"] for p in pack["periods"]]


def test_de_short_term_borrowings_onset_is_a_break() -> None:
    # DE's current portion of debt (its short-term borrowings) first appears in FY2020 at $8,582m: total debt +36.7%
    # [D205] while interest expense fell 15%. FY2016-FY2019 total debt is long-term only.
    reg, years = _pack_registry(_load("packs", "DE"))
    onsets = derived.debt_onsets(reg, years)
    assert onsets == [("debt_current", years[:4])]
    check = derived.debt_checks(reg, years, "operating", derived.debt_breaks(reg, years), onsets)[1]
    assert check["kind"] == "debt_break" and check["period"] == "FY2016,FY2017,FY2018,FY2019"
    assert check["detail"].startswith("Current portion of debt not reported before FY2020, when total debt jumps")
    assert "peer rank" not in check["detail"]
    out = derived.withheld(reg, years[:4], [])
    assert reg.ref("g:total_debt", "FY2020") == "D205" and out["D205"] == "debt_break"  # "Total debt growth 36.7%"
    assert {reg.ref(key, year) for key in ("total_debt", "net_cash", "net_cash_to_revenue") for year in years[:4]} <= set(out)
    for kept in ("FY2020", "FY2021"):
        assert reg.ref("total_debt", kept) not in out and reg.ref("net_cash", kept) not in out


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_no_other_debt_line_onset_in_the_twenty(ticker: str) -> None:
    # AMD's short-term borrowings appear at zero, NVDA's current portion too; SNAP's appear while total debt falls.
    reg, years = _pack_registry(_load("packs", ticker))
    assert derived.debt_onsets(reg, years) == ([("debt_current", years[:4])] if ticker == "DE" else [])


def _onset(interest: tuple[float, ...], line: float = 9e9) -> derived.Registry:
    reg = _registry({"debt_noncurrent": _every(30e9), "debt_current": {y: line for y in YEARS[2:]},
                     "interest_expense": dict(zip(YEARS, interest))})
    for year in YEARS:
        reg.add("D", "total_debt", "Total debt", year, 30e9 + (reg.val("debt_current", year) or 0), "usd")
    return reg


def test_onset_needs_a_jump_that_interest_does_not_follow() -> None:
    assert derived.debt_onsets(_onset((1.4e9, 1.5e9, 1.5e9, 1.4e9, 1.4e9)), YEARS) == [("debt_current", YEARS[:2])]
    assert derived.debt_onsets(_onset((1.4e9, 1.5e9, 1.6e9, 2.0e9, 2.0e9)), YEARS) == []  # interest followed: borrowing
    assert derived.debt_onsets(_onset((1.4e9, 1.5e9, 1.5e9, 1.4e9, 1.4e9), line=6e9), YEARS) == []  # +20%: no jump


def test_one_year_cash_gaps_in_the_twenty() -> None:
    # MSFT's short-term investments are missing in FY2017 ($121.8bn in FY2018): FY2017 net cash read -$72.5bn [D17].
    # AMD's are missing in FY2016 beside a reported zero, and VRTX's and RIVN's start late: none is a gap.
    found = {t: derived.liquidity_gaps(*_pack_registry(_load("packs", t))) for t in sorted(V1_RENDERS)}
    assert {t: gaps for t, gaps in found.items() if gaps} == {
        "COP": [("short_term_investments", "FY2021")], "MSFT": [("short_term_investments", "FY2017")],
        "NVDA": [("short_term_investments", "FY2026")], "ORCL": [("short_term_investments", "FY2017")]}
    reg, years = _pack_registry(_load("packs", "MSFT"))
    out = derived.withheld(reg, [], [], ["FY2017"])
    assert out["D17"] == "liquidity_break" and reg.values["D17"].value == pytest.approx(-72.51e9, rel=1e-3)
    assert {reg.ref("liquidity", "FY2017"), reg.ref("net_cash_to_revenue", "FY2017"), reg.ref("g:liquidity", "FY2018")} <= set(out)
    assert reg.ref("total_debt", "FY2017") not in out and reg.ref("net_cash", "FY2018") not in out


def test_short_term_investments_inside_cash_are_a_double_count() -> None:
    # TGT tags its cash, cash equivalents and short-term investments total at its cash figure ($5,488m in FY2025,
    # beside $4,611m of short-term investments), so its FY2025 net cash of -$4.3bn [D410] counts them twice.
    tgt = _registry({"cash_and_equivalents": {"FY2025": 5488e6}, "short_term_investments": {"FY2025": 4611e6}})
    tgt.add("D", "liquidity", "Cash and investments", "FY2025", 10099e6, "usd")
    assert derived.double_counted(tgt, ["FY2025"], {"FY2025": 5488e6}) == ["FY2025"]
    # MSFT tags it at cash plus short-term investments: no double count.
    msft = _registry({"cash_and_equivalents": {"FY2026": 20930e6}, "short_term_investments": {"FY2026": 55908e6}})
    msft.add("D", "liquidity", "Cash and investments", "FY2026", 113190e6, "usd")
    assert derived.double_counted(msft, ["FY2026"], {"FY2026": 76843e6}) == []
    assert derived.double_counted(tgt, ["FY2025"], {}) == []  # no filer total, no finding
    pack = _load("packs-v2", "TGT")
    assert {"D410", "D411"} <= set(pack["withheld"]) and pack["values"]["D410"]["value"] == pytest.approx(-4.299e9, rel=1e-3)


# --- A long-term line that already holds the current line: a debt double count ----------------------------------

# TGT's own noncurrent long-term debt and lease obligations (LongTermDebtAndCapitalLeaseObligations) and the noncurrent
# capital or finance leases the same 10-K reports, FY2016-FY2019, as evidence._debt_split reads them.
TGT_SPLIT = {"FY2016": (11031e6, 1025e6), "FY2017": (11317e6, 1152e6), "FY2018": (10223e6, 1021e6),
             "FY2019": (11338e6, 1303e6)}


def test_a_long_term_line_that_holds_the_current_line_is_a_double_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # TGT's LongTermDebt is its "Total notes and debentures" [X175 $11,715m at FY2016], and its total debt [D14] adds the
    # $1,718m due within one year [X171] again: $13,433m. Its noncurrent debt and leases less the leases is the line less
    # the current line ($10,006m against $9,997m); FY2017 and FY2018 the same.
    reg, years = _pack_registry(_load("packs", "TGT"))
    assert reg.val("total_debt", "FY2016") == reg.val("debt_noncurrent", "FY2016") + reg.val("debt_current", "FY2016")
    assert derived.debt_double_counted(reg, years, TGT_SPLIT) == ["FY2016", "FY2017", "FY2018"]
    # FY2019: the $137m swap adjustment, tagged nowhere, beside a $161m current line leaves $204m ($10,035m against
    # $9,831m), outside a quarter of it, so the margin, not a missing figure, keeps the year out of every check
    # (packs-v2/README.md, "Not detected").
    monkeypatch.setattr(derived, "DOUBLE_COUNT_MARGIN", 1.3)
    assert derived.debt_double_counted(reg, years, TGT_SPLIT) == ["FY2016", "FY2017", "FY2018", "FY2019"]
    monkeypatch.undo()
    # The leases come out of the filer's figure: with them, FY2016 misses by $1,034m.
    assert derived.debt_double_counted(reg, years, {"FY2016": (11031e6, 0.0)}) == []
    # Without the filer's figure, nothing is named: the tag alone does not tell (TSLA's LongTermDebt is its noncurrent line).
    assert derived.debt_double_counted(reg, years, {}) == []


def test_a_line_that_leaves_the_current_portion_out_is_no_double_count() -> None:
    # TSLA FY2018: LongTermDebt $8,410.5m beside $2,222.0m of current debt, and noncurrent debt and leases of $9,403.7m
    # less $993.2m of capital leases is the line itself: the figures differ by the current line, not within a quarter.
    tsla = _registry({"debt_noncurrent": {"FY2023": 8410.49e6}, "debt_current": {"FY2023": 2221.985e6}})
    assert derived.debt_double_counted(tsla, YEARS, {"FY2023": (9403.7e6, 993.2e6)}) == []
    assert derived.debt_double_counted(tsla, YEARS, {"FY2023": (8410.49e6 - 2221.985e6, 0.0)}) == ["FY2023"]
    # A current line of 1% of the long-term line or less is no finding (PH FY2025: $7m beside $7,501m).
    ph = _registry({"debt_noncurrent": {"FY2023": 7501e6}, "debt_current": {"FY2023": 7e6}})
    assert derived.debt_double_counted(ph, YEARS, {"FY2023": (7494e6, 0.0)}) == []
    # A noncurrent tag leaves the current portion out by definition: DUK's LongTermDebtNoncurrent [X171] is not read, even
    # where a figure equal to the line less the current line is given.
    reg, years = _pack_registry(_load("packs", "DUK"))
    line, current = reg.get("debt_noncurrent", "FY2016"), reg.get("debt_current", "FY2016")
    assert line.formula == "us-gaap:LongTermDebtNoncurrent"
    assert derived.debt_double_counted(reg, years, {"FY2016": (line.value - current.value, 0.0)}) == []


def test_a_debt_double_count_is_a_debt_break_check_after_the_liquidity_checks() -> None:
    reg, years = _pack_registry(_load("packs", "TGT"))
    double = derived.debt_double_counted(reg, years, TGT_SPLIT)
    checks = derived.debt_checks(reg, years, "operating", [], (), (), years, double)
    assert [c["kind"] for c in checks] == ["liquidity_break", "debt_break"]  # TGT's R7 keeps its number
    assert checks[1] == {
        "kind": "debt_break", "severity": "high", "period": "FY2016,FY2017,FY2018",
        "detail": ("The current portion of debt is already inside long-term debt in FY2016-FY2018 (the filer's noncurrent "
                   "long-term debt is the long-term line less the current portion); total debt and net cash there count it "
                   "twice, so this pack leaves them out, with the values built on them (net cash % of revenue, debt growth "
                   "across the break)."),
        "evidence": ["X177", "X173"]}  # FY2018's long-term and current lines, which stay shown
    assert probes.discloses(checks[1]["detail"])  # its own words disclose it
    assert derived.debt_checks(reg, years, "bank", [], debt_double=double) == []  # no total debt to count twice
    # The implied-rate test stays out of a double-counted year, as out of any debt break.
    rated = _with_total_debt([10e9] * 5, [5e8, 5e8, 2.5e9, 5e8, 5e8])
    assert [c["kind"] for c in derived.debt_checks(rated, YEARS, "operating", [], debt_double=["FY2021"])] == ["debt_break"]


def test_a_debt_double_count_withholds_total_debt_and_what_is_built_on_it() -> None:
    # TGT's total debt [D14, D33, D82] and its growth [D62 -20.3%, D109 +5.5%, D156 -10.1%: -10.9%, -1.8% and -2.5% on
    # the notes alone] go; the lines stay. Net cash there, inside the liquidity break too, is withheld as a debt break.
    reg, years = _pack_registry(_load("packs", "TGT"))
    out = derived.withheld(reg, ["FY2016", "FY2017", "FY2018"], [], years)
    assert {vid: out[vid] for vid in ("D14", "D33", "D82", "D62", "D109", "D156", "D15", "D34", "D83")} == dict.fromkeys(
        ("D14", "D33", "D82", "D62", "D109", "D156", "D15", "D34", "D83"), "debt_break")
    assert reg.values["D109"].value == pytest.approx(5.50, abs=0.01) and reg.values["D156"].value == pytest.approx(-10.14, abs=0.01)
    for kept in ("X175", "X171", "X177", "X173", "F185", "D129", "D203"):  # D129, D203: FY2019, which no test names
        assert kept not in out


def test_a_peers_double_counted_year_stays_out_of_its_rank() -> None:
    # BA FY2025: LongTermDebt $53,848m holds the $8,461m of current debt its total adds again; its noncurrent debt and
    # leases are $45,637m. Its net cash then reads $8.5bn too low in CAT's industrials median.
    ba = _peer({"debt_noncurrent": {"FY2025": 53848e6}, "debt_current": {"FY2025": 8461e6}}, {"FY2025": 23e9})
    assert derived.peer_left_out(ba, TEN, "FY2025", {}, {"FY2025": (45637e6, 0.0)}) == "debt line broken"
    assert derived.peer_left_out(ba, TEN, "FY2025", {}) is None


def test_cats_checked_rank_leaves_out_the_peers_that_count_debt_twice() -> None:
    # BA FY2025, PH FY2026 and UPS FY2025 entered CAT's industrials median with net cash short by their current debt
    # ($8,461m, $706m, $608m); three peers remain.
    checked = _load("packs-v2", "CAT")["peers"]["checked"]["net_cash_to_revenue"]
    assert checked["left_out"] == {"BA": "debt line broken", "DE": "debt line broken", "PH": "debt line broken",
                                   "UPS": "debt line broken"}
    assert checked["n"] == 3


def test_debt_split_reads_the_leases_of_the_same_10k(evidence: Any) -> None:
    def rows(*facts: tuple[str, float, str, str]) -> list[dict[str, Any]]:
        return [{"end": end, "val": val, "accn": accn, "filed": filed, "form": "10-K"} for end, val, accn, filed in facts]

    first, later = "0000027419-18-000010", "0000027419-19-000006"
    tags = {
        "LongTermDebtAndCapitalLeaseObligations": rows(("2018-02-03", 11317e6, first, "2018-03-14"),
                                                       ("2019-02-02", 10223e6, later, "2019-03-13")),
        "CapitalLeaseObligationsNoncurrent": rows(("2018-02-03", 1152e6, first, "2018-03-14")),
        # The later 10-K's figures for FY2017, on its own basis, are not read beside the FY2017 10-K's.
        "FinanceLeaseLiabilityNoncurrent": rows(("2018-02-03", 885e6, later, "2019-03-13")),
    }
    payload = {"facts": {"us-gaap": {tag: {"units": {"USD": facts}} for tag, facts in tags.items()}}}
    split = evidence._debt_split(payload, {"2018-02-03": "FY2017", "2019-02-02": "FY2018"})
    assert split == {"FY2017": (11317e6, 1152e6), "FY2018": (10223e6, 0.0)}
    del tags["CapitalLeaseObligationsNoncurrent"]  # FY2017 then has only a later 10-K's lease figure: none is read
    payload = {"facts": {"us-gaap": {tag: {"units": {"USD": facts}} for tag, facts in tags.items()}}}
    assert evidence._debt_split(payload, {"2018-02-03": "FY2017"}) == {"FY2017": (11317e6, 0.0)}


# --- Lines the pack maps nowhere: a data check, nothing withheld -------------------------------------------------

# The filer's own figures (companyfacts, first reported) by the packs' fiscal years: CAT's long-term debt maturing within
# one year (its balance sheet's "Long-term debt due within one year", $7,120m at FY2025), TGT's, and KO's and MSFT's cash,
# cash equivalents and short-term investments totals.
CAT_DUE = dict(zip(TEN, (6662e6, 6194e6, 5830e6, 6210e6, 9149e6, 6352e6, 5322e6, 8763e6, 6665e6, 7120e6)))
TGT_DUE = dict(zip(TEN, (1683e6, 201e6, 1002e6, 94e6, 1056e6, 63e6, 0.0, 1000e6, 1500e6, 2000e6)))
KO_TOTAL = dict(zip(TEN, (18150e6, 15358e6, 10951e6, 7947e6, 8566e6, 10926e6, 10562e6, 12363e6, 12848e6, 13872e6)))
MSFT_TOTAL = dict(zip([f"FY{y}" for y in range(2017, 2027)], (132981e6, 133768e6, 133819e6, 136527e6, 130334e6, 104757e6,
                                                               111262e6, 75543e6, 94565e6, 76843e6)))
CAT_DEBT_CHECK = ("Long-term debt due within one year is in no line of this pack in FY2016-FY2025: the filer reports from "
                  "$5.3 billion to $9.1 billion a year, $7.1 billion in FY2025, beside the noncurrent long-term debt this "
                  "pack sums, so total debt and net cash in those years omit it.")


def test_cats_current_portion_of_long_term_debt_is_an_unmapped_line() -> None:
    # CAT's total debt [D455] is $30,696m noncurrent long-term debt [X180] plus $5,514m short-term borrowings: the $7,120m
    # due within one year is in no line, so its FY2025 net debt reads $26.2bn [D456] against about $33bn.
    reg, years = _pack_registry(_load("packs", "CAT"))
    found = derived.unmapped_lines(reg, years, CAT_DUE, {})
    assert found == [("debt_current", year, CAT_DUE[year]) for year in years]
    checks = derived.unmapped_checks(reg, years, found)
    assert checks == [{"kind": "unmapped_line", "severity": "high", "period": ",".join(years), "detail": CAT_DEBT_CHECK,
                       "evidence": ["X180", "D455"]}]
    # Below the share of total debt, or beside a mapped current line, it is no finding.
    assert derived.unmapped_lines(reg, years, {y: 0.05 * reg.val("total_debt", y) for y in years}, {}) == []
    reg.add("X", "debt_current", "Current portion of debt", "FY2025", 7120e6, "usd", source="filed", fixed_id="X9999")
    assert [year for _, year, _ in derived.unmapped_lines(reg, years, CAT_DUE, {})] == years[:-1]


def test_a_long_term_debt_tag_that_may_hold_the_current_portion_is_not_tested() -> None:
    # TGT FY2024-FY2025: $1.5bn and $2.0bn due within a year beside a long-term line tagged LongTermDebt and no current
    # line. That tag holds the current portion, for TGT as for DUK: its FY2025 $14,398m is the debt note's "Total notes
    # and debentures", the $2,000m due in FY2026 inside it. Read as an omission, these years would be false findings.
    reg, years = _pack_registry(_load("packs", "TGT"))
    assert reg.get("debt_current", "FY2025") is None and reg.get("debt_noncurrent", "FY2025").formula == "us-gaap:LongTermDebt"
    assert reg.val("total_debt", "FY2025") * derived.UNMAPPED_LINE_SHARE < TGT_DUE["FY2025"]
    assert derived.unmapped_lines(reg, years, TGT_DUE, {}) == []


def test_a_year_a_break_check_names_is_not_tested_again() -> None:
    # DE's FY2016-FY2019 onset span already says total debt omits its current portion; the same years with a figure due
    # within one year are not named twice.
    reg, years = _pack_registry(_load("packs", "DE"))
    assert derived.unmapped_lines(reg, years, {y: 8e9 for y in years[:4]}, {}) == []


def test_kos_short_term_investments_are_an_unmapped_line() -> None:
    # KO's own total ($18,150m at FY2016) exceeds its $8,555m of cash and $4,051m of marketable securities: its $9,595m
    # of short-term investments are in no line of the pack. FY2018-FY2020 the marketable securities, which KO's total
    # leaves out, cover the gap, so those years are no finding. FY2024-FY2025 are debt-break years, which the cash test
    # still reads: a break of the other kind leaves cash and investments [D440] shown.
    reg, years = _pack_registry(_load("packs", "KO"))
    found = derived.unmapped_lines(reg, years, {}, KO_TOTAL)
    assert [(line, year) for line, year, _ in found] == [("short_term_investments", y) for y in
                                                         ("FY2016", "FY2017", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025")]
    assert found[0][2] == pytest.approx(18150e6 - 8555e6 - 4051e6)
    first, second = derived.unmapped_checks(reg, years, found)
    assert first["detail"] == (
        "Cash and short-term investments in this pack fall short of the filer's own cash, cash equivalents and short-term "
        "investments total before FY2018 ($5.5 billion in FY2016 and $3.9 billion in FY2017): a short-term investment line "
        "this pack does not map, so cash and investments and net cash before that omit it.")
    assert first["evidence"] == [reg.ref(k, "FY2017") for k in ("cash_and_equivalents", "short_term_investments", "liquidity")]
    assert second["period"] == "FY2021,FY2022,FY2023,FY2024,FY2025"
    assert "after FY2020 (from $1.0 billion to $3.6 billion a year, $3.6 billion in FY2025)" in second["detail"]


def test_a_total_the_pack_matches_or_a_named_gap_is_no_unmapped_line() -> None:
    # MSFT's total equals cash plus short-term investments from FY2018; FY2017's short-term investments are a liquidity
    # gap that its own check names.
    reg, years = _pack_registry(_load("packs", "MSFT"))
    assert reg.val("cash_and_equivalents", "FY2018") + reg.val("short_term_investments", "FY2018") == MSFT_TOTAL["FY2018"]
    assert derived.unmapped_lines(reg, years, {}, MSFT_TOTAL) == []


def test_the_net_debt_flag_quotes_no_level_an_unmapped_line_leaves_incomplete() -> None:
    reg, years = _pack_registry(_load("packs", "CAT"))
    plain = next(f for f in derived.red_flags(reg, years, "operating", [], []) if f["kind"] == "net_debt_build")
    assert plain["detail"] == "Net debt rose 2 years in a row to $26.2 billion in FY2025."
    found = derived.unmapped_lines(reg, years, CAT_DUE, {})
    flag = next(f for f in derived.red_flags(reg, years, "operating", [], [], found) if f["kind"] == "net_debt_build")
    assert flag == {**plain, "detail": "Net debt rose 2 years in a row through FY2025; its level is left out, as total debt "
                                       "and net cash omit long-term debt due within one year."}
    # A line left out only before the run leaves the level quoted.
    early = [hit for hit in found if hit[1] < "FY2023"]
    assert next(f for f in derived.red_flags(reg, years, "operating", [], [], early)
                if f["kind"] == "net_debt_build")["detail"] == plain["detail"]


# What the committed version-2 packs name as an unmapped line: nowhere else, and no other years.
UNMAPPED_HITS = {
    "CAT": {",".join(TEN)},
    "KO": {"FY2016,FY2017", "FY2021,FY2022,FY2023,FY2024,FY2025"},
}


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_2_packs_name_every_unmapped_line_and_withhold_nothing_for_it(ticker: str) -> None:
    pack = _load("packs-v2", ticker)
    checks = [c for c in pack["data_checks"] if c["kind"] == "unmapped_line"]
    assert {c["period"] for c in checks} == UNMAPPED_HITS.get(ticker, set())
    reg, _ = _pack_registry(pack)
    named = {kind: [p for c in pack["data_checks"] if c["kind"] == kind for p in c["period"].split(",")]
             for kind in ("debt_break", "liquidity_break")}
    assert derived.withheld(reg, named["debt_break"], pack["red_flags"], named["liquidity_break"],
                            (pack["peers"] or {}).get("replaced")) == pack["withheld"]  # the check adds nothing to it
    if ticker == "CAT":
        assert checks[0]["detail"] == CAT_DEBT_CHECK


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_no_red_flag_quotes_a_level_an_unmapped_line_leaves_incomplete(ticker: str) -> None:
    # CAT R1 read "Net debt rose 2 years in a row to $26.2 billion in FY2025" on net debt that omits $7.1bn.
    pack = _load("packs-v2", ticker)
    reg, _ = _pack_registry(pack)
    totals = {"Long-term debt due": ("total_debt", "net_cash"), "Cash and short-term": ("liquidity", "net_cash")}
    seeds = {vid for c in pack["data_checks"] if c["kind"] == "unmapped_line"
             for key in next(keys for lead, keys in totals.items() if c["detail"].startswith(lead))
             for year in c["period"].split(",") if (vid := reg.ref(key, year))}
    built = derived._built_on(reg, seeds)
    for flag in pack["red_flags"]:
        if flag["kind"] != "data_quality" and built & set(flag["evidence"]):
            assert not re.search(r"\$|\d%", flag["detail"]) and " omit " in flag["detail"], flag


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_2_packs_withhold_what_their_checks_name(ticker: str) -> None:
    # DE's FY2016-FY2019 onset span withholds its total debt and net cash, and "Total debt growth: FY2020 36.7%" [D205].
    pack = _load("packs-v2", ticker)
    reg, _ = _pack_registry(pack)
    named = {kind: [p for c in pack["data_checks"] if c["kind"] == kind for p in c["period"].split(",")]
             for kind in ("debt_break", "liquidity_break")}
    assert derived.withheld(reg, named["debt_break"], pack["red_flags"], named["liquidity_break"],
                            (pack["peers"] or {}).get("replaced")) == pack["withheld"]
    if ticker == "DE":
        assert pack["withheld"]["D205"] == "debt_break" and pack["values"]["D205"]["value"] == pytest.approx(36.68, abs=0.01)
    if ticker == "TGT":  # its FY2016-FY2018 double count: total debt and its growth, and net cash there
        ids = ("D14", "D33", "D82", "D62", "D109", "D156", "D15")
        assert {vid: pack["withheld"].get(vid) for vid in ids} == dict.fromkeys(ids, "debt_break")


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_2_packs_name_every_break_and_no_other(ticker: str) -> None:
    pack = _load("packs-v2", ticker)
    found = {(c["kind"], c["period"]) for c in pack["data_checks"] if c["kind"] in ("debt_break", "liquidity_break")}
    assert found == BREAKS.get(ticker, set())
    for check in pack["data_checks"]:
        if check["kind"] in ("debt_break", "liquidity_break"):  # the rank is named only where the pack withholds it
            rank = pack["series_keys"].get(f"peer_pctile:net_cash_to_revenue|{pack['periods'][-1]['key']}")
            assert ("the net-cash peer rank" in check["detail"]) == (
                pack["periods"][-1]["key"] in check["period"].split(",") and rank is not None and rank in pack["withheld"])


# --- Fix 8 for the peers: a peer's broken year stays out of the median and rank ------------------------------------

def _peer(series: dict[str, dict[str, float]], liquidity: dict[str, float]) -> derived.Registry:
    reg = _registry(series)
    for year, value in liquidity.items():
        reg.add("D", "liquidity", "Cash and investments", year, value, "usd")
    return reg


@pytest.mark.parametrize("name, series, liquidity, combined, reason", [
    # KO: the long-term line stops after FY2023 while short-term borrowings and interest go on; FY2025 net cash +18.3%.
    ("KO", {"debt_noncurrent": {y: 35.5e9 for y in TEN[:8]}, "short_term_borrowings": _every(1.5e9, TEN),
            "interest_expense": _every(1.6e9, TEN)}, {"FY2025": 10.3e9}, {}, "debt line broken"),
    # KMB: long-term debt only in FY2016; a five-year window would never see it. MDLZ, SO, MPC, PSX: no long-term line,
    # another debt line positive.
    ("KMB", {"debt_noncurrent": {"FY2016": 6.4e9}, "debt_current": _every(0.7e9, TEN), "interest_expense": _every(0.26e9, TEN)},
     {"FY2025": 0.69e9}, {}, "debt line broken"),
    ("SO", {"short_term_borrowings": _every(0.72e9, TEN)}, {"FY2025": 1.6e9}, {}, "no long-term debt line"),
    # GM: no debt line at all, but $2.7-4.4bn of interest a year to FY2020 implies about $37bn of debt.
    ("GM", {"interest_expense": dict(zip(TEN[:5], (2.68e9, 3.14e9, 3.88e9, 4.42e9, 4.12e9)))}, {"FY2025": 27.67e9}, {},
     "no long-term debt line"),
    # NVDA FY2026: short-term investments missing ($34.6bn in FY2025); TGT: inside cash.
    ("NVDA", {"debt_noncurrent": _every(8e9, TEN), "short_term_investments": {y: 34.6e9 for y in TEN[:9]}},
     {**{y: 43.2e9 for y in TEN[:9]}, "FY2025": 10.6e9}, {}, "cash line broken"),
    ("TGT", {"debt_noncurrent": _every(14.4e9, TEN), "cash_and_equivalents": _every(5.488e9, TEN),
             "short_term_investments": _every(4.611e9, TEN)}, {"FY2025": 10.1e9}, {"FY2025": 5.488e9}, "cash line broken"),
    # Never borrowed: VRTX's $72.5m of interest implies 5% of its cash; PINS reports none.
    ("VRTX", {"debt_noncurrent": {"FY2016": 0.0}, "interest_expense": dict(zip(TEN, (0, 69.3e6, 72.5e6, 58.5e6, 58.2e6, 0,
              54.8e6, 44.1e6, 30.6e6, 13.3e6)))}, {"FY2025": 12.32e9}, {}, None),
    ("PINS", {}, {"FY2025": 2.47e9}, {}, None),
    ("PEP", {"debt_noncurrent": _every(42.3e9, TEN), "debt_current": _every(6.9e9, TEN), "interest_expense": _every(1.1e9, TEN)},
     {"FY2025": 9.5e9}, {}, None),
])
def test_peer_left_out(name: str, series: dict[str, dict[str, float]], liquidity: dict[str, float],
                       combined: dict[str, float], reason: str | None) -> None:
    assert derived.peer_left_out(_peer(series, liquidity), TEN, "FY2025", combined) == reason


def _peer_note(note: str) -> dict[str, str]:
    """A peer rank's note, "CL -32.3; NKE -0.8; ...; left out: ...", as {peer: its value as printed}."""
    kept = note.split("; left out:")[0]
    return dict(item.rsplit(" ", 1) for item in kept.split("; ") if item)


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_2_peer_ranks_rest_on_no_broken_peer_year(ticker: str) -> None:
    # PG's version-1 staples median (-1.0%) took in KO's FY2025 +18.3% [KO D443], which KO's own pack withholds.
    pack = _load("packs-v2", ticker)
    for series, vid in pack["series_keys"].items():
        if vid in pack["withheld"] or series.split("|")[0] not in ("peer_median:net_cash_to_revenue",
                                                                 "peer_pctile:net_cash_to_revenue"):
            continue
        for peer, value in _peer_note(pack["values"][vid]["note"]).items():
            if peer not in V1_RENDERS:
                continue
            own = _load("packs-v2", peer)
            same = [i for k, i in own["series_keys"].items()
                    if k.startswith("net_cash_to_revenue|") and f"{own['values'][i]['value']:.1f}" == value]
            assert same and not set(same) & set(own["withheld"]), (vid, peer, value)


def _staples(left: tuple[str, ...]) -> tuple[derived.Registry, dict[str, dict[str, Any]], str, str, str]:
    """PG FY2026 (-27.8% net cash % of revenue) and its version-1 staples rank, with ``left`` left out."""
    reg = derived.Registry()
    own = reg.add("D", "net_cash_to_revenue", "Net cash % of revenue", "FY2026", -27.8, "pct")
    old_rank = reg.add("D", "peer_pctile:net_cash_to_revenue", "Net cash % of revenue: percentile vs staples peers (n=6)",
                       "FY2026", 33.3, "pctile", inputs=[own], source="peer")
    old_median = reg.add("D", "peer_median:net_cash_to_revenue", "Net cash % of revenue: staples peer median (n=6)",
                         "FY2026", -1.05, "pct", source="peer")
    values = {"CL": -32.3, "KMB": -0.0, "KO": 18.3, "MDLZ": -1.3, "NKE": -0.8, "PEP": -42.2}
    results = {t: {"period": "FY2025", "net_cash_to_revenue": v,
                   **({"left_out": {"net_cash_to_revenue": "debt line broken"}} if t in left else {})} for t, v in values.items()}
    return reg, results, own, old_rank, old_median


def test_checked_peer_ranks_replace_version_1s_without_the_broken_peers(evidence: Any) -> None:
    # PG FY2026: version 1's staples median of -1.0% (33rd percentile) took in KO, KMB and MDLZ; without them it is
    # -32.3% of three peers, and PG's -27.8% ranks 67th.
    reg, results, own, old_rank, old_median = _staples(("KO", "KMB", "MDLZ"))
    replaced, checked = evidence.checked_peer_ranks(reg, results, "staples", "FY2026", set())
    assert replaced == {old_rank: "peer_break", old_median: "peer_break"}
    rank, median = (reg.values[checked["net_cash_to_revenue"][k]] for k in ("percentile_id", "median_id"))
    assert (round(rank.value, 2), median.value) == (66.67, -32.3) and rank.inputs == [own]
    assert median.label == "Net cash % of revenue: staples peer median (n=3)" and rank.period == median.period == "FY2026"
    assert median.note == "CL -32.3; NKE -0.8; PEP -42.2; left out: KMB (debt line broken); KO (debt line broken); MDLZ (debt line broken)"
    # Filed beside version 1's, which keep their series keys; the backstops still read the new ones as net-cash references.
    assert reg.ref("peer_pctile:net_cash_to_revenue", "FY2026") == old_rank
    keys = probes.series_by_id({"series_keys": {f"{k}|{p}": vid for (k, p), vid in reg.by_key.items()}})
    assert keys[rank.id] == "peer_pctile:net_cash_to_revenue" and keys[median.id] == "peer_median:net_cash_to_revenue"
    assert derived.withheld(reg, [], [], [], replaced) == {old_rank: "peer_break", old_median: "peer_break"}
    # No peer left out: version 1's pair stands.
    reg, results, *_ = _staples(())
    assert evidence.checked_peer_ranks(reg, results, "staples", "FY2026", set()) == ({}, {})


@pytest.mark.parametrize("left, own_broken", [(("KO", "KMB", "MDLZ", "PEP"), False), (("KO",), True)])
def test_checked_peer_ranks_replace_nothing_below_three_peers_or_on_a_broken_own_year(
        evidence: Any, left: tuple[str, ...], own_broken: bool) -> None:
    # RIVN: F and GM left out leave two autos peers; KO: its own FY2025 net cash is withheld already.
    reg, results, own, old_rank, old_median = _staples(left)
    replaced, checked = evidence.checked_peer_ranks(reg, results, "staples", "FY2026", {own} if own_broken else set())
    assert replaced == {old_rank: "peer_break", old_median: "peer_break"} and checked == {}
    assert len(reg.values) == 3


def test_version_2_render_shows_the_checked_peer_median_not_version_1s() -> None:
    text = render.render(_load("packs-v2", "PG"))
    assert (f"- Net cash % of revenue: staples peer median (n=3) ({render.NET_CASH_LEGEND}): FY2026 -32.3% [D695]" in text)
    assert "[D676]" not in text and "[D677]" not in text and "(n=6) (below zero" not in text


# --- Fix 11: passage units --------------------------------------------------------------------------------------

COSTCO_FX = ("Changes in foreign currencies relative to the U.S. dollar increased SG&A expenses by $126, attributable to "
             "our Other International and Canadian operations.")
COSTCO_FEES = (
    "Effective September 1, 2024, we increased our membership fees in the U.S. and Canada for Gold Star (individual), "
    "Business, and Business affiliates to $65 per year. The Executive membership fee increased from $120 to $130 "
    "(membership fee of $65, plus Executive upgrade of $65), and the maximum annual 2% reward associated with the "
    "Executive Membership increased from $1,000 to $1,250. We expect these fee changes to increase revenues "
    "approximately $370 over the next two years, $190 of which will benefit fiscal 2025.")


def test_declared_scale() -> None:
    assert passages.declared_scale("(amounts in millions, except per share data) ... (In millions)") == "million"
    assert passages.declared_scale("(in thousands) ... (in thousands) ... in millions") == ""
    assert passages.declared_scale("no declaration here") == ""


def test_table_scale_dollars_carry_their_unit_and_prices_stay_as_filed() -> None:
    assert passages.with_units(COSTCO_FX, "million") == COSTCO_FX.replace("$126,", "$126 million,")
    fees = passages.with_units(COSTCO_FEES, "million")
    assert "approximately $370 million over" in fees and "years, $190 million of which" in fees
    for as_filed in ("to $65 per year", "from $120 to $130 (", "fee of $65,", "upgrade of $65)", "from $1,000 to $1,250."):
        assert as_filed in fees
    for text in ("capex will range from $18-19 billion.", "at an average price per share of $950.90 and $957.66, totaling $847.",
                 "Profit per share was $18.81 in 2025.", "a fully refundable deposit of $100, and we expect"):
        assert passages.with_units(text, "million") == text.replace("$847.", "$847 million.")
    assert passages.with_units("total assets were $ 31, and", "million") == "total assets were $ 31 million, and"
    # A figure linked to the one before it in its sentence (a range, a comparison) reads as that one does.
    oil = "The WTI price averaged $65 per barrel for the full-year 2025, compared to $76 in 2024."
    assert passages.with_units(oil, "million") == oil
    assert (passages.with_units("The fee rose to $65 per year. Sales rose from $100 to $500.", "million")
            == "The fee rose to $65 per year. Sales rose from $100 million to $500 million.")
    assert passages.with_units(COSTCO_FX, "") == COSTCO_FX


def test_candidates_record_the_sections_declared_scale() -> None:
    paragraph = ("Net sales increased $27,335 or 10% during 2026, primarily due to higher comparable sales and sales at new "
                 "warehouses, partially offset by lower gasoline prices compared to 2025.")
    filing = {"accession": "0000909832-26-000001", "form": "10-K", "filed": "2026-10-08", "document_url": "https://x/doc.htm"}
    found = passages.candidates(filing, {"mda": f"(amounts in millions)\n\n{paragraph}", "full": ""}, "FY2026", [])
    assert found and found[0]["table_scale"] == "million" and found[0]["text"] == paragraph  # the text stays as filed
    found = passages.candidates(filing, {"mda": paragraph, "full": ""}, "FY2026", [])
    assert found and "table_scale" not in found[0]
    # A section that declares no scale takes its document's (DE's Note 3; CAT's early MD&As).
    found = passages.candidates(filing, {"mda": paragraph, "full": "(in millions, except per share)"}, "FY2026", [])
    assert found and found[0]["table_scale"] == "million"
    assert "else the one its document declares" in " ".join((passages.__doc__ or "").split())


# --- Rendering ---------------------------------------------------------------------------------------------------

def _pack(version: str) -> dict[str, Any]:
    values = {
        # IDs that sort as strings out of year order: D10 (FY2019) before D9 (FY2018).
        "D9": {"label": "Revenue growth", "period": "FY2018", "value": 5.0, "unit": "pct"},
        "D10": {"label": "Revenue growth", "period": "FY2019", "value": 6.0, "unit": "pct"},
        "D100": {"label": "Revenue growth", "period": "FY2017", "value": 4.0, "unit": "pct"},
        "D11": {"label": "Net cash % of revenue", "period": "FY2019", "value": -38.8, "unit": "pct"},
        "D12": {"label": "Total debt", "period": "FY2019", "value": 1.5e9, "unit": "usd"},
        # A long-term line reported as zero inside a break (ORCL FY2022), beside a year that reports it.
        "F1": {"label": "Long-term debt", "period": "FY2018", "value": 5e9, "unit": "usd"},
        "F2": {"label": "Long-term debt", "period": "FY2019", "value": 0.0, "unit": "usd"},
    }
    keys = {"g:revenue|FY2018": "D9", "g:revenue|FY2019": "D10", "g:revenue|FY2017": "D100",
            "net_cash_to_revenue|FY2019": "D11", "total_debt|FY2019": "D12", "long_term_debt|FY2018": "F1",
            "long_term_debt|FY2019": "F2"}
    flags = [{"id": "R1", "kind": "revenue_decline", "severity": "medium", "persistence": 1, "detail": "Revenue declined.", "evidence": []},
             {"id": "R2", "kind": "debt_build", "severity": "medium", "persistence": 1, "detail": "Total debt rose 31%.", "evidence": ["D12"]},
             {"id": "R3", "kind": "data_quality", "severity": "high", "persistence": 1, "detail": "Long-term debt not reported.", "evidence": []}]
    return json.loads(json.dumps({  # through JSON with sorted keys, as the packs are committed
        "version": version, "company_name": "Example", "ticker": "EX", "window": "FY2017-FY2019", "sector": "x", "sic": "1",
        "industry": "x", "profile": "operating", "values": values, "series_keys": keys, "segments": [], "peers": {},
        "red_flags": flags, "data_checks": [], "inflection_years": [],
        "withheld": {"D12": "debt_break", "R2": "debt_break", "F2": "debt_break"},
        "passages": [{"id": "P1", "fiscal_year": "FY2019", "accession": "a", "section": "Item 7", "kind": "causal",
                      "text": COSTCO_FX, "table_scale": "million"}],
    }, sort_keys=True))


def test_version_2_render_orders_derived_cells_by_year_and_legends_net_cash() -> None:
    text = render.render(_pack("trend-depth-pack-v2"))
    assert "- Revenue growth: FY2017 4.0% [D100] · FY2018 5.0% [D9] · FY2019 6.0% [D10]" in text
    assert f"- Net cash % of revenue ({render.NET_CASH_LEGEND}): FY2019 -38.8% [D11]" in text
    assert render.NET_CASH_LEGEND == "below zero = net debt; a higher percentile = more net cash than peers"


def test_version_2_render_withholds_and_ranks_flags_and_gives_passages_their_unit() -> None:
    text = render.render(_pack("trend-depth-pack-v2"))
    assert "[D12]" not in text and "[R2]" not in text  # built on a broken debt year
    assert "- Long-term debt: FY2018 $5,000.0m [F1]\n" in text and "[F2]" not in text  # a filed line's withheld cell
    assert text.index("[R3] high") < text.index("[R1] medium")  # an appended high flag reads first
    assert "by $126 million, attributable" in text


def test_version_1_render_is_unchanged_by_version_2() -> None:
    text = render.render(_pack("trend-depth-pack-v1"))
    assert "- Revenue growth: FY2019 6.0% [D10] · FY2017 4.0% [D100] · FY2018 5.0% [D9]" in text  # as the frozen runs read it
    assert "[D12]" in text and "[R2]" in text and "by $126, attributable" in text and "legend" not in text
    assert "- Long-term debt: FY2018 $5,000.0m [F1] · FY2019 $0.0m [F2]" in text
    assert render.NET_CASH_LEGEND not in text and text.index("[R1]") < text.index("[R3]")


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_1_packs_render_as_the_frozen_runs_read_them(ticker: str) -> None:
    pack = _load("packs", ticker)
    assert pack["version"] == "trend-depth-pack-v1"
    assert hashlib.sha256(render.render(pack).encode()).hexdigest() == V1_RENDERS[ticker]


# The only version-1 entries version 2 changes on purpose: fix 4's rewording of the net-debt flag (same ID, kind,
# severity, persistence and evidence) where the company was in net debt throughout.
REWORDED_FLAGS = {("CAT", "R1"), ("DUK", "R3"), ("NEE", "R2"), ("ORCL", "R3")}


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_2_packs_keep_every_version_1_id_and_value(ticker: str) -> None:
    old, new = _load("packs", ticker), _load("packs-v2", ticker)
    assert new["version"] == "trend-depth-pack-v2"
    for vid, value in old["values"].items():
        assert new["values"].get(vid) == value, vid
    assert {k: new["series_keys"].get(k) for k in old["series_keys"]} == old["series_keys"]
    flags = {f["id"]: f for f in new["red_flags"]}
    for flag in old["red_flags"]:
        if (ticker, flag["id"]) in REWORDED_FLAGS:
            assert flags[flag["id"]] | {"detail": flag["detail"]} == flag
            assert flags[flag["id"]]["detail"].startswith("Net debt rose ")
        else:
            assert flags[flag["id"]] == flag, flag["id"]
    texts = {p["id"]: (p["accession"], p["text"]) for p in new["passages"]}
    assert all(texts.get(p["id"]) == (p["accession"], p["text"]) for p in old["passages"])
    assert new["data_checks"][:len(old["data_checks"])] == old["data_checks"]
    added = [int(vid[1:]) for vid in new["values"] if vid not in old["values"]]
    assert all(vid.startswith("D") for vid in new["values"] if vid not in old["values"])
    assert not added or min(added) > max(int(vid[1:]) for vid in old["values"] if vid.startswith("D"))


@pytest.mark.parametrize("ticker", sorted(V1_RENDERS))
def test_committed_version_2_packs_render_no_withheld_id(ticker: str) -> None:
    pack = _load("packs-v2", ticker)
    shown = set(re.findall(r"\[([DFRX]\d+)\]", render.render(pack)))
    assert not shown & set(pack["withheld"])
    assert set(pack["withheld"].values()) <= {"debt_break", "liquidity_break", "peer_break"}


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _years(years: list[str]) -> str:
    """"FY2016 and FY2022–FY2025": runs of consecutive years as ranges, listed as a sentence lists them."""
    runs: list[list[int]] = []
    for year in sorted(int(y[2:]) for y in years):
        if runs and runs[-1][-1] == year - 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return _and([f"FY{run[0]}" if len(run) == 1 else f"FY{run[0]}–FY{run[-1]}" for run in runs])


def test_readme_states_the_implied_rate_inside_each_long_term_debt_break() -> None:
    above: dict[str, list[str]] = {}
    under: dict[str, list[str]] = {}
    for ticker in sorted(V1_RENDERS):
        pack = _load("packs-v2", ticker)
        keys = [p["key"] for p in pack["periods"]]

        def val(key: str, period: str) -> float | None:
            vid = pack["series_keys"].get(f"{key}|{period}")
            return pack["values"][vid]["value"] if vid else None

        for check in pack["data_checks"]:
            if check["kind"] != "debt_break" or not check["detail"].startswith("Long-term debt") or pack["profile"] == "bank":
                continue
            for year in check["period"].split(","):
                i = keys.index(year)
                prior = val("total_debt", keys[i - 1]) if i else None
                base = [val("total_debt", year)] + ([prior] if prior and prior > 0 else [])
                rate = val("interest_expense", year) / (sum(base) / len(base)) * 100.0
                (above if rate > derived.IMPLIED_RATE_CEILING else under).setdefault(ticker, []).append(year)
    listing = {name: _and([f"{t} {_years(years)}" for t, years in sorted(found.items())]) for name, found in
               (("above", above), ("under", under))}
    readme = " ".join((RECORDS / "packs-v2" / "README.md").read_text().split())
    assert f"is above 12% in {listing['above']}, and under it in {listing['under']}." in readme


def test_readme_names_each_debt_double_count_the_packs_check() -> None:
    readme = " ".join((RECORDS / "packs-v2" / "README.md").read_text().split())
    found = []
    for ticker in sorted(V1_RENDERS):
        for check in _load("packs-v2", ticker)["data_checks"]:
            if check["kind"] == "debt_break" and check["detail"].startswith("The current portion of debt is already inside"):
                found.append(ticker)
                assert f"{ticker} {_years(check['period'].split(','))}" in readme, ticker
    assert found == ["TGT"]


def test_readme_names_each_unmapped_line_the_packs_check() -> None:
    readme = " ".join((RECORDS / "packs-v2" / "README.md").read_text().split())
    for ticker in sorted(V1_RENDERS):
        years = [p for c in _load("packs-v2", ticker)["data_checks"] if c["kind"] == "unmapped_line"
                 for p in c["period"].split(",")]
        assert not years or f"{ticker} {_years(years)}:" in readme, ticker


# --- The builder ---------------------------------------------------------------------------------------------------

@pytest.fixture
def evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stub = types.ModuleType("evals.trend_depth.bootstrap")
    stub.RECORDS = tmp_path
    monkeypatch.setitem(sys.modules, "evals.trend_depth.bootstrap", stub)
    for name in ("evidence", "sec_inputs"):
        monkeypatch.delitem(sys.modules, f"evals.trend_depth.{name}", raising=False)
    module = importlib.import_module("evals.trend_depth.evidence")
    yield module
    for name in ("evidence", "sec_inputs"):
        sys.modules.pop(f"evals.trend_depth.{name}", None)  # the next import sees the real bootstrap again


def test_builder_writes_version_2_and_will_not_overwrite_a_version_1_pack(evidence: Any, monkeypatch: pytest.MonkeyPatch,
                                                                         tmp_path: Path) -> None:
    import asyncio

    async def build(ticker: str, **kwargs: Any) -> dict[str, Any]:
        return {"version": evidence.PACK_VERSION, "values": {}, "segments": [], "passages": [], "red_flags": [],
                "data_checks": [], "withheld": {}, "fulltext_end": kwargs.get("fulltext_end")}

    monkeypatch.setattr(evidence, "build_pack", build)
    assert evidence.PACK_VERSION == "trend-depth-pack-v2" and evidence.PACKS == tmp_path / "packs"
    evidence.PACKS.mkdir()
    frozen = evidence.PACKS / "KO.json.gz"
    frozen.write_bytes(gzip.compress(json.dumps({"version": "trend-depth-pack-v1"}).encode()))
    with pytest.raises(SystemExit, match="trend-depth-pack-v1"):
        evidence.main(["KO"])  # the default output directory is packs/
    assert json.loads(gzip.decompress(frozen.read_bytes())) == {"version": "trend-depth-pack-v1"}
    out = tmp_path / "packs-v2"
    evidence.main(["--out", str(out), "--fulltext-end", "2026-10-24", "KO"])
    written = json.loads(gzip.decompress((out / "KO.json.gz").read_bytes()))
    assert written["version"] == "trend-depth-pack-v2" and written["fulltext_end"] == "2026-10-24"
    evidence.main(["--out", str(out), "KO"])  # rebuilding a version-2 pack in place is allowed
    asyncio.run(evidence._main(["KO"], replace=True))
    assert json.loads(gzip.decompress(frozen.read_bytes()))["version"] == "trend-depth-pack-v2"
