"""The auditor's view of a match (evals/trend_depth/semantics.py, DEEPSEEK-ERRORS.md fix 14) on the committed packs: no
twin may license a wrong number (review 6, lenses pack-v2 [1] and measures [1]).

Pins: an ID a version-2 pack withholds is never a twin, of a cited value or of an input, whatever its reason and in
either form of the pack's list (COP's current portion of debt and KO's short-term borrowings are not "total debt");
an input's twins, and those of a calculation's values, are shown only when all of them are of one period (AMD's total
debt growth is not long-term debt's; VRTX's buybacks plus dividends % of free cash flow keeps its buybacks twin); a red
flag's whole text; a passage figure's own sentences, as the gate read them, with the 10-K's year and section (review
7): each figure its own sentence, a table-scale reading named, a long sentence cut around its figure and the cap
stated, no sentence ended at an abbreviation, every sentence printing it up to the limit, and ``audit`` handing each
claim its own parsed figure; and instructions that read a twin as a name for that one value and a sign as part of the
match. Each view is built as ``semantics.audit`` builds it, from the gate's own match of the sentence.

Flag classes (``classify_flag``; reviews 8 and 9, measures [0], arm-fairness [3]): a figure cited beside what the
pack computes it from is one quantity, so a flag on it counts as it does when the figure is cited alone, for K0's
sentences on packs/ and C's on packs-v2 alike (a growth gap with both growths, a CAGR with its levels, a margin with
its numerator and denominator, a window low, high or median with its point, packs-v2's operating cash flow / net
income window figures, a sum's inverse); different metrics that print one number stay two; and every committed
derivation the rule reads is the gate's own calculation.

The module is imported over a stub bootstrap, as in ``test_trend_depth_stages.py``, so the real bootstrap (which
rewrites the process's database and AI settings) never loads and no model is called.
"""
from __future__ import annotations

import asyncio
import gzip
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import factcheck
from evals.trend_depth.providers import CallResult

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
    """Each verified claim of ``text`` and the auditor's view of its match, as ``semantics.audit`` builds them: each
    claim with its own parsed figure."""
    detail = factcheck.check([{"section": "balance_sheet", "text": text, "type": "fact"}], pack)["detail"][0]
    return {c["claim"]: semantics._describe(c.get("matched", ""), c["ids"], pack, figure) + semantics._bound(c)
            for c, figure in zip(detail["claims"], factcheck.parse_claims(detail["text"]), strict=True)
            if c["status"] == "verified" and c.get("ids")}


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


# --- Passage figures (review 7, decision b) ---------------------------------------------------------------------------

CAT_P9 = ("Operating profit fell $1.921 billion on unfavorable manufacturing costs of $2.148 billion and unfavorable price "
          "realization of $817 million, with manufacturing costs largely reflecting higher tariffs [P9].")
CAT_WHERE = "passage P9: P9 = a figure in the FY2025 10-K, Item 7. Management's Discussion and Analysis: "


def _quote(view: str) -> str:
    return view.split(': "', 1)[1].rsplit('"', 1)[0]


def test_a_passage_figure_is_shown_with_the_passage_sentence_that_prints_it(semantics: Any) -> None:
    # eval-v1 DeepSeek's CAT sentence: P9 prints each figure in a sentence of its own, so each claim shows its own.
    # View 1 showed all three as "P9 = a figure in a FY2025 10-K passage", which left the auditor nothing to judge.
    views = _views(semantics, CAT_P9, _load("packs", "CAT"))
    assert views["$1.921 billion"] == CAT_WHERE + ('"Operating profit was $11.151 billion in 2025, a decrease of $1.921 '
                                                   'billion, or 15 percent, compared with $13.072 billion in 2024."')
    assert views["$2.148 billion"] == views["$817 million"] == CAT_WHERE + (
        '"The decrease was primarily due to unfavorable manufacturing costs of $2.148 billion and unfavorable price '
        'realization of $817 million, partially offset by the profit impact of higher sales volume of $1.218 billion."')


