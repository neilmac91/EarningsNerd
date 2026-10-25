"""The version-2 repair loop's code fixes (evals/trend_depth/autocite.py; DEEPSEEK-ERRORS.md fixes 1 and 5).

Fix 1 appends a figure's missing ID only when the figure is that ID's own value at its printed precision, the ID is
cited elsewhere in the analysis or is an input of a cited derived value, the claim's one year is the ID's, and the
ID's whole label (a "% of" denominator and a window or peer reference included) is attached to the figure; and then
only when appending it changes no other claim's verdict. Each refusal below is a shape of wrong number that must
stay a gate failure. The review's leaks (a difference read as a level, a red flag's threshold read as a level, a
label's denominator or window word dropped, an appended ID verifying another claim) and the substitution test's
recorded leaks run on their real sentences and committed packs, as do DEEPSEEK-ERRORS.md §1.1's seven own-ID
omissions, three of which the safe core still fixes. Fix 5 retypes a figures-only cause that cites no passage, and
only that. ``autocite`` is pure, so it is imported directly.
"""
from __future__ import annotations

import gzip
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import autocite, factcheck

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"


def _value(vid: str, label: str, period: str, unit: str, number: float, **extra: Any) -> tuple[str, dict[str, Any]]:
    return vid, {"id": vid, "label": label, "period": period, "unit": unit, "value": number, **extra}


SERIES = {"F1": "revenue|FY2024", "F2": "revenue|FY2025", "F3": "gross_margin|FY2024", "F4": "gross_margin|FY2025",
          "F5": "operating_margin|FY2025", "F6": "net_margin|FY2025", "D1": "ch:gross_margin|FY2025",
          "D2": "net_cash_to_revenue|FY2025", "D3": "peer_pctile:net_cash_to_revenue|FY2025",
          "D4": "peer_median:net_cash_to_revenue|FY2025", "D5": "fcf_to_ni|FY2025", "D6": "fcf_to_ni|FY2024",
          "D7": "g:revenue|FY2025", "D8": "cs:sga|FY2025", "D9": "incremental_margin|FY2025", "D10": "g:seg_cloud|FY2025",
          "D11": "net_cash_to_assets|FY2025", "D12": "efficiency_ratio|FY2025", "D13": "peer_median:efficiency_ratio|FY2025",
          "D14": "net_cash_to_revenue_reported|FY2025", "D16": "cagr:revenue|FY2022..FY2025", "D17": "g:cloud_revenue|FY2025",
          "D18": "cs:other_income|FY2025"}
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
        _value("D12", "Efficiency ratio (noninterest expense / revenue)", "FY2025", "pct", 52.42),
        _value("D13", "Efficiency ratio: banks peer median (n=7)", "FY2025", "pct", 61.65),
        _value("D14", "Net cash % of revenue (as reported)", "FY2025", "pct", 2.1),
        _value("D16", "Revenue CAGR", "FY2022..FY2025", "pct", -5.3),
        _value("D17", "Cloud revenue growth", "FY2025", "pct", -12.0),
        _value("D18", "Other income % of revenue", "FY2025", "pct", -24.0),
    ]),
    "series_keys": {key: vid for vid, key in SERIES.items()},
    "passages": [{"id": "P1", "text": "A one-off gain on the sale of a building."}],
    "red_flags": [{"id": "R1", "detail": "Free cash flow ran below 80% of net income in FY2024, FY2025.",
                   "evidence": ["D6", "D5"], "kind": "weak_cash_conversion"}],
}


def _output(*sentences: tuple[str, str]) -> dict[str, Any]:
    return {"sections": [{"key": "cash", "sentences": [{"type": kind, "text": text} for kind, text in sentences]}]}


def _cite(*sentences: tuple[str, str], pack: dict[str, Any] = PACK) -> tuple[list[str], dict[str, Any]]:
    """The texts after auto-citation, and its record."""
    fixed, cited = autocite.autocite(_output(*sentences), pack)
    return [s["text"] for s in fixed["sections"][0]["sentences"]], cited


