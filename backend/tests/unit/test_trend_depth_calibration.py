"""The depth harness's calibration and form measures (evals/trend_depth/calibration.py, DEEPSEEK-ERRORS.md §1.3, fix 6
and §3 "Measures"): each lexicon on the recorded sentences it was written for and on the true sentences it must leave
alone, the scope each measure counts in, and the eval-v1 counts the lexicons were checked against."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.trend_depth import calibration

RUNS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10" / "runs"
SECTIONS = ("arc", "drivers", "margins", "cash", "balance_sheet", "red_flags", "watch")


def _s(text: str, section: str = "red_flags", kind: str = "comparison") -> dict:
    return {"section": section, "text": text, "type": kind}


@pytest.mark.parametrize("text, words", [
    # Fix 6's own words and their kin, in DeepSeek's eval-v1 data sentences ...
    ("The current ratio of 0.55x is below 1.0x and near the 0.53x window low, leaving little short-term cushion [F177][F178].",
     ["cushion"]),
    ("Operating margin has fallen four straight years, 30.7pp from the FY2021 peak to the FY2025 window low [D486][D470], and "
     "the EYLEA franchise erosion behind it is structural rather than one-off [P3].", ["structural", "one-off"]),
    ("Stock-based compensation was 13.8% of revenue in FY2025 and at least 10% in each of the last five years, persistent "
     "dilution pressure [D223][R3].", ["persistent", "pressure"]),
    ("New electric vehicles still held 67.6% of revenue but fell 12.5%, a concentration risk in a shrinking core [D150][D151].",
     ["risk"]),
    ("Stock-based compensation of $994 million equalled 20.0% of operating cash flow [X77][D431], so cash conversion leans on "
     "a non-cash add-back.", ["leans on"]),
    ("Payout exceeded free cash flow in FY2025 and FY2026, at 116.6% and 100.7%, leaving little room if free cash flow dips "
     "again as it did in FY2025 [D663][D700].", ["little room"]),
    ("The 2.4-year burn coverage flag [R4] is stale: it refers to the FY2022 free cash flow deficit of $1.5 billion, and free "
     "cash flow has been positive in every year since [F92].", ["stale"]),
    ("The revenue basis break is material: FY2018 and FY2019 in the table are recasts [X1][X2].", ["material"]),
    ("The FY2017 SG&A figure was later restated to $3,098.0 million from $3,066.6 million [R8][X34]; the pack uses the "
     "first-reported value, so FY2017 cost ratios are slightly understated.", ["understated"]),
    # ... and the candidate prompt's own example of a verdict on the data, which belongs in a judgement sentence.
    ("Net cash of $4.0 billion is overstated, as long-term debt is not reported after FY2021 [D351].", ["overstated"]),
    # ... and Sonnet's.
    ("The FY2024 revenue decline of 3.4% looks benign, as FY2025 revenue of $67.6 billion exceeded FY2023's $67.1 billion "
     "[D316][F10][F8].", ["benign"]),
    ("Reported total debt of $1.0 billion equals only the current portion, so net cash of $7.1 billion and its 100th "
     "percentile among six peers are unreliable [D336][X203][D337][D850].", ["unreliable"]),
    ("The FY2025 10-K reports a $960 million fall in a trademark's fair value, leaving $2,440 million carrying value and "
     "likely further impairment if projections are missed [P12].", ["likely"]),
    # Data words that only look evaluative.
    ("Automotive cost fell on fewer vehicles, lower raw material and conversion costs [P4].", []),
    ("Raw material purchases rose 8.0% in FY2025 [X1].", []),
    ("The filing says production costs were favourable on lower material costs, partly offset by higher overhead [P16].", []),
    ("IEEPA tariff refunds added three basis points to gross margin net of member price cuts [P30].", []),
    ("Risk-weighted assets rose 4.1% to $1.8 trillion [X20].", []),
    ("Diluted EPS rose 165.0% against net income growth of 164.2%, as the diluted share count was flat at -0.1% [D1][D2].", []),
])
def test_the_evaluative_lexicon_finds_words_that_say_what_figures_mean(text: str, words: list) -> None:
    assert [h["words"] for h in calibration.evaluative([_s(text)])["hits"]] == ([words] if words else [])


def test_evaluative_words_count_only_in_fact_and_comparison_sentences_outside_arc_and_watch() -> None:
    word = "Liquidity is thin: the current ratio was 0.55x against a window low of 0.53x [F177][F178]."
    sentences = [_s(word, "red_flags", "fact"), _s(word, "balance_sheet", "comparison"),  # counted
                 _s(word, "arc", "fact"), _s(word, "watch", "comparison"),  # the arc and the watch list are not data sentences
                 _s(word, "red_flags", "judgement"), _s(word, "red_flags", "cause"),  # meaning belongs in these
                 _s("The current ratio was 0.55x [F177].", "balance_sheet", "fact")]
    found = calibration.evaluative(sentences)
    assert found["sentences"] == 3 and [h["section"] for h in found["hits"]] == ["red_flags", "balance_sheet"]


@pytest.mark.parametrize("text, wording", [
    # Forecasts and consequences in DeepSeek's eval-v1 watch items ...
    ("If capex as a share of revenue stays above the FY2026 34.9%, free cash flow margin will likely remain under the 20.2% "
     "window low [D455][D456][D982].", "will likely"),
    ("Capex: FY2026 capital expenditures above the FY2025 level of $2.8 billion would keep capital intensity at its window "
     "high of 4.2% of revenue [X100][D451].", "would keep"),
    ("R&D as a share of revenue: holding above the FY2025 40.8% [D470] keeps pressure on margin, while a move back toward the "
     "34.6% median [D763] would restore operating leverage.", "keeps pressure"),
    ("Buybacks plus dividends against free cash flow: a ratio below the 179.9% FY2025 level would ease the funding gap; above "
     "it would widen reliance on debt [D445].", "would ease the"),
    ("If buybacks plus dividends exceed the FY2025 $9.0 billion, capital return would move further above the 30% of operating "
     "cash flow framework [D339][P31].", "would move further"),
    # ... and Sonnet's one, whose threshold carries a decimal point before its "if".
    ("Free cash flow margin: it stays below FY2025's 8.8% if capex runs at the guided $18 to $19 billion, versus $17.3 billion "
     "in FY2025, per the FY2026 10-K [D343][P4][F70].", "it stays below FY2025's 8.8% if"),
    # The threshold and the direction that would confirm or reverse the trend are what fix 6 asks for.
    ("Operating margin: a FY2026 reading below the 14.3% window median would confirm the FY2025 erosion; a recovery above the "
     "20.2% FY2024 high would reverse it [D603][D605].", None),
    ("Watch days inventory outstanding against the 165-day FY2025 level; a further rise would signal demand lagging the Data "
     "Center build [D472].", None),
    ("Receivables growth below revenue growth, against 23.6% versus 10.1% in FY2026, would ease the concern in the FY2027 "
     "10-K [D432][D400].", None),
    ("Days inventory above 125 days would confirm the build-up risk, while a return toward 113 days would ease it, as shown "
     "in the FY2027 10-K [D470][D420].", None),
])
def test_the_forecast_lexicon_finds_watch_items_that_say_what_would_follow(text: str, wording: object) -> None:
    hits = calibration.watch_forecasts([_s(text, "watch")])["hits"]
    assert [h["wording"] for h in hits] == ([wording] if wording else [])


def test_forecasts_count_only_in_the_watch_list_and_judgements_only_outside_it() -> None:
    forecast = "Free cash flow margin will likely remain under the 20.2% window low [D982]."
    sentences = [_s(forecast, "watch", "comparison"), _s(forecast, "watch", "judgement"), _s(forecast, "red_flags", "judgement"),
                 _s("Revenue grew 5.6% [D1].", "drivers", "fact")]
    assert calibration.watch_forecasts(sentences)["items"] == 2 and len(calibration.watch_forecasts(sentences)["hits"]) == 2
    assert calibration.judgement_outside_watch(sentences) == {"judgements": 1, "sentences": 2}


def test_form_counts_words_without_citations_sentences_and_the_sections_with_a_sentence() -> None:
    output = {"sections": [
        {"key": "arc", "sentences": [{"type": "fact", "text": "Revenue compounded at 5.4% a year [F1][F10]."}]},
        {"key": "drivers", "sentences": [{"type": "comparison", "text": "Operating costs fell 3.4% [D373]."},
                                         {"type": "cause", "text": "Prices fell [P17]."}]},
        {"key": "margins", "sentences": []},  # a section with no sentence is missing from the reader's view
    ]}
    form = calibration.form(output, SECTIONS)
    # 15 as generate.word_count counts them, which the records' "words" hold: a full stop left by a citation is a word.
    assert (form["words"], form["sentences"], form["sections"]) == (15, 3, 2)
    assert form["missing"] == ["margins", "cash", "balance_sheet", "red_flags", "watch"]


def _recorded(system: str) -> list[dict]:
    out = []
    for path in sorted((RUNS / "eval-v1" / system).glob("*.json")):
        record = json.loads(path.read_text())
        out += [{"section": s["key"], "text": x["text"], "type": x["type"]} for s in record["output"]["sections"] for x in s["sentences"]]
    return out


@pytest.mark.parametrize("system, judgement, evaluative, forecasts", [
    # DEEPSEEK-ERRORS.md §1.3 counted 4 of 530, 18 of 330 and 11 of 60 for DeepSeek by hand (the lexicon also finds DE's
    # "slightly understated"); 20 of 527, 7 of 312 and 1 of 60 for Sonnet.
    ("deepseek-flash", (4, 530), (20, 330), (11, 60)),
    ("claude-sonnet-5-5", (20, 527), (7, 312), (1, 60)),
])
def test_the_measures_reproduce_the_eval_v1_counts_they_were_checked_against(system: str, judgement: tuple, evaluative: tuple,
                                                                              forecasts: tuple) -> None:
    sentences = _recorded(system)
    j = calibration.judgement_outside_watch(sentences)
    e, w = calibration.evaluative(sentences), calibration.watch_forecasts(sentences)
    assert (j["judgements"], j["sentences"]) == judgement
    assert (len(e["hits"]), e["sentences"]) == evaluative
    assert (len(w["hits"]), w["items"]) == forecasts