def test_a_figure_read_at_the_table_s_scale_says_so(semantics: Any) -> None:
    # eval-v1 DeepSeek's COST sentence: the gate read P14's "$27,335" in millions, as the filing's tables print it.
    text = ("FY2026 net sales rose $27.3 billion, of which comparable sales added $22.5 billion on a 5% higher average "
            "ticket and 3% more shopping frequency [P14].")
    assert _views(semantics, text, _load("packs", "COST"))["$27.3 billion"] == (
        "passage P14 (x1e+06): P14 = a figure in the FY2026 10-K, Item 7. Management's Discussion and Analysis; printed "
        'without its scale and read in millions: "Net sales increased $27,335 or 10% during 2026."')


def test_a_long_sentence_is_cut_around_its_figure_and_says_so(semantics: Any) -> None:
    # eval-v1 DeepSeek's ORCL sentence: P9's sentence runs past the cap and prints the $1.5 billion near its end.
    text = ("Net margin rose 3.5pp to 25.2% as the effective tax rate fell to 28.4% from 39.2%, helped by $1.5 billion more "
            "stock-based compensation tax benefit [D434][F54][D407][D360][P9].")
    view = _views(semantics, text, _load("packs", "ORCL"))["$1.5 billion"]
    assert view.endswith(f"(cut to {semantics.QUOTE_CAP} characters around the figure)")
    quote = _quote(view)
    assert quote.startswith("…") and len(quote) <= semantics.QUOTE_CAP + 1
    assert "an increase in tax benefits related to stock-based compensation of $1.5 billion" in quote


def test_a_sentence_ends_at_its_stop_not_at_an_abbreviation(semantics: Any) -> None:
    # eval-v1 DeepSeek's RIVN sentence: P10's "Also, Inc. (refer to Note 16" does not end the sentence of the $186 million.
    text = ("Net margin of -67.7% tracked operating margin, with other expense of $54 million including a $186 million "
            "litigation settlement [F43][X84][P10].")
    quote = _quote(_views(semantics, text, _load("packs", "RIVN"))["$186 million"])
    assert quote.startswith("Other expense, net increased for the year ended December 31, 2025 primarily due to $186 million")
    assert "equity method investment in Also, Inc. (refer to Note 16" in quote


