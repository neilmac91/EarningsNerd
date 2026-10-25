"""The auditor's view of a match (evals/trend_depth/semantics.py, DEEPSEEK-ERRORS.md fix 14) on the committed packs: no
twin may license a wrong number (review 6, lenses pack-v2 [1] and measures [1]).

Pins: an ID a version-2 pack withholds is never a twin, of a cited value or of an input, whatever its reason and in
either form of the pack's list (COP's current portion of debt and KO's short-term borrowings are not "total debt");
an input's twins, and those of a calculation's values, are shown only when all of them are of one period (AMD's total
debt growth is not long-term debt's; VRTX's buybacks plus dividends % of free cash flow keeps its buybacks twin); a red
flag's whole text; and instructions that read a twin as a name for that one value and a sign as part of the match.
Each view is built as ``semantics.audit`` builds it, from the gate's own match of the sentence.

The module is imported over a stub bootstrap, as in ``test_trend_depth_stages.py``, so the real bootstrap (which
rewrites the process's database and AI settings) never loads and no model is called.
"""
from __future__ import annotations

import gzip
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import factcheck

STAGES = ("generate", "judge", "causes", "semantics", "report")
RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"


@pytest.fixture
def semantics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stub = types.ModuleType("evals.trend_depth.bootstrap")
    stub.RECORDS = tmp_path
    stub.BACKEND = Path(__file__).resolve().parents[2]
    stub.PRODUCTION_MODEL = "stub"
    monkeypatch.setitem(sys.modules, "evals.trend_depth.bootstrap", stub)
    for name in (*STAGES, "gold"):
        monkeypatch.delitem(sys.modules, f"evals.trend_depth.{name}", raising=False)
    yield importlib.import_module("evals.trend_depth.semantics")
    for name in [n for n in sys.modules if n.split(".")[-1] in (*STAGES, "gold") and n.startswith("evals.trend_depth.")]:
        del sys.modules[name]  # the next test imports them afresh, over its own stub


