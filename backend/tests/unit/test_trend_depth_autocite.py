"""The version-2 repair loop's code fixes (evals/trend_depth/autocite.py; DEEPSEEK-ERRORS.md fixes 1 and 5).

Fix 1 appends a figure's missing ID only when exactly one candidate reconciles the figure and fits it: its period
agrees with the sentence's years and its metric words are attached to the figure. Each refusal below is a shape of
wrong number that must stay a gate failure (a wrong year, a wrong metric, an ambiguous match, a level stated as a
change, a phrase that names another cited metric, another year of a cited series). Fix 5 retypes a figures-only
cause that cites no passage, and only that. ``autocite`` is pure, so it is imported directly; the synthetic pack
mimics the recorded failures (CVX 2.1%, NVDA 71.1%, ORCL 80%, SNAP 1.2pp).
"""
from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from evals.trend_depth import autocite, factcheck


def _value(vid: str, label: str, period: str, unit: str, number: float, **extra: Any) -> tuple[str, dict[str, Any]]:
    return vid, {"id": vid, "label": label, "period": period, "unit": unit, "value": number, **extra}


SERIES = {"F1": "revenue|FY2024", "F2": "revenue|FY2025", "F3": "gross_margin|FY2024", "F4": "gross_margin|FY2025",
          "F5": "operating_margin|FY2025", "F6": "net_margin|FY2025", "D1": "ch:gross_margin|FY2025",
          "D2": "net_cash_to_revenue|FY2025", "D3": "peer_pctile:net_cash_to_revenue|FY2025",
          "D4": "peer_median:net_cash_to_revenue|FY2025", "D5": "fcf_to_ni|FY2025", "D6": "fcf_to_ni|FY2024",
          "D7": "g:revenue|FY2025", "D8": "cs:sga|FY2025", "D9": "incremental_margin|FY2025", "D10": "g:seg_cloud|FY2025",
          "D11": "net_cash_to_assets|FY2025"}
PACK: dict[str, Any] = {
    "values": dict([
        _value("F1", "Revenue", "FY2024", "usd", 100e9),
        _value("F2", "Revenue", "FY2025", "usd", 110e9),
        _value("F3", "Gross margin", "FY2024", "pct", 75.0),
        _value("F4", "Gross margin", "FY2025", "pct", 71.1),
        _value("F5", "Operating margin", "FY2025", "pct", 20.0),
        _value("F6", "Net margin", "FY2025", "pct", 21.2),
        _value("D1", "Gross margin change", "FY2025", "pp", -3.9, inputs=["F4", "F3"]),
        _value("D2", "Net cash % of revenue", "FY2025", "pct", 2.0965),
        _value("D3", "Net cash % of revenue: percentile vs energy peers (n=6)", "FY2025", "pctile", 83.33, inputs=["D2"]),
        _value("D4", "Net cash % of revenue: energy peer median (n=6)", "FY2025", "pct", -7.71),
        _value("D5", "Free cash flow / net income", "FY2025", "x", -1.39),
        _value("D6", "Free cash flow / net income", "FY2024", "x", 0.36),
        _value("D7", "Revenue growth", "FY2025", "pct", 10.0, inputs=["F2", "F1"]),
        _value("D8", "SG&A % of revenue", "FY2025", "pct", 30.3),
        _value("D9", "Incremental operating margin (change in operating income / change in revenue)", "FY2025", "pct", 44.8),
        _value("D10", "Cloud (segment) growth", "FY2025", "pct", 11.2),
        _value("D11", "Net cash % of assets", "FY2025", "pct", 2.12),
    ]),
    "series_keys": {key: vid for vid, key in SERIES.items()},
    "passages": [{"id": "P1", "text": "A one-off gain on the sale of a building."}],
    "red_flags": [{"id": "R1", "detail": "Free cash flow ran below 80% of net income in FY2024, FY2025.",
                   "evidence": ["D6", "D5"], "kind": "weak_cash_conversion"}],
}


def _output(*sentences: tuple[str, str]) -> dict[str, Any]:
    return {"sections": [{"key": "cash", "sentences": [{"type": kind, "text": text} for kind, text in sentences]}]}


def _cite(*sentences: tuple[str, str]) -> tuple[list[str], dict[str, Any]]:
    """The texts after auto-citation, and its record."""
    fixed, cited = autocite.autocite(_output(*sentences), PACK)
    return [s["text"] for s in fixed["sections"][0]["sentences"]], cited


