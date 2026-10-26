"""The version-2 repair loop's code step before a repair (evals/trend_depth/retype.py; DEEPSEEK-ERRORS.md fix 5, and
fix 1's removal).

Fix 5 retypes a figures-only cause that cites no passage, and only that; an explanatory clause is told from a fixed
phrase. ``first_pass``, the whole code step, adds no ID: auto-citation (fix 1) was removed after reviews 6, 7 and 8 each
found a new class of wrong number it licensed. So a figure stated without its own ID stays a gate failure, which the
repair fixes: on review 8's leaks (a from-level dated by the cited change's year, a base year's level as the current
one), on CVX's committed packs of both versions, and on the three recorded omissions auto-citation used to fix (NVDA's
71.1% in eval-v1 and dev-v4, JPM's 52.4%). The code-only replay of recorded first passes (``real_failures``) decides
through that same function. ``retype`` is pure, so it is imported directly.
"""
from __future__ import annotations

import gzip
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import retype

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"


def _value(vid: str, label: str, period: str, unit: str, number: float, **extra: Any) -> tuple[str, dict[str, Any]]:
    return vid, {"id": vid, "label": label, "period": period, "unit": unit, "value": number, **extra}


PACK: dict[str, Any] = {
    "values": dict([
        _value("F3", "Gross margin", "FY2024", "pct", 75.0),
        _value("F4", "Gross margin", "FY2025", "pct", 71.1),
        _value("F5", "Operating margin", "FY2025", "pct", 20.0),
        _value("F6", "Net margin", "FY2025", "pct", 21.2),
        _value("D1", "Gross margin change", "FY2025", "pp", -3.9, inputs=["F4", "F3"]),
        _value("D8", "SG&A % of revenue", "FY2025", "pct", 30.3),
    ]),
    "passages": [{"id": "P1", "text": "A one-off gain on the sale of a building."}],
    "red_flags": [],
}


def _output(*sentences: tuple[str, str]) -> dict[str, Any]:
    return {"sections": [{"key": "cash", "sentences": [{"type": kind, "text": text} for kind, text in sentences]}]}


