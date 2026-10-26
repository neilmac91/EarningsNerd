"""The gate rules round 2 kept from dev-v5's first-try failures (DEEPSEEK-ERRORS.md §2, "As built", round 2).

dev-v5's 116 first-try failures were read one by one: 10 were false positives of the gate, 63 were induced by a prompt
line, 43 were true errors. Seven rules came out of the false positives. Verified against 17c5d4b, five were withdrawn
(G2, G3, G4(a), G4(b) and G6: each passed false sentences 17c5d4b caught or failed true ones it passed) and two stay,
each tested here on the committed packs:

- G1 (``factcheck._direction``): a figure's own movement noun after it ("a 14.7% operating-income decline") overrides
  a direction word before it that belongs to another noun ("Rising debt alongside ..."); read only where such a word
  stands before, as "a 1.6pp gain" alone may be a gain in a lower-is-better ratio (eval-v1 Haiku CVX); only for a
  percentage, as a pp figure may be a cost line's share move cited as the margin's change ("Gross margin improved with
  a 0.6pp decline in the cost-of-revenue share": verification found the first build failing it); only after "a" or
  "an"; and only when no stop word ("despite", "in", ...) stands between the figure and the noun.
- G7 (``factcheck.line_moved``): a cost line's operating-margin effect said through the line's own move ("Cost of
  revenue fell 1.1pp", "lower SG&A adding 2.0pp") reads the inverse of the direction word; only in the figure's own
  clause.

Each rule has its recorded sentences, its false mirrors and a true sentence for each word it reads; each guard has a
true sentence and a false mirror whose verdicts flip when the guard is taken out (``GUARDS``). Pure: reads the
committed packs, calls no model.
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import factcheck

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"


@lru_cache(maxsize=None)
def _pack(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


def _failures(folder: str, ticker: str, text: str, kind: str = "comparison", backstops: bool = True) -> list[str]:
    sentence = {"section": "margins", "type": kind, "text": text}
    return [f["failure"] for f in factcheck.check([sentence], _pack(folder, ticker), backstops=backstops)["failures"]]


# Every recorded sentence the kept rules turn from failing to passing (the replay against 17c5d4b over every label,
# finals and first passes), on the pack its arm reads, typed as recorded: 4 true sentences, 2 of them dev-v5's.
RECORDED = [
    # G1: C's CAT (dev-v5-r1).
    ("packs-v2", "CAT", "judgement",
     "Rising debt alongside a 14.7% operating-income decline is the balance-sheet pressure to watch [R1][D464]."),
    # G7: P's SNAP (dev-v5-r1); dev-v3 Sonnet REGN; eval-v1 Haiku-low ORCL.
    ("packs-v2", "SNAP", "comparison",
     "Cost of revenue fell 1.1pp to 45.0% of revenue and R&D 1.3pp to 30.2%, while other lines added 3.3pp, taking the "
     "margin up 5.7pp [D386][D431][D387][D432][D433][D419]."),
    ("packs", "REGN", "fact", "The FY2025 margin fell 3.2pp, with R&D costing 4.7pp and lower SG&A adding 2.0pp [D453][D465][D466]."),
    ("packs", "ORCL", "cause",
     "In FY2026 lower R&D intensity added 1.9pp to margin [D444], while other cost lines took 2.1pp [D445], mainly from "
     "higher cloud infrastructure costs [P19]."),
]


@pytest.mark.parametrize("folder, ticker, kind, text", RECORDED)
def test_the_recorded_true_sentences_pass(folder: str, ticker: str, kind: str, text: str) -> None:
    for backstops in (False, True):
        assert _failures(folder, ticker, text, kind, backstops) == [], (ticker, text)


# Each rule's false mirrors, with the failure each must keep. "(passed before)" marks a mirror the gate let through
# before the rule: the rule closes both directions.
MIRRORS = [
    # G1
    ("packs-v2", "CAT", "Rising debt alongside a 14.7% operating-income rise is the pressure to watch [R1][D464].", "other way"),
    ("packs-v2", "CAT", "Falling debt alongside a 14.7% operating-income rise is the pressure to watch [R1][D464].",
     "other way"),  # (passed before)
    ("packs-v2", "CAT", "Rising debt alongside a 14.7% gain in operating income is the pressure to watch [R1][D464].", "other way"),
    ("packs-v2", "CAT", "Operating income rose 14.7% in FY2025 [D464].", "other way"),
    # G1 is read only after a direction word: with none before, "a 22.4% rebound" (CAT's revenue fell 22.4% in FY2020)
    # is not read as a rise, and U1 still flags the unsigned fall.
    ("packs-v2", "CAT", "The path was cyclical: a 22.4% rebound in FY2020 to $41.7 billion [F5][D198].", "backstop U1"),
    # G7
    ("packs-v2", "SNAP", "Cost of revenue rose 1.1pp to 45.0% of revenue [D386][D431].", "other way"),  # (passed before)
    ("packs-v2", "SNAP", "Higher cost of revenue added 1.1pp to operating margin [D431].", "other way"),  # (passed before)
    ("packs-v2", "SNAP", "Operating margin fell 1.1pp on cost of revenue [D431].", "other way"),
    ("packs", "REGN", "The FY2025 margin fell 3.2pp, with higher SG&A adding 2.0pp [D453][D466].", "other way"),  # (passed before)
    ("packs", "ORCL", "In FY2026 higher R&D intensity added 1.9pp to margin [D444].", "other way"),  # (passed before)
]


@pytest.mark.parametrize("folder, ticker, text, failure", MIRRORS)
def test_each_rule_s_false_mirror_fails(folder: str, ticker: str, text: str, failure: str) -> None:
    found = _failures(folder, ticker, text)
    assert any(failure in f for f in found), (text, found)
    if not failure.startswith("backstop"):
        assert _failures(folder, ticker, text, backstops=False) == found, text


# Each word of each rule, in a true sentence.
TRUE_FORMS = [
    # G1: the figure's own noun, each one read.
    ("packs-v2", "CAT", "Rising debt alongside a 14.7% fall in operating income is the pressure to watch [R1][D464]."),
    ("packs-v2", "CAT", "Rising debt alongside a 14.7% drop in operating income is the pressure to watch [R1][D464]."),
    ("packs-v2", "CAT", "Higher debt came with a 14.7% operating-income contraction [R1][D464]."),
    ("packs-v2", "CAT", "Rising debt alongside a further 14.7% decline in operating income is the pressure [R1][D464]."),
    # The noun is read after an evaluative word too (the verification's; 17c5d4b failed it).
    ("packs", "AMD", "Improving gross margin accompanied a 68.3% operating-income slump in FY2023 [D371]."),
    # G1 is read only after a direction word, and only for a percentage: "a 1.6pp gain" is left to its magnitude
    # (eval-v1 Haiku CVX, whose cost-of-revenue share fell 1.6pp, a gain to the margin).
    ("packs", "CVX", "Cost of revenue fell 9.2% [D370], taking its share of revenue to 57.2% from 58.8% [D338][D296], a "
                     "1.6pp gain, as purchased crude and products fell [P14]."),
    # G7: the line as the subject, after "has", and as the qualified noun; the margin's own move, and the margin's gain
    # with the line named after it.
    ("packs-v2", "SNAP", "Cost of revenue fell 1.1pp to 45.0% of revenue [D386][D431]."),
    ("packs-v2", "SNAP", "Cost of revenue has fallen 1.1pp to 45.0% of revenue [D386][D431]."),
    ("packs-v2", "SNAP", "Lower cost of revenue added 1.1pp to operating margin [D431]."),
    ("packs-v2", "SNAP", "Operating margin rose 1.1pp on cost of revenue [D431]."),
    ("packs", "ORCL", "The FY2026 gain came from 1.9pp of R&D [D444]."),
]


@pytest.mark.parametrize("folder, ticker, text", TRUE_FORMS)
def test_each_rule_s_true_forms_pass(folder: str, ticker: str, text: str) -> None:
    for backstops in (False, True):
        assert _failures(folder, ticker, text, backstops=backstops) == [], text


# --- Each guard, pinned ------------------------------------------------------------------------------------------------
#
# For each guard the verification found no test of, a true sentence that passes only with the guard in and a false
# mirror that fails only with it, and the same for the percentage guard this round added after verification. The
# article, stop-word, percentage and clause-split sentences keep 17c5d4b's verdicts; the "gain" pair are G1's own
# (17c5d4b failed the true one and passed the mirror). CAT's FY2025: operating income -14.7% (D464),
# free cash flow -11.2% after -11.0% in FY2024 (D469), revenue +4.3% (D463), debt +14.1%; MSFT's FY2026: operating
# income +20.8% (D473), free cash flow -6.5%; SNAP's FY2025: cost of revenue's share fell to 45.0% (D386), +1.1pp to the
# margin (D431).
GUARDS = [
    # G1's article guard: with no "a" or "an" before the figure, a noun after it is another's ("revenue gains").
    ("article", "packs-v2", "CAT", True, "Operating income fell 14.7% versus revenue gains of 4.3% in FY2025 [D464][D463]."),
    ("article", "packs-v2", "CAT", False, "Operating income rose 14.7% versus revenue declines in FY2025 [D464]."),
    # G1's stop words: a noun after "despite" (or "in", "of", ...) is not the figure's.
    ("stop words", "packs-v2", "CAT", True,
     "Free cash flow fell a further 11.2% despite revenue gains of 4.3% in FY2025 [D469][D463]."),
    ("stop words", "packs-v2", "CAT", False, "Free cash flow rose a further 11.2% despite revenue declines in FY2025 [D469]."),
    # G1's noun "gain".
    ("gain", "packs-v2", "MSFT", True, "Free cash flow fell alongside a 20.8% operating-income gain in FY2026 [D473]."),
    ("gain", "packs-v2", "CAT", False, "Falling debt alongside a 14.7% operating-income gain is the pressure to watch [R1][D464]."),
    # G1 reads only a percentage's noun: a pp figure may be the cost-of-revenue share's fall cited as the margin's gain
    # (KO's FY2025, +0.6pp: the gross-margin change D462, the operating-margin effect D475). The first two are the
    # verification's, which the first build failed; the third is a bridge sentence of the form the candidate asks for.
    ("percentage", "packs-v2", "KO", True,
     "Gross margin improved with a 0.6pp decline in the cost-of-revenue share in FY2025 [D475]."),
    ("percentage", "packs-v2", "KO", True, "Gross margin improved with a 0.6pp decline in the cost-of-revenue share in FY2025 [D462]."),
    ("percentage", "packs-v2", "KO", True, "Operating margin widened with a 0.6pp drop in the cost-of-revenue share in FY2025 [D475]."),
    ("percentage", "packs-v2", "KO", False, "Operating margin narrowed with a 0.6pp rise in the cost-of-revenue share in FY2025 [D475]."),
    # G7's clause split: the line's move in an earlier clause does not turn the margin's.
    ("clause split", "packs-v2", "SNAP", True, "Cost of revenue fell to 45.0%, and operating margin rose 1.1pp on it [D386][D431]."),
    ("clause split", "packs-v2", "SNAP", False, "Cost of revenue fell to 45.0%, but operating margin fell 1.1pp on it [D386][D431]."),
    ("clause split", "packs-v2", "SNAP", True, "Cost of revenue fell to 45.0% and operating margin rose 1.1pp on it [D386][D431]."),
    ("clause split", "packs-v2", "SNAP", False, "Cost of revenue fell to 45.0% while operating margin fell 1.1pp on it [D386][D431]."),
]


def _without(guard: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Take one guard out of the gate."""
    if guard == "article":
        monkeypatch.setattr(factcheck, "_ARTICLE_BEFORE", re.compile(r"$"))
        return
    if guard == "percentage":
        monkeypatch.setattr(factcheck, "_NOUN_UNITS", ("pct", "pp"))
        return
    if guard == "clause split":
        monkeypatch.setattr(factcheck, "_CLAUSE_BEFORE", re.compile(r"(?!)"))
        return
    pattern = factcheck._OWN_NOUN.pattern
    old = {"stop words": f"(?!{factcheck._NOUN_STOP}\\b)", "gain": "gains?|"}[guard]
    assert pattern.count(old) == 1, guard
    monkeypatch.setattr(factcheck, "_OWN_NOUN", re.compile(pattern.replace(old, ""), re.I))


@pytest.mark.parametrize("guard, folder, ticker, true, text", GUARDS)
def test_each_guard_decides_its_sentences(guard: str, folder: str, ticker: str, true: bool, text: str,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    for backstops in (False, True):
        found = _failures(folder, ticker, text, backstops=backstops)
        assert found == [] if true else any("other way" in f for f in found), (text, found)
    _without(guard, monkeypatch)
    for backstops in (False, True):
        found = _failures(folder, ticker, text, backstops=backstops)
        assert any("other way" in f for f in found) if true else found == [], (guard, text, found)