@pytest.mark.parametrize("sentences, vid", [
    # CVX: the level of a percentile stated without its ID, which an earlier sentence cites.
    ((("fact", "Net cash was 2.1% of revenue [D2]."),
      ("comparison", "That 2.1% net cash position ranks in the 83rd percentile of six energy peers, whose median is -7.7% [D3][D4].")),
     "D2"),
    # NVDA: the level a cited change was computed from, of the change's own year (cited nowhere else).
    ((("comparison", "Gross margin fell 3.9pp to 71.1% [D1]."),), "F4"),
    # ORCL: a red flag's threshold, when the sentence cites all of the flag's evidence.
    ((("comparison", "Free cash flow has run below 80% of net income for two years, at -1.39x in FY2025 [D6][D5]."),), "R1"),
    # SNAP: the other side of a difference of two levels of one year.
    ((("fact", "Operating margin was 20.0% [F5]."),
      ("comparison", "Net margin of 21.2% [F6] beat operating margin by 1.2pp, helped by a one-off gain [P1].")),
     "F5"),
])
def test_a_figure_stated_without_its_own_id_gets_it(sentences: tuple, vid: str) -> None:
    texts, cited = _cite(*sentences)
    assert texts[-1] == sentences[-1][1][:-1] + f"[{vid}]." and cited["rejected"] == 0
    assert [(a["sentence"], a["id"]) for a in cited["added"]] == [(sentences[-1][1], vid)]  # the text the model wrote
    assert texts[:-1] == [text for _, text in sentences[:-1]]  # nothing else is touched
    assert factcheck.check([{"section": "cash", "text": t, "type": "fact"} for t in texts], PACK)["failures"] == []


@pytest.mark.parametrize("sentences, rejected", [
    # A wrong year: 75.0% is FY2024's margin, cited elsewhere, in a sentence about FY2025.
    ((("fact", "Gross margin was 75.0% in FY2024 [F3]."), ("comparison", "Gross margin fell 3.9pp to 75.0% [D1].")), 1),
    # A wrong metric: no word of the value's label stands by the figure.
    ((("fact", "Net cash was 2.1% of revenue [D2]."), ("comparison", "That 2.1% stake ranks in the 83rd percentile [D3].")), 1),
    # Two candidates fit: neither is chosen.
    ((("fact", "Net cash was 2.1% of revenue [D2]."), ("fact", "Net cash was 2.1% of assets [D11]."),
      ("comparison", "That 2.1% net cash position ranks in the 83rd percentile [D3].")), 1),
    # "fell 30.3%" states a change: a share of revenue is no reading of it.
    ((("fact", "SG&A was 30.3% of revenue [D8]."), ("comparison", "SG&A fell 30.3% [D7].")), 1),
    # The candidate's name is modified: "Incremental operating margin" is no operating margin.
    ((("fact", "Operating margin was 20.0% [F5]."), ("comparison", "Incremental operating margin was 20.0% [D9].")), 1),
    # The candidate's name is modified: "Cloud revenue" is no company revenue.
    ((("fact", "Revenue was $110.0 billion in FY2025 [F2]."), ("comparison", "Cloud revenue rose 11.2% to $110.0 billion [D10].")), 1),
    # The phrase is a reference ("median") and the candidate is a company's level.
    ((("fact", "Operating margin was 20.0% [F5]."), ("comparison", "Peers trail, whose median operating margin is 20.0% [D9].")), 1),
    # "growth" names the figure before it ("11.2% growth and"), not the claim.
    ((("fact", "Revenue grew 10.0% [D7]."), ("comparison", "Cloud added 11.2% growth and now is 10.0% of revenue [D10].")), 1),
    # Another year of a series the sentence cites sits as near as the cited year: as likely a wrong year as an omission.
    ((("fact", "Revenue was $100.0 billion in FY2024 [F1]."), ("comparison", "Revenue reached $100.0 billion, up from FY2024 [F2].")), 1),
    # A direction word makes the figure a change: a difference of two margins of one year does not reconcile it.
    ((("fact", "Operating margin was 20.0% [F5]."), ("comparison", "Operating margin improved a solid 1.2pp [F6].")), 0),
    # A difference of two changes is no reading of a figure.
    ((("fact", "Revenue grew 10.0% [D7]."), ("comparison", "Cloud growth beat revenue growth by 1.2pp [D10].")), 0),
    # A flag whose evidence the sentence cites only in part, though another sentence cites the flag.
    ((("comparison", "Free cash flow has run below 80% of net income for two years, at -1.39x in FY2025 [D5]."),
      ("fact", "That is the weak-conversion flag [R1].")), 0),
    # A sentence that cites nothing: its figures are thresholds or forecasts more often than omissions.
    ((("fact", "Gross margin was 75.0% in FY2024 [F3]."), ("judgement", "Watch whether gross margin recovers above 75.0% in FY2024.")), 0),
])
def test_a_wrong_or_ambiguous_number_keeps_failing(sentences: tuple, rejected: int) -> None:
    texts, cited = _cite(*sentences)
    assert texts == [text for _, text in sentences] and cited == {"added": [], "rejected": rejected}