def _load(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


def _views(semantics: Any, text: str, pack: dict[str, Any]) -> dict[str, str]:
    """Each verified claim of ``text`` and the auditor's view of its match, as ``semantics.audit`` builds them."""
    detail = factcheck.check([{"section": "balance_sheet", "text": text, "type": "fact"}], pack)["detail"][0]
    return {c["claim"]: semantics._describe(c.get("matched", ""), c["ids"], pack) + semantics._bound(c)
            for c in detail["claims"] if c["status"] == "verified" and c.get("ids")}


# --- Withheld IDs (lens pack-v2 [1]) ----------------------------------------------------------------------------------

@pytest.mark.parametrize(("ticker", "text", "claim", "withheld"), [
    ("COP", "Total debt was $1.0 billion in FY2025 [X203].", "$1.0 billion", "D336"),
    ("KO", "Total debt was $1.5 billion in FY2025 [X186].", "$1.5 billion", "D441"),
])
def test_a_withheld_total_debt_is_no_twin_of_the_debt_line_it_was_built_on(semantics: Any, ticker: str, text: str,
                                                                         claim: str, withheld: str) -> None:
    # The finding's cases: packs-v2 withholds COP's and KO's FY2025 total debt (one debt line, a debt break), so the
    # P and C arms never see it, and as a twin it told the auditor this sentence labels the number correctly.
    old, new = _load("packs", ticker), _load("packs-v2", ticker)
    assert new["withheld"][withheld] == "debt_break" and new["values"][withheld]["label"] == "Total debt"
    view = _views(semantics, text, new)[claim]
    assert view.startswith("cited: ") and "same value as" not in view and withheld not in view
    # On packs/, which shows K0 that total debt, it is still the same value under the pack's own label.
    assert f"same value as {withheld} = Total debt" in _views(semantics, text, old)[claim]


@pytest.mark.parametrize("reason", ["debt_break", "liquidity_break", "peer_break", "a list"])
def test_every_withheld_id_is_left_out_of_both_twin_lists_whatever_its_reason(semantics: Any, reason: str) -> None:
    pack = _load("packs-v2", "COP")
    others = {vid: why for vid, why in pack["withheld"].items() if vid != "D336"}
    pack["withheld"] = list({**others, "D336": reason}) if reason == "a list" else {**others, "D336": reason}
    revenue = pack["series_keys"]["revenue|FY2025"]
    # A one-period value built on the current portion of debt, so the input twin list is reached too.
    pack["values"]["D9999"] = {"id": "D9999", "label": "Current portion of debt % of revenue", "period": "FY2025",
                               "unit": "pct", "value": 1.0, "inputs": ["X203", revenue]}
    assert "D336" not in semantics._describe("cited", ["X203"], pack)
    assert "D336" not in semantics._describe("cited", ["D9999"], pack)
    pack["withheld"] = others  # what is not withheld is still a twin, on both lists
    assert semantics._describe("cited", ["X203"], pack).endswith("; same value as D336 = Total debt")
    assert "its input X203 = Current portion of debt has the same value as D336 = Total debt" in semantics._describe(
        "cited", ["D9999"], pack)


def test_no_view_of_a_version_2_pack_names_a_withheld_id_as_a_twin(semantics: Any) -> None:
    # The five packs where a withheld ID has a visible twin (debt and liquidity breaks), every value of each.
    for ticker in ("COP", "DE", "KO", "NVDA", "ORCL"):
        pack = _load("packs-v2", ticker)
        withheld = semantics._withheld(pack)
        for vid in pack["values"]:
            for twins in semantics._describe("cited", [vid], pack).split("same value as ")[1:]:
                named = {name.split(" = ")[0] for name in twins.split("; ")[0].split(", ") if " = " in name}
                assert not named & withheld, (ticker, vid, named & withheld)


# --- Twins across periods (lens measures [1]) -------------------------------------------------------------------------

def test_a_growth_shows_no_input_twin_as_a_twin_of_one_year_is_not_a_twin_of_the_change(semantics: Any) -> None:
    for folder in ("packs", "packs-v2"):
        pack = _load(folder, "AMD")
        # The finding: total debt growth (D170, -61.1%) is not long-term debt's (D157, -56.4%), though FY2019's total
        # debt equals FY2019's long-term debt; the input twin licensed this sentence's wrong number.
        view = _views(semantics, "Long-term debt fell 61.1% in FY2019 [D170].", pack)["61.1%"]
        assert view == "cited: D170 = Total debt growth, FY2019, -61.12%"
        assert semantics._describe("cited", ["D157"], pack) == "cited: D157 = Long-term debt growth, FY2019, -56.37%"


def test_a_one_period_value_keeps_its_input_twin(semantics: Any) -> None:
    # VRTX pays no dividend, so "buybacks plus dividends" is its share repurchases; the share of free cash flow is one
    # period's, so the input twin licenses "share repurchases were 63% of free cash flow" and nothing else.
    for folder in ("packs", "packs-v2"):
        view = _views(semantics, "Buybacks were 63.2% of free cash flow in FY2025 [D442].", _load(folder, "VRTX"))["63.2%"]
        assert view == ("cited: D442 = Buybacks plus dividends % of free cash flow, FY2025, 63.17%; its input D441 = "
                        "Buybacks plus dividends has the same value as X147 = Share repurchases (cash)")


@pytest.mark.parametrize(("ticker", "text", "claim", "view"), [
    # eval-v1 DeepSeek's sentences: a growth and a CAGR computed across years from two cited values.
    ("DE", "It has since fallen 15.6% in FY2024 and 11.7% in FY2025 [D367][D412], a 25.4% decline from the peak "
           "[F8][F10].", "25.4%",
     "growth F10/F8 = -25.42%: F10 = Revenue, FY2025, $45.68 billion | F8 = Revenue, FY2023, $61.25 billion"),
    ("JPM", "Revenue, net interest income plus noninterest income, rose from $96.6 billion in FY2016 to $182 billion "
            "in FY2025 [D5][D206], a 7.3% CAGR.", "7.3%",
     "CAGR D5->D206 over 9y = 7.32%: D206 = Net interest income plus noninterest income, FY2025, $182.45 billion | "
     "D5 = Net interest income plus noninterest income, FY2016, $96.57 billion"),
])
def test_a_calculation_across_years_shows_no_twin_of_its_values(semantics: Any, ticker: str, text: str, claim: str,
                                                               view: str) -> None:
    # JPM's FY2025 revenue equals "Total revenues as reported" but its FY2016 revenue has no such twin: the twin would
    # have licensed a CAGR of total revenues as reported that the pack never computed.
    assert _views(semantics, text, _load("packs", ticker))[claim] == view


def test_a_window_level_shows_no_input_twin_as_its_one_input_is_of_another_period(semantics: Any) -> None:
    # VRTX's net margin window high (D665, FY2016..FY2025) is FY2018's net margin (F48). A twin of FY2018's margin is
    # not a twin of the window high: another metric's high may fall in another year. None has one in the committed
    # packs, so one is planted.
    pack = _load("packs", "VRTX")
    pack["values"]["X9999"] = {**pack["values"]["F48"], "id": "X9999", "label": "Pre-tax margin"}
    assert semantics._describe("cited", ["F48"], pack).endswith("same value as X9999 = Pre-tax margin")
    assert semantics._describe("cited", ["D665"], pack) == (
        "cited: D665 = Net margin window high (FY2018), FY2016..FY2025, 68.80%")


def test_a_calculation_within_one_year_keeps_its_values_twins(semantics: Any) -> None:
    text = "Buybacks plus dividends were 63.2% of free cash flow in FY2025 [D441][F105]."
    view = _views(semantics, text, _load("packs", "VRTX"))["63.2%"]
    assert view.startswith("share D441/F105 = 63.17%: D441 = Buybacks plus dividends, FY2025, $2.02 billion; "
                           "same value as X147 = Share repurchases (cash) | F105 = Free cash flow")


def test_an_input_twin_is_shown_only_when_every_input_is_of_the_value_s_period(semantics: Any) -> None:
    for folder, ticker in (("packs", "AMD"), ("packs-v2", "DE")):
        pack = _load(folder, ticker)
        shown = 0
        for vid, value in pack["values"].items():
            if "its input" in semantics._describe("cited", [vid], pack):
                shown += 1
                inputs = value["inputs"]
                assert all(pack["values"][i]["period"] == value["period"] for i in inputs), (ticker, vid)
        assert shown > 100  # the one-period ones keep theirs: common-size shares, margins, ratios


# --- The rest of the view ---------------------------------------------------------------------------------------------

def test_a_red_flag_is_shown_whole_so_its_figure_is_in_view(semantics: Any) -> None:
    # eval-v1 DeepSeek's CAT sentence: the 0.06% stands 195 characters into R3, past the 120 the view used to show.
    text = ("Net income for FY2021 to FY2025 in the table is proxy-sourced and differs from the 10-K by up to 0.06%, so "
            "the 10-K figures should be used where precision matters [R3][X16][X20].")
    view = _views(semantics, text, _load("packs", "CAT"))["0.06%"]
    assert view.startswith("passage R3: R3 = red-flag text: Net income for FY2021") and "differ by up to 0.06%" in view


def test_the_instructions_read_a_twin_as_a_name_for_one_value_and_a_sign_as_part_of_the_match(semantics: Any) -> None:
    system = " ".join(semantics.SYSTEM.split())
    # The view-2 draft let any twin license the number, an input's included: "long-term debt fell 61.1%".
    assert "the number is consistent if the sentence names any of them" not in system
    assert "other names for that value, and for nothing else" in system
    assert "a name may replace that input or value inside the same calculation only" in system
    assert ("The number stated as anything else about that name (its level, its growth, a ratio or share the match "
            "does not compute) is a mismatch.") in system
    # The gate checks no level's sign, so the auditor is the only check of "net income of $2.1 billion" for a loss.
    assert "a different metric, period, segment, sign or basis" in system
    assert "The opposite sign is a mismatch: a negative value stated as a positive amount" in system
    assert '"net debt" for a net cash above zero' in system


def test_the_withheld_list_is_read_in_either_form(semantics: Any) -> None:
    assert semantics._withheld({"withheld": {"D1": "debt_break", "D2": "peer_break"}}) == {"D1", "D2"}
    assert semantics._withheld({"withheld": ["D1", "D2"]}) == {"D1", "D2"}
    assert semantics._withheld({}) == set()


def test_these_tests_leave_the_real_bootstrap_unloaded() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