@lru_cache(maxsize=None)
def _pack(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


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
    fixed, retyped = retype.retype(_output(("cause", text)), PACK)
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
    assert retype.explanatory(text) == word


BRIDGE = "The FY2025 gross-margin fall came from operating margin (-3.9pp), partly offset by net margin [D1][F5][F6]."
OMITTED = "Gross margin fell 3.9pp to 71.1% [D1]."  # NVDA's shape: 71.1% is F4, cited in the sentence before


def test_the_code_step_retypes_and_adds_no_id() -> None:
    """``first_pass`` is the retyping, then the gate with its backstops: the retyped bridge passes, and the omitted ID
    stays the gate's failure, with every sentence's text as the model wrote it."""
    first = _output(("fact", "Gross margin was 71.1% in FY2025 [F4]."), ("cause", BRIDGE), ("comparison", OMITTED))
    fixed, retyped, gate = retype.first_pass(first, PACK)
    assert [r["sentence"] for r in retyped] == [BRIDGE]
    assert [s["text"] for s in fixed["sections"][0]["sentences"]] == [s["text"] for s in first["sections"][0]["sentences"]]
    assert [(f["sentence"], f["failure"]) for f in gate["failures"]] == [(OMITTED, "'71.1%' matches nothing the sentence cites")]
    assert "backstop_failures" in gate and first["sections"][0]["sentences"][1]["type"] == "cause"  # its input unchanged


# Review 8, repair-loop [0] and [1], on CVX's committed packs: D369 is the FY2025 net margin change (-2.5pp) of F30
# (FY2025, 6.7%) and F29 (FY2024, 9.2%); F26 is FY2021's 10.0%. Auto-citation appended F30 to a from-level (whose
# level was 9.2%) and F26 to a current level (6.7%), and the gate passed each. With no ID added by code, each stays
# the gate's failure and goes to the repair, on both pack versions, so every arm alike.
CITED_ELSEWHERE = "Net margin was 6.7% in FY2025 [F30], 9.2% in FY2024 [F29] and 10.0% in FY2021 [F26]."
REVIEW_8_LEAKS = [
    ("Net margin fell 2.5pp in FY2025 from a net margin of 6.7% [D369].", "6.7%"),
    ("Net margin fell 2.5pp from net margin of 6.7% [D369].", "6.7%"),
    ("Net margin fell 2.5pp in FY2025, down from a net margin of 6.7% [D369].", "6.7%"),
    ("Net margin fell 2.5pp in FY2025 against a net margin of 6.7% a year earlier [D369].", "6.7%"),
    ("Net margin was 6.7% before it fell 2.5pp in FY2025 [D369].", "6.7%"),
    ("A net margin of 6.7% a year earlier fell 2.5pp in FY2025 [D369].", "6.7%"),
    ("Net margin has fallen to 10.0% since the end of FY2021 [D369].", "10.0%"),
    ("Net margin has fallen to 10.0% compared with FY2021 [D369].", "10.0%"),
    ("Net margin has fallen to 10.0% relative to FY2021 [D369].", "10.0%"),
    ("Net margin has fallen to 10.0% against FY2021 [D369].", "10.0%"),
    ("Net margin has fallen to 10.0% after FY2021 [D369].", "10.0%"),
    ("Net margin has fallen to 10.0% from its FY2021 level [D369].", "10.0%"),
]


@pytest.mark.parametrize("folder", ["packs", "packs-v2"])
@pytest.mark.parametrize("sentence, figure", REVIEW_8_LEAKS)
def test_review_8s_auto_citation_leaks_stay_gate_failures(folder: str, sentence: str, figure: str) -> None:
    first = _output(("comparison", sentence), ("fact", CITED_ELSEWHERE))
    fixed, retyped, gate = retype.first_pass(first, _pack(folder, "CVX"))
    assert fixed == first and retyped == []
    assert (sentence, f"'{figure}' matches nothing the sentence cites") in [(f["sentence"], f["failure"]) for f in gate["failures"]]


# The recorded own-ID omissions auto-citation fixed (DEEPSEEK-ERRORS.md "As built", fix 1), on their first passes'
# sentences and committed pack: each now goes to the repair, like the four it refused.
RECORDED_OMISSIONS = [
    ("NVDA", "", "Gross margin fell 3.9pp to 71.1% and drove the 2.0pp operating-margin decline, partly offset by R&D and "
     "SG&A leverage of 1.3pp and 0.6pp [D462][D463][D478][D479].", "71.1%"),  # eval-v1
    ("NVDA", "", "Gross margin fell 3.9pp to 71.1%, the main drag on operating margin, which slipped 2.0pp [D462][D463].",
     "71.1%"),  # dev-v4
    ("JPM", "The efficiency ratio was 52.4% in FY2025 [D207].", "Against seven bank peers the 52.4% efficiency ratio sits "
     "at the 0th percentile versus a 61.7% median, while return on average equity of 16.1% is at the 100th percentile "
     "against an 11.8% median [D336][D337][D213][D338][D339].", "52.4%"),  # dev-v4
]


@pytest.mark.parametrize("ticker, elsewhere, sentence, figure", RECORDED_OMISSIONS)
def test_a_recorded_own_id_omission_goes_to_the_repair(ticker: str, elsewhere: str, sentence: str, figure: str) -> None:
    first = _output(*([("fact", elsewhere)] if elsewhere else []), ("comparison", sentence))
    fixed, _, gate = retype.first_pass(first, _pack("packs", ticker))
    assert fixed == first and not gate["passed"]
    assert (sentence, f"'{figure}' matches nothing the sentence cites") in [(f["sentence"], f["failure"]) for f in gate["failures"]]


def test_the_code_only_replay_decides_through_the_code_step(tmp_path: Path) -> None:
    """``real_failures`` replays a recorded first pass through ``first_pass``: a bridge the retyping makes whole is no
    longer failing, an omitted ID still is, by the gate alone too."""
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "T.json").write_text(json.dumps(PACK))
    for ticker, first in (("A", _output(("cause", BRIDGE))),
                          ("B", _output(("fact", "Gross margin was 71.1% in FY2025 [F4]."), ("comparison", OMITTED)))):
        path = tmp_path / "runs" / "eval-v1" / "deepseek-flash" / f"{ticker}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ticker": "T", "output": first}))
    lines = retype.real_failures(tmp_path, ["eval-v1"], "deepseek-flash")
    assert lines[-1] == ("  first passes: 2; failing: 2; failing after retyping: 1; failing the gate alone: 2; "
                         "failing the gate alone after retyping: 1")
    assert f"    retyped: {BRIDGE}" in lines and f"    still: '71.1%' matches nothing the sentence cites | {OMITTED}" in lines


def test_retyping_never_loads_the_bootstrap() -> None:
    assert "evals.trend_depth.bootstrap" not in sys.modules