@lru_cache(maxsize=None)
def _pack(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


@pytest.mark.parametrize("sentences, vid", [
    # NVDA: the level a cited change was computed from, of the change's own year (cited nowhere else).
    ((("comparison", "Gross margin fell 3.9pp to 71.1% [D1]."),), "F4"),
    # The level of a percentile, cited elsewhere, its whole label by the figure: "net cash" before it, "of revenue" after.
    ((("fact", "Net cash was 2.1% of revenue [D2]."),
      ("comparison", "Net cash of 2.1% of revenue ranks in the 83rd percentile of six energy peers, whose median is -7.7% [D3][D4].")),
     "D2"),
    # JPM: the label right after the figure ("the 52.4% efficiency ratio"), against a peer median it is no part of.
    ((("fact", "The efficiency ratio was 52.4% in FY2025 [D12]."),
      ("comparison", "Against seven bank peers the 52.4% efficiency ratio sits above the 61.7% median [D13].")), "D12"),
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
    # CVX: the label's denominator is not by the figure ("net cash position", not "net cash % of revenue").
    ((("fact", "Net cash was 2.1% of revenue [D2]."),
      ("comparison", "That 2.1% net cash position ranks in the 83rd percentile of six energy peers, whose median is -7.7% [D3][D4].")), 1),
    # Two candidates fit (twin labels): neither is chosen.
    ((("fact", "Net cash was 2.1% of revenue [D2]."), ("fact", "Net cash was 2.1% of revenue as reported [D14]."),
      ("comparison", "Net cash of 2.1% of revenue ranks in the 83rd percentile [D3].")), 1),
    # "fell 30.3%" states a change: a share of revenue is no reading of it.
    ((("fact", "SG&A was 30.3% of revenue [D8]."), ("comparison", "SG&A fell 30.3% of revenue [D7].")), 1),
    # The candidate's name is modified: "Incremental operating margin" is no operating margin.
    ((("fact", "Operating margin was 20.0% [F5]."), ("comparison", "Incremental operating margin was 20.0% [D9].")), 1),
    # The candidate's name is modified: "Cloud revenue" is no company revenue.
    ((("fact", "Revenue was $110.0 billion in FY2025 [F2]."), ("comparison", "Cloud revenue rose 11.2% to $110.0 billion [D10].")), 1),
    # ORCL: "its revenue" is the unit's, not the company's (here no segment line is cited to say so).
    ((("fact", "Revenue was $110.0 billion in FY2025 [F2]."),
      ("comparison", "The unit grew fast, and its revenue rose 10.0% to $110.0 billion [D7].")), 1),
    # The phrase is a reference ("median") and the candidate is a company's level.
    ((("fact", "Operating margin was 20.0% [F5]."), ("comparison", "Peers trail, whose median operating margin is 20.0% [D9].")), 1),
    # "growth" names the figure before it ("11.2% growth and"), not the claim.
    ((("fact", "Revenue grew 10.0% [D7]."), ("comparison", "Cloud added 11.2% growth and now is 10.0% of revenue [D10].")), 1),
    # The sentence names two years and binds neither to the figure: the claim has no one year (NEE's "on total debt of").
    ((("fact", "Gross margin was 75.0% in FY2024 [F3]."),
      ("comparison", "Revenue reached $110.0 billion in FY2025 from FY2024, with gross margin at 75.0% [F2].")), 1),
    # Another year of a series the sentence cites: as likely a wrong year as an omission.
    ((("fact", "Revenue was $100.0 billion in FY2024 [F1]."), ("comparison", "Revenue reached $100.0 billion, up from FY2024 [F2].")), 1),
    # A qualifier's latitude is no own value: 71.1% is "above 70.0%", but 70.0% is not 71.1%.
    ((("fact", "Gross margin was 71.1% in FY2025 [F4]."), ("comparison", "Gross margin stayed above 70.0% in FY2025 [D1].")), 0),
    # SNAP: a difference of two levels is never read, though the other side is cited elsewhere.
    ((("fact", "Operating margin was 20.0% [F5]."),
      ("comparison", "Net margin of 21.2% [F6] beat operating margin by 1.2pp, helped by a one-off gain [P1].")), 0),
    # ORCL: a red flag's threshold is never read, though the sentence cites all of the flag's evidence.
    ((("comparison", "Free cash flow has run below 80% of net income for two years, at -1.39x in FY2025 [D6][D5]."),), 0),
    # A direction word makes the figure a change: a difference of two margins of one year does not reconcile it.
    ((("fact", "Operating margin was 20.0% [F5]."), ("comparison", "Operating margin improved a solid 1.2pp [F6].")), 0),
    # A difference of two changes is no reading of a figure.
    ((("fact", "Revenue grew 10.0% [D7]."), ("comparison", "Cloud growth beat revenue growth by 1.2pp [D10].")), 0),
    # The gate would verify "rose 12.0%" only through another value (D17 less D18), not as D17's own: D17 fell 12.0%.
    ((("fact", "Cloud revenue growth was -12.0% in FY2025 [D17]."),
      ("comparison", "Cloud revenue growth rose 12.0% in FY2025 [D18].")), 0),
    # An ID whose claim a backstop would then fail (U1: a fall printed with no sign) is not appended either.
    ((("fact", "Revenue fell at a 5.3% CAGR from FY2022 to FY2025 [D16]."),
      ("comparison", "Revenue CAGR was 5.3% in FY2025, with an operating margin of 20.0% [F5].")), 1),
    # "against" opens another phrase: "of revenue" names 2.1%, not the $110.0 billion of cash.
    ((("fact", "Revenue was $110.0 billion in FY2025 [F2]."),
      ("comparison", "Net cash was 2.1% of revenue against $110.0 billion of cash [D2].")), 1),
    # "cost of revenue" is no revenue: the word before "of" and the label's words modifies them.
    ((("fact", "Revenue was $110.0 billion in FY2025 [F2]."), ("comparison", "The cost of revenue of $110.0 billion in FY2025 rose [D7].")), 1),
    # A sentence that cites nothing: its figures are thresholds or forecasts more often than omissions.
    ((("fact", "Gross margin was 75.0% in FY2024 [F3]."), ("judgement", "Watch whether gross margin recovers above 75.0% in FY2024.")), 0),
])
def test_a_wrong_or_ambiguous_number_keeps_failing(sentences: tuple, rejected: int) -> None:
    texts, cited = _cite(*sentences)
    assert texts == [text for _, text in sentences] and cited == {"added": [], "rejected": rejected}


# The review's leaks (repair-loop findings 0 to 3) and the substitution test's recorded leaks, on their real sentences
# and committed packs: (packs folder, ticker, a sentence elsewhere citing the candidate, the sentence auto-citation must
# leave failing).
LEAKS = [
    # Capital expenditure printed as free cash flow: $15.8 billion of operating cash flow less F102's $9.4 billion.
    ("packs", "COST", "Free cash flow was $9.4 billion in FY2026 [F102].",
     "Operating cash flow of $15.8 billion was 1.71x net income, and free cash flow of $6.4 billion was 1.02x [F82][F42][D421][D422]."),
    ("packs-v2", "COST", "Free cash flow was $9.4 billion in FY2026 [F102].",
     "Operating cash flow of $15.8 billion was 1.71x net income, and free cash flow of $6.4 billion was 1.02x [F82][F42][D421][D422]."),
    # A peer gap printed as the margin: the 31.0% median less F60's 10.7%.
    ("packs", "AMD", "Operating margin was 10.7% in FY2025 [F60].",
     "Operating margin of 20.3% is at the 17th percentile against a semis peer median of 31.0% [D818][D819]."),
    # A red flag's threshold printed as the level: the current ratio is 0.55x, free cash flow -0.34x, -1.39x, 0.40x.
    ("packs", "DUK", "", "The current ratio was 1.0x in FY2025 [F177]."),
    ("packs-v2", "DUK", "", "The current ratio was 1.0x in FY2025 [F177]."),
    ("packs", "DUK", "", "Free cash flow was 80% of net income in FY2025 [D269][D309][D347]."),
    ("packs", "ORCL", "", "Free cash flow equalled 80% of net income in FY2026 [D362][D409]."),
    ("packs", "KO", "", "Free cash flow equalled 80% of net income in FY2025 [D387][D437]."),
    # A "% of" label's denominator: D438 is a share of operating cash flow; the share of revenue is 3.0% (D429).
    ("packs", "NVDA", "Stock-based compensation was 6.2% of operating cash flow in FY2026 [D438].",
     "Stock-based compensation of 6.2% of revenue in FY2026 followed growth of 34.8% [D469]."),
    ("packs-v2", "NVDA", "Stock-based compensation was 6.2% of operating cash flow in FY2026 [D438].",
     "Stock-based compensation of 6.2% of revenue in FY2026 followed growth of 34.8% [D469]."),
    # A window median printed as the year's level: FY2025's R&D share is 3.18% (D442), the median 3.28% (D1132).
    ("packs", "CAT", "The window median of R&D was 3.3% of revenue [D1132].", "R&D was 3.3% of revenue in FY2025, while revenue grew 4.3% [D463]."),
    ("packs-v2", "CAT", "The window median of R&D was 3.3% of revenue [D1132].", "R&D was 3.3% of revenue in FY2025, while revenue grew 4.3% [D463]."),
    # An appended F60 would verify '20.3%' as the median less F60 (revenue grew 34.3%): F60 fits '10.7%' but stays out.
    ("packs", "AMD", "Operating margin was 10.7% in FY2025 [F60].",
     "Operating margin was 10.7% against a 31.0% semis peer median, and revenue grew 20.3% [D818][D819]."),
    # The substitution test's leaks as recorded before: total revenue as the segment's ("its revenue"), revenue growth
    # as a segment's sales ("sales fell").
    ("packs", "ORCL", "Revenue was $67.4 billion in FY2026 [F10].",
     "In FY2026, cloud infrastructure supplied 84% of constant currency cloud growth, and its revenue rose 76.9% to "
     "$67.4 billion [P17][D644][S92]."),
    ("packs", "DE", "Revenue fell 11.7% in FY2025 [D412].",
     "In FY2025 the same segment subtracted 7.0pp from revenue growth as sales fell 11.7% [D869][D868], with U.S. and "
     "Canada volumes down 30% [P10]."),
    # The safe core's own leaks in the first two-arm run, each closed by one rule. A comma or a citation ends a phrase:
    # "of revenue" belongs to 18.3%, not to the $47.9 billion of cash and investments (KO's revenue).
    ("packs", "KO", "Revenue was $47.9 billion in FY2025 [F10].",
     "Net cash was $8.8 billion at FY2025, or 18.3% of revenue, against $47.9 billion of cash and investments [D442][D443]."),
    ("packs", "DUK", "Revenue was $22.7 billion in FY2016 [F1].",  # the comma alone: "from" opens no phrase
     "Net debt reached $89.6 billion in FY2025, 282.3% of revenue, from $22.7 billion in FY2016 [D352][D353]."),
    # "and" and "with" open another phrase: "growth" belongs to 7.2pp and to the product, not to revenue.
    ("packs", "COST", "Revenue grew 10.1% in FY2026 [D434].", "By segment, the United States contributed 7.2pp of growth and "
     "10.1% of revenue [D672]."),
    ("packs", "VRTX", "Revenue grew 8.9% in FY2025 [D446].", "TRIKAFTA/KAFTRIO is 85.9% of revenue with growth of 8.9%, so "
     "one product's saturation now sets the top line [D529]."),
    # The run after a figure takes only the label's words, "of" and articles: "on growth in Microsoft Cloud" is a cause.
    ("packs", "MSFT", "Microsoft Cloud grew 26.9% in FY2026 [D567].", "FY2026 was the sharpest step, with revenue up 26.9% on "
     "growth in Microsoft Cloud, Azure and Microsoft 365 Commercial cloud [P17]."),
    # "cost of revenue" is no revenue: a word before "of" and the label modifies it.
    ("packs", "VRTX", "Revenue was $12.00 billion in FY2025 [F10].", "Inventory days rose from 287 to 373 [D397][D444], and "
     "inventory of $1.69 billion [X178] exceeded FY2025 cost of revenue of $12.00 billion [X30]."),
    # A movement word after the figure ("rise") makes it a change: a share of revenue is no reading of it.
    ("packs", "SNAP", "Cost of revenue was 45.0% of revenue in FY2025 [D386].", "The passages provided do not explain the "
     "45.0% cost-of-revenue rise [D421] behind the 1.1pp gain [D431]."),
    # FY2024 is 6.0%'s year, not $10.7 billion's, whose cited values are of two years: the claim has no one year.
    ("packs", "JPM", "The provision was $10.7 billion in FY2024 [X146].", "Provision for credit losses rose to $10.7 billion, "
     "7.8% of revenue against 6.0% in FY2024, a 1.8pp increase [D208][D185]."),
    # A sentence citing a segment line takes no company-wide value: NEER's net income is not NEE's.
    ("packs", "NEE", "Net income was $6.83 billion in FY2025 [F32].", "The filing ties NEER's higher results, to $6.83 billion "
     "of net income [S29], to new investments, partly offset by higher financing costs [P26]."),
    # "plus" is no word of "Buybacks plus dividends": the total is not the buybacks.
    ("packs", "MSFT", "Buybacks plus dividends were $48.7 billion in FY2026 [D467].", "Buybacks of $48.7 billion plus "
     "dividends of $26.4 billion absorbed 72.7% of free cash flow [X157][D468]."),
]


@pytest.mark.parametrize("folder, ticker, elsewhere, sentence", LEAKS)
def test_the_reviews_leaks_stay_gate_failures(folder: str, ticker: str, elsewhere: str, sentence: str) -> None:
    pack = _pack(folder, ticker)
    texts, cited = _cite(*([("fact", elsewhere)] if elsewhere else []), ("comparison", sentence), pack=pack)
    assert texts[-1] == sentence and not [a for a in cited["added"] if a["sentence"] == sentence]
    assert not factcheck.check([{"section": "cash", "text": sentence, "type": "comparison"}], pack, backstops=True)["passed"]


def test_an_id_that_would_verify_another_claim_is_not_appended() -> None:
    pack = _pack("packs", "AMD")
    sentence = {"section": "cash", "type": "comparison",
                "text": "Operating margin was 10.7% against a 31.0% semis peer median, and revenue grew 20.3% [D818][D819]."}
    found = autocite.search(sentence, pack, ["F60"])
    assert [(s.claim, s.accepted) for s in found] == [("10.7%", "F60"), ("20.3%", None)]  # F60 is 10.7%'s own value
    assert autocite.cite_sentence(sentence, pack, ["F60"]) == (sentence["text"], [], 1)  # but would verify '20.3%'


# DEEPSEEK-ERRORS.md §1.1's seven own-ID omissions, on their recorded first passes: (folder, ticker, a sentence
# elsewhere citing the ID, the first pass's sentence, the ID appended or None when it now goes to a repair).
OMISSIONS = [
    ("packs", "NVDA", "", "Gross margin fell 3.9pp to 71.1% and drove the 2.0pp operating-margin decline, partly offset "
     "by R&D and SG&A leverage of 1.3pp and 0.6pp [D462][D463][D478][D479].", "F30"),  # eval-v1
    ("packs", "NVDA", "", "Gross margin fell 3.9pp to 71.1%, the main drag on operating margin, which slipped 2.0pp "
     "[D462][D463].", "F30"),  # dev-v4
    ("packs", "JPM", "The efficiency ratio was 52.4% in FY2025 [D207].", "Against seven bank peers the 52.4% efficiency "
     "ratio sits at the 0th percentile versus a 61.7% median, while return on average equity of 16.1% is at the 100th "
     "percentile against an 11.8% median [D336][D337][D213][D338][D339].", "D207"),
    # D352 is "Net cash % of revenue": its denominator is not by the figure.
    ("packs", "CVX", "Net cash was 2.1% of revenue in FY2025 [D352].", "That 2.1% net cash position ranks in the 83rd "
     "percentile of six energy peers, whose median is -7.7% [D637][D638].", None),
    # D355 is "Cash burn": "cash" is not by the figure ("the latest $1.7 billion burn").
    ("packs", "DUK", "", "Cash of $245 million covers only 0.1 years of the latest $1.7 billion burn [F137][D356][R2].", None),
    # A red flag's threshold, and a difference of two levels, are no longer read.
    ("packs", "ORCL", "", "Free cash flow has run below 80% of net income for two years, at -1.39x in FY2026 [D362][D409].", None),
    ("packs", "SNAP", "Operating margin was -9.0% in FY2025 [F30].", "Net margin of -7.8% [F50] beat operating margin by "
     "1.2pp, helped by $96.7 million of debt-extinguishment gains in other income [P18].", None),
]


@pytest.mark.parametrize("folder, ticker, elsewhere, sentence, vid", OMISSIONS)
def test_the_recorded_own_id_omissions(folder: str, ticker: str, elsewhere: str, sentence: str, vid: Any) -> None:
    texts, cited = _cite(*([("fact", elsewhere)] if elsewhere else []), ("comparison", sentence), pack=_pack(folder, ticker))
    assert texts[-1] == (autocite.with_citation(sentence, vid) if vid else sentence)
    assert [a["id"] for a in cited["added"] if a["sentence"] == sentence] == ([vid] if vid else [])


def test_a_label_whose_words_a_conjunction_joins_is_attached() -> None:
    texts, cited = _cite(("fact", "Buybacks plus dividends were $48.7 billion in FY2026 [D467]."),
                         ("comparison", "Buybacks plus dividends of $48.7 billion absorbed 72.7% of free cash flow [D468]."),
                         pack=_pack("packs", "MSFT"))
    assert texts[-1].endswith("[D468][D467].") and [a["id"] for a in cited["added"]] == ["D467"]


def test_auto_citation_leaves_its_input_unchanged() -> None:
    first = _output(("fact", "Net cash was 2.1% of revenue [D2]."), ("comparison", "Net cash of 2.1% of revenue ranks in the 83rd percentile [D3]."))
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


@pytest.mark.parametrize("text, vid, left", [
    ("Revenue grew 10.0% [D7][F1].", "D7", "Revenue grew 10.0% [F1]."),
    ("Revenue grew 10.0% [D7, F1] and [F2].", "F1", "Revenue grew 10.0% [D7] and [F2]."),
    ("Revenue grew 10.0% [D7].", "F1", "Revenue grew 10.0% [D7]."),
])
def test_an_id_is_taken_out_of_its_citations(text: str, vid: str, left: str) -> None:
    assert autocite.without(text, vid) == left


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


ANALYSIS = _output(
    ("fact", "Operating margin was 20.0% in FY2025 [F5]."), ("fact", "Gross margin was 75.0% in FY2024 [F3]."),
    ("comparison", "Gross margin was 71.1% in FY2025 [F4]."),
    ("comparison", "Operating margin was 20.0% and net margin 21.2% in FY2025 [F5][F6]."),
    ("comparison", "Free cash flow was -1.39x net income in FY2025 [D5][F5]."),
    ("comparison", "Gross margin fell 3.9pp to 71.1% in FY2025 [D1][F4]."))


def test_the_substitution_test_runs_both_arms_and_every_kind() -> None:
    result = autocite.substitution_test([("T", ANALYSIS, PACK)])
    counts = result["counts"]
    assert set(counts) == set(autocite.ARMS) and all(set(counts[arm]) == set(autocite.KINDS) for arm in autocite.ARMS)
    for arm in autocite.ARMS:
        for kind in autocite.KINDS:  # a planted threshold ("80%" from R1) and gap ("1.2%", 21.2% less 20.0%) included
            assert counts[arm][kind].get("substitutes", 0) >= 1, (arm, kind)
            assert "licensed" not in counts[arm][kind], (arm, kind)
    assert counts["omitted"]["gap"]["matches_nothing"] >= 1  # with F5 out, 1.2% reads as nothing: the old route's shape
    assert not result["leaks"]["kept"] and not result["leaks"]["omitted"]
    assert result["control"]["recovered"] >= 1  # "Gross margin fell 3.9pp to 71.1% in FY2025 [D1]" gets F4 back


def test_a_licence_shows_as_a_leak_in_both_arms(monkeypatch: pytest.MonkeyPatch) -> None:
    licensing = lambda sentence, pack, elsewhere: [  # noqa: E731 - a stand-in that licenses every claim
        autocite.Search(index, claim.text, ["F9"], ["F9"]) for index, claim in enumerate(factcheck.parse_claims(sentence["text"]))]
    monkeypatch.setattr(autocite, "search", licensing)
    monkeypatch.setattr(autocite, "_only_targets_changed", lambda *args: True)
    leaked = autocite.substitution_test([("T", ANALYSIS, PACK)])
    for arm in autocite.ARMS:
        for kind in autocite.KINDS:
            assert leaked["counts"][arm][kind]["licensed"] == leaked["counts"][arm][kind]["substitutes"] >= 1, (arm, kind)
        assert leaked["leaks"][arm]


def test_auto_citation_never_loads_the_bootstrap() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