def test_auto_citation_leaves_its_input_unchanged() -> None:
    first = _output(("fact", "Net cash was 2.1% of revenue [D2]."), ("comparison", "That 2.1% net cash position ranks in the 83rd percentile [D3]."))
    before = json.dumps(first)
    fixed, cited = autocite.autocite(first, PACK)
    assert json.dumps(first) == before and cited["added"] and fixed != first


@pytest.mark.parametrize("text, cited", [
    ("Revenue grew 10.0% [D7].", "Revenue grew 10.0% [D7][F1]."),
    ("Revenue grew 10.0% [D7]", "Revenue grew 10.0% [D7][F1]"),
    ("Revenue grew 10.0% [D7], a record.", "Revenue grew 10.0% [D7], a record [F1]."),
])
def test_an_id_is_appended_after_the_closing_citations(text: str, cited: str) -> None:
    assert autocite.with_citation(text, "F1") == cited


@pytest.mark.parametrize("text, kind", [
    # MSFT: a margin bridge, all figures and the names of what it cites.
    ("The FY2025 gross-margin fall came from operating margin (-3.9pp), partly offset by net margin [D1][F5][F6].", "comparison"),
    # NVDA: "so" opens an explanation the figures do not give.
    ("Gross margin fell 3.9pp [D1], so pricing power is weakening.", "cause"),
    # "as" opens an explanation, though every word names what the sentence cites (MSFT dev-v3).
    ("Gross margin fell 3.9pp as operating margin fell [D1][F5].", "cause"),
    # A causal word outside the explanatory set still says something beyond the figures.
    ("Gross margin fell 3.9pp on lower volumes [D1].", "cause"),
    # It cites a passage: the gate's own rule decides.
    ("Gross margin fell 3.9pp [D1][P1].", "cause"),
])
def test_only_a_figures_only_cause_without_a_passage_is_retyped(text: str, kind: str) -> None:
    fixed, retyped = autocite.retype(_output(("cause", text)), PACK)
    assert fixed["sections"][0]["sentences"][0]["type"] == kind
    assert retyped == ([{"section": "cash", "sentence": text, "from": "cause", "to": "comparison"}] if kind == "comparison" else [])


@pytest.mark.parametrize("text, word", [
    ("Margin fell, so conversion is diluted [D1].", "so"),
    ("Margin fell as costs rose [D1].", "as"),
    ("Margin fell because costs rose [D1].", "because"),
    ("Margin fell due to costs [D1].", "due to"),
    ("SG&A was 30.3% as a share of revenue [D8].", None),
    ("Costs such as freight rose [D1].", None),
    ("Margin held as well as cash [D1].", None),
    ("Net income as reported rose [D1].", None),
    ("Margin is the lowest so far [D1].", None),
])
def test_explanatory_clauses_are_told_from_fixed_phrases(text: str, word: Any) -> None:
    assert autocite.explanatory(text) == word


def test_the_substitution_test_counts_what_auto_citation_would_license(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = _output(("fact", "Operating margin was 20.0% in FY2025 [F5]."), ("fact", "Gross margin was 75.0% in FY2024 [F3]."),
                       ("comparison", "Gross margin was 71.1% in FY2025 [F4]."))
    result = autocite.substitution_test([("T", analysis, PACK)])
    assert result["counts"]["year"]["matches_nothing"] >= 1 and result["counts"]["metric"]["matches_nothing"] >= 1
    assert "licensed" not in result["counts"]["year"] and "licensed" not in result["counts"]["metric"] and not result["leaks"]
    licensing = lambda sentence, pack, elsewhere, cache=None: [  # noqa: E731 - a stand-in that licenses every claim
        autocite.Search(0, claim.text, ["F9"], ["F9"]) for claim in factcheck.parse_claims(sentence["text"])]
    monkeypatch.setattr(autocite, "search", licensing)
    leaked = autocite.substitution_test([("T", analysis, PACK)])
    assert leaked["counts"]["year"]["licensed"] == leaked["counts"]["year"]["matches_nothing"] and leaked["leaks"]


def test_auto_citation_never_loads_the_bootstrap() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
