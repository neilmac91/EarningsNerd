"""Evidence pack version 2 (evals/trend_depth/{derived,passages,render,evidence}.py; DEEPSEEK-ERRORS.md §2 fixes 3, 4,
8, 9 and 11).

Pins: the added values (an operating cash flow / net income median and low, a same-year net-minus-operating margin)
and the debt-break checks register after every version-1 ID; the net-debt red flag says "net debt rose" when the
company was in net debt throughout; a long-term debt line that stops, or reads zero, while debt is still evident
is a break, and everything built on a broken year is withheld from the render; passages in millions carry their
unit; a version-2 render puts derived cells in year order and a legend on net-cash rows; a version-1 pack renders
byte for byte as the frozen runs read it; and the committed version-2 packs keep every version-1 ID and value.
The builder is imported over a stub bootstrap, so no database, settings or SEC call is touched.
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

from evals.trend_depth import derived, passages, render

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
YEARS = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023"]


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


# --- Rendering ---------------------------------------------------------------------------------------------------

def _pack(version: str) -> dict[str, Any]:
    values = {
        # IDs that sort as strings out of year order: D10 (FY2019) before D9 (FY2018).
        "D9": {"label": "Revenue growth", "period": "FY2018", "value": 5.0, "unit": "pct"},
        "D10": {"label": "Revenue growth", "period": "FY2019", "value": 6.0, "unit": "pct"},
        "D100": {"label": "Revenue growth", "period": "FY2017", "value": 4.0, "unit": "pct"},
        "D11": {"label": "Net cash % of revenue", "period": "FY2019", "value": -38.8, "unit": "pct"},
        "D12": {"label": "Total debt", "period": "FY2019", "value": 1.5e9, "unit": "usd"},
    }
    keys = {"g:revenue|FY2018": "D9", "g:revenue|FY2019": "D10", "g:revenue|FY2017": "D100",
            "net_cash_to_revenue|FY2019": "D11", "total_debt|FY2019": "D12"}
    flags = [{"id": "R1", "kind": "revenue_decline", "severity": "medium", "persistence": 1, "detail": "Revenue declined.", "evidence": []},
             {"id": "R2", "kind": "debt_build", "severity": "medium", "persistence": 1, "detail": "Total debt rose 31%.", "evidence": ["D12"]},
             {"id": "R3", "kind": "data_quality", "severity": "high", "persistence": 1, "detail": "Long-term debt not reported.", "evidence": []}]
    return json.loads(json.dumps({  # through JSON with sorted keys, as the packs are committed
        "version": version, "company_name": "Example", "ticker": "EX", "window": "FY2017-FY2019", "sector": "x", "sic": "1",
        "industry": "x", "profile": "operating", "values": values, "series_keys": keys, "segments": [], "peers": {},
        "red_flags": flags, "data_checks": [], "inflection_years": [], "withheld": {"D12": "debt_break", "R2": "debt_break"},
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
    assert text.index("[R3] high") < text.index("[R1] medium")  # an appended high flag reads first
    assert "by $126 million, attributable" in text


def test_version_1_render_is_unchanged_by_version_2() -> None:
    text = render.render(_pack("trend-depth-pack-v1"))
    assert "- Revenue growth: FY2019 6.0% [D10] · FY2017 4.0% [D100] · FY2018 5.0% [D9]" in text  # as the frozen runs read it
    assert "[D12]" in text and "[R2]" in text and "by $126, attributable" in text and "legend" not in text
    assert render.NET_CASH_LEGEND not in text and text.index("[R1]") < text.index("[R3]")


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
    shown = set(re.findall(r"\[([DR]\d+)\]", render.render(pack)))
    assert not shown & set(pack["withheld"])


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