def test_every_sentence_printing_the_figure_is_shown_up_to_the_limit(semantics: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # eval-v1 DeepSeek's TGT sentence: P11 prints 20.6% twice, once for 2025's rate and once for 2024's adjusted one;
    # the gate accepts either, so the auditor sees both.
    text = ("The SG&A rate held at 20.6% only because a 0.6pp interchange settlement benefit offset deleveraging from lower "
            "sales [P11].")
    first = '"Our SG&A expense rate was 20.6\xa0percent in 2025, consistent with 2024."'  # the filing's no-break space
    view = _views(semantics, text, _load("packs", "TGT"))["20.6%"]
    assert first in view and '" / "Excluding these items, our Adjusted SG&A expense rate was 20.9 percent' in view
    monkeypatch.setattr(semantics, "QUOTE_SENTENCES", 1)
    assert _views(semantics, text, _load("packs", "TGT"))["20.6%"].endswith(f"{first} (and 1 more sentence printing it)")


def test_an_audit_hands_each_claim_its_own_figure(semantics: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``semantics.audit`` builds the view from the gate's claim and its parsed figure, so the auditor reads the
    sentence of P9 each number is printed in."""
    sent: list[str] = []

    async def auditor(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append(user)
        return CallResult('{"items": [{"n": 1, "label": "consistent", "reason": "r"}]}', 1000, 0, 100, 0, 1.0, 0.25,
                          "claude_cli", "m", {"stop_reason": "end_turn"})

    monkeypatch.setattr(sys.modules["evals.trend_depth.causes"], "call", auditor)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "CAT.json.gz").write_bytes((RECORDS / "packs" / "CAT.json.gz").read_bytes())
    record = {"ticker": "CAT", "arm": "deepseek-flash", "generation_ok": True,
              "output": {"sections": [{"key": "margins", "title": "Margins", "sentences": [{"type": "fact", "text": CAT_P9}]}]}}
    path = tmp_path / "runs" / "test" / "deepseek-flash" / "CAT.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record))
    asyncio.run(semantics.run("test", ["deepseek-flash"], ["CAT"], 1))
    assert len(sent) == 1 and sent[0].count(CAT_WHERE) == 3
    assert sent[0].count('"Operating profit was $11.151 billion in 2025') == 1  # the $1.921 billion's alone
    assert sent[0].count('"The decrease was primarily due to unfavorable manufacturing costs of $2.148 billion') == 2


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


# --- Flag classes (review 8 measures [0]) ------------------------------------------------------------------------------

def _flag_class(semantics: Any, text: str, claim: str, pack: dict[str, Any]) -> str:
    item = {"sentence": factcheck.CITATION_RE.sub("", text).strip(), "claim": claim, "label": "mismatch"}
    return semantics.classify_flag(item, [{"section": "margins", "type": "comparison", "text": text}], pack, 2)


def _cited(text: str) -> list[str]:
    return [i for g in factcheck.CITATION_RE.findall(text) for i in factcheck.ID_RE.findall(g)]


@pytest.mark.parametrize("wording", ["sat 4.3pp above the 22.7% operating margin", "exceeded the 22.7% operating margin by 4.3pp"])
def test_a_cited_gap_and_its_two_margins_are_one_quantity(semantics: Any, wording: str) -> None:
    # PG FY2026 on packs-v2: D693 is net margin F50 (18.44%) less operating margin F30 (22.69%), -4.25pp, which the gate
    # also builds from the two margins ("pp F50-F30"). C's prompt asks for all three IDs, K0's packs/ offers the two.
    new, old = _load("packs-v2", "PG"), _load("packs", "PG")
    assert new["values"]["D693"]["inputs"] == ["F50", "F30"]
    text = f"In FY2026 net margin of 18.4% {wording}"
    assert [_flag_class(semantics, f"{text} {ids}.", "4.3pp", pack)
            for ids, pack in (("[F50][F30][D693]", new), ("[F50][F30]", new), ("[F50][F30]", old))] == ["substantive"] * 3


@pytest.mark.parametrize("gap, inputs, expected", [
    (5.0, ["F1", "F2"], "substantive"),  # the difference of its two inputs: one quantity
    (5.04, ["F1", "F2"], "ambiguous"),   # the same inputs, another value: two quantities that both print as 5.0pp
    (5.0, ["F1", "F3"], "ambiguous"),    # the same value, other inputs: not the calculation the gate built
])
def test_only_a_derived_value_equal_to_the_calculation_of_its_inputs_merges(semantics: Any, gap: float, inputs: list[str],
                                                                          expected: str) -> None:
    values = {"F1": ("Net margin", "pct", 10.0), "F2": ("Operating margin", "pct", 5.0), "F3": ("Gross margin", "pct", 5.0),
              "D1": ("Net margin minus operating margin (pp, same year)", "pp", gap)}
    pack = {"values": {vid: {"id": vid, "label": label, "period": "FY2025", "unit": unit, "value": value}
                       for vid, (label, unit, value) in values.items()}, "passages": [], "red_flags": []}
    pack["values"]["D1"]["inputs"] = inputs
    assert _flag_class(semantics, "Net margin of 10.0% was 5.0pp above the 5.0% operating margin [F1][F2][D1].", "5.0pp",
                       pack) == expected


# --- One quantity by the pack's own derivation (review 9 measures [0], arm-fairness [3]) ------------------------------
# A flag counts (substantive) or not (ambiguous) by the quantities that match its figure. A figure cited beside what
# the pack computes it from is one quantity, so its flag counts as the same figure's does when cited alone: the class
# must not depend on how many IDs the sentence carries, as the frozen prompt's sentences carry the gap with both
# growths and the candidate prompt's carry the year value with packs-v2's window low. Each row: the sentence citing
# both, the same sentence citing less, and the figure. True sentences and their false mirrors alike: a flag counts the
# same either way, and only a false one should draw it.
ONE_QUANTITY = [
    # CVX FY2025 (held out): the growth gap D379 (-1.22pp) is revenue growth D358 (-4.64%) less operating-expense growth
    # D373 (-3.42%), though its inputs list revenue and operating income. eval-v1 DeepSeek's (K0's) own sentence, true,
    # and its false mirrors, which the gate passes by magnitude, so that the Opus audit alone can catch them (§4).
    pytest.param("CVX", "Operating costs fell 3.4% while revenue fell 4.6%, so the revenue decline outran cost reduction by "
                 "1.2pp [D373][D358][D379].",
                 "Operating costs fell 3.4% while revenue fell 4.6%, so the revenue decline outran cost reduction by "
                 "1.2pp [D379].", "1.2pp", id="CVX gap, K0's recorded sentence"),
    pytest.param("CVX", "Operating costs fell 3.4% while revenue fell 4.6%, so cost reduction outran the revenue decline by "
                 "1.2pp [D373][D358][D379].",
                 "Operating costs fell 3.4% while revenue fell 4.6%, so cost reduction outran the revenue decline by "
                 "1.2pp [D379].", "1.2pp", id="CVX gap, its false mirror"),
    pytest.param("CVX", "Revenue fell 4.6% in FY2025, 1.2pp less than operating costs [D358][D373][D379].",
                 "Revenue fell 4.6% in FY2025, 1.2pp less than operating costs [D358][D379].", "1.2pp",
                 id="CVX gap, the appositive mirror"),
    # DE FY2024: its gap's inputs (revenue, operating income) are complete, yet not what it is computed from.
    pytest.param("DE", "In FY2024 revenue fell 15.6% while operating costs fell only 11.9% [D367][D382], a 3.7pp gap [D389].",
                 "In FY2024 revenue fell 15.6% while operating costs fell only 11.9%, a 3.7pp gap [D389].", "3.7pp",
                 id="DE gap, K0's recorded sentence"),
    # AMD: the revenue CAGR F231, a metrics-table value with no inputs, is FY2016's and FY2025's revenue [F1][F10].
    pytest.param("AMD", "Revenue compounded at 26.0% a year from $4,319 million in FY2016 to $34,639 million in FY2025 "
                 "[F1][F10][F231].", "Revenue compounded at 26.0% a year [F231].", "26.0%", id="AMD CAGR, true"),
    pytest.param("AMD", "Operating cash flow compounded at 26.0% a year from $4,319 million in FY2016 to $34,639 million in "
                 "FY2025 [F1][F10][F231].", "Operating cash flow compounded at 26.0% a year [F231].", "26.0%",
                 id="AMD CAGR, relabelled"),
    # PG FY2026: operating margin F30 is "100 * operating_income / revenue", F20 over F10.
    pytest.param("PG", "Operating margin was 22.7% in FY2026 on operating income of $19.7 billion and revenue of $87.0 "
                 "billion [F30][F20][F10].", "Operating margin was 22.7% in FY2026 [F30].", "22.7%", id="PG margin, true"),
    pytest.param("PG", "Net margin was 22.7% in FY2026 on operating income of $19.7 billion and revenue of $87.0 billion "
                 "[F30][F20][F10].", "Net margin was 22.7% in FY2026 [F30].", "22.7%", id="PG margin, relabelled"),
    # CAT FY2025 (development): the margin change D476 is FY2025's margin F30 less FY2024's, which the window high D1122
    # is (eval-v1 Haiku's sentence, an Opus flag classed ambiguous before), and its mirror.
    pytest.param("CAT", "Operating margin of 16.5% [F30] is above its 14.3% window median [D1123] but 3.7pp below the "
                 "FY2024 high of 20.2% [D476][D1122].", "Operating margin fell 3.7pp in FY2025 [D476].", "3.7pp",
                 id="CAT margin change against the window high, true"),
    pytest.param("CAT", "Operating margin of 16.5% [F30] is above its 14.3% window median [D1123] but 3.7pp above the "
                 "FY2024 high of 20.2% [D476][D1122].", "Operating margin rose 3.7pp in FY2025 [D476].", "3.7pp",
                 id="CAT margin change against the window high, its mirror"),
    # Fix 3's operating cash flow / net income window figures, which packs-v2 appends (C reads them, K0 cannot):
    # COST's window low D721 is its FY2022 value D225, NVDA's D850 its FY2026 value D435 (development), CAT's median
    # D1158 its FY2022 value D291. The mislabel is fix 3's own class, free cash flow for operating cash flow.
    pytest.param("COST", "Free cash flow was 1.26x net income in FY2022 [D225], the window low [D721].",
                 "Free cash flow was 1.26x net income in FY2022 [D225], the lowest of the window.", "1.26x",
                 id="COST window low, relabelled"),
    pytest.param("COST", "Operating cash flow was 1.26x net income in FY2022 [D225], the window low [D721].",
                 "Operating cash flow was 1.26x net income in FY2022 [D225], the lowest of the window.", "1.26x",
                 id="COST window low, true"),
    pytest.param("NVDA", "Free cash flow was 0.86x net income in FY2026 [D435], the window low [D850].",
                 "Free cash flow was 0.86x net income in FY2026 [D435], the lowest of the window.", "0.86x",
                 id="NVDA window low, relabelled"),
    pytest.param("CAT", "Free cash flow was 1.16x net income in FY2022 [D291], the window median [D1158].",
                 "Free cash flow was 1.16x net income in FY2022 [D291], the median of the window.", "1.16x",
                 id="CAT window median, relabelled"),
    # ORCL FY2026 (eval-v1 DeepSeek): free cash flow F104 is operating cash flow F84 less capex F94, so each of the three
    # is the gate's calculation over the other two (an inversion of the pack's own formula), and its relabel.
    *[pytest.param("ORCL", f"{lead} rose 53.6% to $32.0 billion, 47.5% of revenue, but capex of $55.7 billion pushed {tail} "
                   "to -$23.7 billion [D426][F84][D406][F94][F104].",
                   f"{lead} rose 53.6% to $32.0 billion, 47.5% of revenue, but capex of $55.7 billion pushed {tail} "
                   "to -$23.7 billion [D426][F84][D406][F104].", claim, id=f"ORCL {claim}, {kind}")
      for lead, tail, kind in (("Operating cash flow", "free cash flow", "true"), ("Free cash flow", "operating cash flow",
                                                                                  "relabelled"))
      for claim in ("$32.0 billion", "$55.7 billion", "-$23.7 billion")],
]


@pytest.mark.parametrize("ticker, cited_with, cited_without, claim", ONE_QUANTITY)
def test_a_figure_cited_beside_what_it_is_computed_from_is_one_quantity(semantics: Any, ticker: str, cited_with: str,
                                                                       cited_without: str, claim: str) -> None:
    classes = {}
    for folder in ("packs", "packs-v2"):
        pack = _load(folder, ticker)
        for name, text in (("with", cited_with), ("without", cited_without)):
            if all(i in pack["values"] for i in _cited(text)):  # packs/ lacks packs-v2's appended IDs
                classes[(folder, name)] = _flag_class(semantics, text, claim, pack)
    assert ("packs-v2", "with") in classes and ("packs", "without") in classes  # C's sentence and K0's
    assert classes == dict.fromkeys(classes, "substantive")


# Different metrics that print one number stay two quantities, whatever the sentence cites: the merge reads the pack's
# derivation, never the value alone.
DIFFERENT_METRICS = [
    # USB: two CAGRs of different series, 2.78% and 2.83% (eval-v1 Sonnet, an Opus flag).
    pytest.param("USB", "From FY2016 to FY2025 net interest income compounded at 4.0% [F115], ahead of noninterest income "
                 "at 2.8% [F116] and net income at 2.8% [F117].", "2.8%", id="USB two CAGRs"),
    # VRTX pays no dividend, so its buybacks plus dividends D441 (inputs: buybacks X147 alone) equal its buybacks to
    # the cent, and their share of free cash flow D442 (inputs D441, F105) equals the gate's buybacks over free cash
    # flow: one number, two names, neither the pack's calculation of the other. Both names are true, so a flag on the
    # number is likely the gate's choice of name; only a window figure is the one input it equals.
    pytest.param("VRTX", "Buybacks of $2.02 billion absorbed 63.2% of free cash flow in FY2025 [X147][F105][D442].", "63.2%",
                 id="VRTX share of free cash flow, no dividend"),
    pytest.param("VRTX", "Buybacks of $2.02 billion absorbed 63.2% of free cash flow in FY2025 [X147][D441][D442].",
                 "$2.02 billion", id="VRTX buybacks plus no dividend"),
    # eval-v1 DeepSeek's VRTX sentence (flagged by Opus and V4 Pro): 63.17% and its difference from a -0.04% share
    # count change, 63.13%.
    pytest.param("VRTX", "Buybacks of $2.02 billion absorbed 63.2% of free cash flow in FY2025, yet the diluted share "
                 "count was unchanged [D441][D442][D459].", "63.2%", id="VRTX recorded sentence"),
    # MSFT FY2026: the margin's change (+1.16pp) and its bridge's residual (+1.22pp) (eval-v1 Sonnet, an Opus flag).
    pytest.param("MSFT", "The FY2026 bridge was +1.2pp in total: cost of revenue cost 0.9pp, R&D added 0.8pp and other "
                 "lines added 1.2pp [D487][D500][D501][D502].", "1.2pp", id="MSFT bridge residual"),
    # PG FY2026 has no operating-expense line, so its gap D482 (-2.15pp) is revenue growth less the growth of revenue
    # less operating income, which no pack value holds: the difference of revenue growth D457 and cost-of-revenue
    # growth D472 (-2.08pp) is another metric (review 9 arm-fairness [0]'s substitute). TGT FY2025 likewise.
    pytest.param("PG", "In FY2026 revenue rose 3.3% while cost of revenue rose 5.3%, a 2.1pp gap [D457][D472][D482].",
                 "2.1pp", id="PG gap against cost of revenue"),
    pytest.param("TGT", "In FY2025 revenue fell 1.7% while cost of revenue fell 1.3%, a 0.4pp gap [D416][D431][D439].",
                 "0.4pp", id="TGT gap against cost of revenue"),
]


@pytest.mark.parametrize("ticker, text, claim", DIFFERENT_METRICS)
def test_different_metrics_that_print_one_number_stay_two(semantics: Any, ticker: str, text: str, claim: str) -> None:
    assert [_flag_class(semantics, text, claim, _load(folder, ticker)) for folder in ("packs", "packs-v2")] == ["ambiguous"] * 2


def _window_pack(low_inputs: list[str]) -> dict[str, Any]:
    values = {"F1": ("Operating margin", "FY2024", 7.5), "F2": ("Operating margin", "FY2025", 5.0),
              "F3": ("Gross margin", "FY2025", 5.0),
              "D1": ("Operating margin window low (FY2025)", "FY2024..FY2025", 5.0)}
    pack = {"values": {vid: {"id": vid, "label": label, "period": period, "unit": "pct", "value": value}
                       for vid, (label, period, value) in values.items()}, "passages": [], "red_flags": []}
    pack["values"]["D1"].update(formula="minimum over window", inputs=low_inputs)
    return pack


@pytest.mark.parametrize("text, low_inputs, expected", [
    ("Net margin was 5.0% in FY2025 [F2], the window low [D1].", ["F2"], "substantive"),   # the low is the year's value
    ("Net margin was 5.0% in FY2025 [F3], the window low [D1].", ["F2"], "ambiguous"),     # another series, one number
    ("Net margin was 5.0% in FY2025 [F2], the window low [D1].", ["F1"], "ambiguous"),     # not the point it selected
])
def test_a_window_figure_is_only_the_point_of_its_own_series(semantics: Any, text: str, low_inputs: list[str],
                                                             expected: str) -> None:
    assert _flag_class(semantics, text, "5.0%", _window_pack(low_inputs)) == expected


def test_every_committed_derivation_is_the_gate_s_own_calculation(semantics: Any) -> None:
    """The derivations ``classify_flag`` reads, on every committed pack of both versions: each growth gap whose pack
    holds the operating-expense growth is revenue growth less it (95 of 144 per version; the other 49 have no
    operands), and each metrics-table value the dataset calculated (margins, free cash flow, working capital, the
    current ratio, CAGRs: 1,112 per version) is the gate's calculation over the series its formula names. A rebuilt
    pack that breaks one fails here, not silently in the measure."""
    for folder in ("packs", "packs-v2"):
        gaps, gaps_found, calculated, calculated_found = 0, 0, 0, 0
        for path in sorted((RECORDS / folder).glob("*.json.gz")):
            pack = json.loads(gzip.decompress(path.read_bytes()))
            series_ids = semantics._series_ids(pack)
            for (series, _), vid in series_ids.items():
                value = pack["values"][vid]
                if series not in semantics._COMPUTED_FROM and value.get("source") != "calculated":
                    continue
                operands = semantics._operands(vid, pack, series_ids)
                gap = series in semantics._COMPUTED_FROM
                gaps, calculated = gaps + gap, calculated + (not gap)
                if not operands:
                    continue
                found = factcheck.candidates([vid, *sorted(operands)], pack)
                cited = next(c for c in found if c.how == "cited" and c.ids == (vid,))
                assert semantics._computed_as(cited, found, pack, series_ids) is not None, (folder, path.name, vid)
                gaps_found, calculated_found = gaps_found + gap, calculated_found + (not gap)
        assert (gaps, gaps_found, calculated, calculated_found) == (144, 95, 1112, 1112), folder


def test_a_planted_relabel_of_a_cagr_counts(semantics: Any) -> None:
    """plant-sem's REGN relabel: "Operating cash flow compounded at 12.8% a year" cites the revenue CAGR [F198] with
    its two levels [F1][F10]. The auditor flagged 12.8% and the flag was classed ambiguous, so that this planted error
    counted only through the sentence's other flags; it is one quantity, and counts on its own."""
    run = RECORDS / "runs" / "plant-sem"
    audit = json.loads((run / "semantics" / "claude-sonnet-5-5" / "REGN.json").read_text())
    record = json.loads((run / "claude-sonnet-5-5" / "REGN.json").read_text())
    item = next(i for i in audit["items"] if i["label"] == "mismatch" and i["claim"] == "12.8%")
    sentences = [s for section in record["output"]["sections"] for s in section["sentences"]]
    text = next(s["text"] for s in sentences if factcheck.CITATION_RE.sub("", s["text"]).strip() == item["sentence"])
    assert "Operating cash flow compounded at 12.8%" in text and _cited(text) == ["F1", "F10", "F198"]
    assert semantics.classify_flag(item, sentences, _load("packs", "REGN"), audit.get("view", 1)) == "substantive"


def test_these_tests_leave_the_real_bootstrap_unloaded() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
