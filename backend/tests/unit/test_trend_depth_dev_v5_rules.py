"""The gate, probe and retype rules from dev-v5's first-try failures (DEEPSEEK-ERRORS.md §2, "As built", round 2).

dev-v5's 116 first-try failures were read one by one: 10 were false positives of the gate, 63 were induced by a prompt
line, 43 were true errors. Seven rules came out of the false positives, each tested here on the committed packs, with
the recorded sentence that passes now and the false mirror that must fail (several of which passed before):

- G1 (``factcheck._direction``): a figure's own movement noun after it ("a 14.7% operating-income decline") overrides
  a direction word before it that belongs to another noun ("Rising debt alongside ..."); read only where such a word
  stands before, as "a 1.6pp gain" alone may be a gain in a lower-is-better ratio (eval-v1 Haiku CVX).
- G2 (``factcheck._direction``): a position against the year before right after a change ("3.3pp below the prior
  year") gives its direction.
- G3 (``probes._FALL_WORDS``): "collapse", "plummet" and "tumble" say a fall, so U1 spares the figure.
- G4(a) (``factcheck.bind_periods``): a from-level right after a bare "from", with no year written after it and bound
  to one year, may be that year's level or the year before's; not after a source verb ("came from") nor where "<year>
  <metric> fell from" already dated it.
- G4(b) (``factcheck.bind_periods``): a year followed by "and", "but", "while" or "whereas" binds no figure after it.
- G6 (``retype._FIGURE_TALK``): the words of a product's contribution to growth with no passage (REGN's REGEN-COV
  sentences) are figure talk, so such a "cause" is retyped as a comparison; "lift" stays out.
- G7 (``factcheck.line_moved``): a cost line's operating-margin effect said through the line's own move ("Cost of
  revenue fell 1.1pp", "lower SG&A adding 2.0pp") reads the inverse of the direction word.

G5 (a net-cash label between a level and its reference governs the reference) was left out as low priority: NEE's
P sentence (dev-v5-r2) still fails R2a. Pure: reads the committed packs, calls no model.
"""
from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import factcheck, retype

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"


@lru_cache(maxsize=None)
def _pack(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


def _failures(folder: str, ticker: str, text: str, kind: str = "comparison", backstops: bool = True) -> list[str]:
    sentence = {"section": "margins", "type": kind, "text": text}
    return [f["failure"] for f in factcheck.check([sentence], _pack(folder, ticker), backstops=backstops)["failures"]]


# Every recorded sentence the round-2 rules turn from failing to passing (``replay --base 17c5d4b`` and the round's own
# replay over every label), on the pack its arm reads, typed as recorded: 14 true sentences, of which 7 are dev-v5's.
RECORDED = [
    # G1: C's CAT (dev-v5-r1).
    ("packs-v2", "CAT", "judgement",
     "Rising debt alongside a 14.7% operating-income decline is the balance-sheet pressure to watch [R1][D464]."),
    # G2: C's COP (dev-v5-r1), a U1 hit before.
    ("packs-v2", "COP", "comparison",
     "The effective tax rate rose to 36.9% in FY2025 from 32.4% in FY2024, and net margin of 15.4% sat 3.3pp below the "
     "prior year [D332][D298][F30][D351]."),
    # G3: P's CAT (dev-v5-r2), a U1 hit before.
    ("packs-v2", "CAT", "comparison",
     "The path was cyclical rather than smooth: a 22.4% collapse in FY2020 to $41.7 billion [F5][D198] was followed by "
     "a 22.1% rebound in FY2021 [F6][D251]."),
    # G4(a): C's NEE (dev-v5-r2), Q's COST (dev-v5-r1); dev-v3 Haiku-low COST, Sonnet PG; eval-v1 Haiku-low JPM, USB.
    ("packs-v2", "NEE", "comparison",
     "The FY2025 bridge was flat, with operating margin up just 0.3pp as D&A rose to 25.5% of revenue from 23.2% "
     "[D247][D224][D189]."),
    ("packs", "COST", "fact",
     "Net cash reached $15,139 million, or 5.0% of revenue, in FY2026 from $9,496 million a year earlier "
     "[D427][D428][D378]."),
    ("packs", "COST", "fact",
     "FY2024 shareholder payouts reached 146.9% of free cash flow [D332] with dividends of $9.04 billion [X118], cutting "
     "net cash from $8.78 billion [D280] to $5.25 billion [D329]; the cited passages do not explain the FY2024 dividend."),
    ("packs", "PG", "fact",
     "FY2019 was the one break in the window: operating income fell to $5.5 billion from $13.4 billion and operating "
     "margin dropped 11.9pp to 8.1% [F13][F12][D109][F23]."),
    ("packs", "JPM", "cause",
     "The largest move was FY2021's margin rise from 24.3% [D90] to 39.7% [D114], as provisions fell to -7.6% of "
     "revenue [D112] on improved credit [P55]."),
    ("packs", "USB", "fact",
     "One FY2020 passage describes a provision decrease that conflicts with the filed rise from $1.50 billion to $3.81 "
     "billion [X139][X140], so I do not use it [P59]."),
    # G4(b): P's REGN (dev-v5-r1); dev-v3 Haiku-low REGN.
    ("packs-v2", "REGN", "comparison",
     "R&D reached 40.8% of revenue, the highest since FY2016 and far above the 20.1% peer median [D420][D779]."),
    ("packs", "REGN", "fact",
     "Buybacks of $3,438.6m [X137] and dividends of $370.3m [X140] took 93.3% of free cash flow [D437], with dividends "
     "starting in FY2025 after none in FY2024 [X139] and diluted shares down 5.6% [D459]."),
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
    # G2: the gate itself now reads the position, so each mirror fails without the backstops too.
    ("packs-v2", "COP", "Net margin of 15.4% sat 3.3pp above the prior year [F30][D351].", "other way"),
    ("packs-v2", "COP", "Net margin of 15.4% sat 3.3pp higher than the prior year [F30][D351].", "other way"),  # (passed before)
    ("packs-v2", "COP", "Net margin of 15.4% ran 3.3pp ahead of a year earlier [F30][D351].", "other way"),
    # G3: a rise word U1 does not know leaves the fall unsigned.
    ("packs-v2", "CAT", "The path was cyclical: a 22.4% rebound in FY2020 to $41.7 billion [F5][D198].", "backstop U1"),
    ("packs-v2", "CAT", "Revenue soared 22.4% in FY2020 to $41.7 billion [F5][D198].", "backstop U1"),
    # G4(a): a level two years back; a year written after the from-level dates it, a citation between them or not;
    # "came from" names a source; "<year> D&A rose from" already dated the level.
    ("packs-v2", "NEE", "In FY2025, D&A rose to 25.5% of revenue from 23.7% [D224][D154].", "not in the period(s) named (2024, 2025)"),
    ("packs-v2", "NEE", "D&A rose to 25.5% of revenue from 23.7% [D154] in FY2024 [D224].", "not in the period(s) named (2024)"),
    ("packs-v2", "NEE", "D&A rose to 25.5% of revenue from 23.7% in FY2024 [D224][D154].", "not in the period(s) named (2024)"),
    ("packs-v2", "NEE", "FY2025 D&A rose from 23.7% of revenue [D154].", "not in the period(s) named (2024)"),
    ("packs", "COST", "Net cash reached $15,139 million, or 5.0% of revenue, in FY2026 from $5,247 million a year earlier "
                      "[D427][D428][D329].", "not in the period(s) named (2025, 2026)"),
    ("packs", "ORCL", "The FY2026 gain came from 0.3pp of R&D [D397].", "not in the period(s) named (2026)"),
    # G4(b): the year still binds the figure before it.
    ("packs-v2", "REGN", "R&D reached 40.8% of revenue in FY2016 and far above the 20.1% peer median [D420][D779].",
     "not in the period(s) named (2016)"),
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
    # G1 is read only after a direction word: with none before, "a 1.6pp gain" is left to its magnitude (eval-v1 Haiku
    # CVX, whose cost-of-revenue share fell 1.6pp, a gain to the margin).
    ("packs", "CVX", "Cost of revenue fell 9.2% [D370], taking its share of revenue to 57.2% from 58.8% [D338][D296], a "
                     "1.6pp gain, as purchased crude and products fell [P14]."),
    # G2: each position and each way of naming the year before.
    ("packs-v2", "COP", "Net margin of 15.4% sat 3.3pp below the prior year [F30][D351]."),
    ("packs-v2", "COP", "Net margin of 15.4% sat 3.3pp under the previous year [F30][D351]."),
    ("packs-v2", "COP", "Net margin of 15.4% sat 3.3pp lower than a year earlier [F30][D351]."),
    ("packs-v2", "COP", "Net margin of 15.4% fell 3.3pp short of a year before [F30][D351]."),
    ("packs-v2", "COP", "Net margin of 15.4% was 3.3pp below a year ago [F30][D351]."),
    ("packs-v2", "COP", "Net margin of 15.4% was 3.3pp below the year before [F30][D351]."),
    ("packs-v2", "COP", "Net margin of 15.4% was 3.3pp below the preceding year [F30][D351]."),
    # G3: each fall word.
    ("packs-v2", "CAT", "Revenue collapsed 22.4% in FY2020 to $41.7 billion [F5][D198]."),
    ("packs-v2", "CAT", "Revenue plummeted 22.4% in FY2020 to $41.7 billion [F5][D198]."),
    ("packs-v2", "CAT", "Revenue tumbled 22.4% in FY2020 to $41.7 billion [F5][D198]."),
    # G4(a): "down from", and the level of the year before after a year opening the sentence.
    ("packs-v2", "NEE", "In FY2025 D&A rose to 25.5% of revenue, up from 23.2% [D224][D189]."),
    ("packs-v2", "NEE", "FY2025 D&A rose from 23.2% of revenue [D189]."),
    ("packs", "ORCL", "The FY2026 gain came from 1.9pp of R&D [D444]."),
    # G4(b): each conjunction after the year.
    ("packs-v2", "REGN", "R&D reached 40.8% of revenue, the highest since FY2016 but far above the 20.1% peer median [D420][D779]."),
    ("packs-v2", "REGN", "R&D reached 40.8% of revenue, the highest since FY2016 while far above the 20.1% peer median [D420][D779]."),
    ("packs-v2", "REGN", "R&D reached 40.8% of revenue, the highest since FY2016 whereas the 20.1% peer median sat far lower [D420][D779]."),
    # G7: the line as the subject, after "has", and as the qualified noun; the margin's own move.
    ("packs-v2", "SNAP", "Cost of revenue fell 1.1pp to 45.0% of revenue [D386][D431]."),
    ("packs-v2", "SNAP", "Cost of revenue has fallen 1.1pp to 45.0% of revenue [D386][D431]."),
    ("packs-v2", "SNAP", "Lower cost of revenue added 1.1pp to operating margin [D431]."),
    ("packs-v2", "SNAP", "Operating margin rose 1.1pp on cost of revenue [D431]."),
]


@pytest.mark.parametrize("folder, ticker, text", TRUE_FORMS)
def test_each_rule_s_true_forms_pass(folder: str, ticker: str, text: str) -> None:
    for backstops in (False, True):
        assert _failures(folder, ticker, text, backstops=backstops) == [], text


# --- G6: the retyping's figure talk ------------------------------------------------------------------------------------

def _retyped(folder: str, ticker: str, text: str) -> bool:
    output = {"sections": [{"key": "arc", "sentences": [{"type": "cause", "text": text}]}]}
    return bool(retype.retype(output, _pack(folder, ticker))[1])


# The six recorded REGEN-COV contribution sentences typed "cause" with no passage (dev-v5: K0, P, Q and C), retyped now.
REGEN_COV = [
    ("packs", "The FY2021 spike came from REGEN-COV, whose US sales of $5,828.0 million contributed 66.4pp of that year's "
              "growth [S48][D582]."),
    ("packs-v2", "The FY2021 spike came from REGEN-COV, which contributed 66.4pp of growth and 36.3% of revenue that year "
                 "[D582][D580], before collapsing to zero in FY2022 [S49]."),
    ("packs", "The FY2021 spike came from REGEN-COV, which contributed 66.4pp of that year's growth, and its "
              "disappearance drove the FY2022 reversal [D582][D585]."),
    ("packs-v2", "The FY2021 spike came from REGEN-COV, which contributed 66.4pp of growth and 36.3% of revenue, before "
                 "falling to zero in FY2022 [D582][D580][S49][D585]."),
    ("packs-v2", "The FY2021 surge came from REGEN-COV, which contributed 66.4pp of the 89.1% growth on $5,828.0 million "
                 "of US sales [D582][D241][S48]."),
    # Variants for the forms of "collapse" no record holds.
    ("packs-v2", "The FY2021 spike came from REGEN-COV, which contributed 66.4pp of growth [D582], before a collapse to "
                 "zero in FY2022 [S49]."),
    ("packs-v2", "The FY2021 spike came from REGEN-COV, which contributed 66.4pp of growth [D582] and collapsed to zero "
                 "in FY2022 [S49]."),
]
# Causes that stay causes: an explanatory "as", and "lifting", which says more than the figures (REGN's receivables
# fell, so days sales outstanding fell: dev-v5 Q's sentence is wrong, and the repair is right).
STILL_CAUSES = [
    ("packs", "REGN", "The FY2021 spike came from REGEN-COV, whose U.S. sales of $5,828.0m contributed 66.4pp of that "
                      "year's growth [S48][D582], and the FY2022 reversal followed as those sales fell to zero [S49][D585]."),
    ("packs", "REGN", "Receivables fell 7.6% to $5,741.1m, lifting days sales outstanding to 146 [X197][D462][D438], "
                      "while stock-based compensation of $993.7m was 20.0% of operating cash flow [X77][D431]."),
    ("packs", "REGN", "Receivables fell 7.6%, lifting conversion, while stock-based compensation of $993.7 million "
                      "remained 20.0% of operating cash flow [X197][D462][X77][D431]."),
    ("packs-v2", "JPM", "Net interest income drove that step, rising 33.8% in FY2023 to $89.3 billion, as higher rates "
                        "lifted interest income to $171 billion [D174][F8][X125]."),
]
_ROUND_2_TALK = "spike surge reversal collapse collapsed collapsing zero disappearance whose s sale".split()


@pytest.mark.parametrize("folder, text", REGEN_COV)
def test_a_contribution_with_no_passage_is_retyped(folder: str, text: str) -> None:
    assert _retyped(folder, "REGN", text)


@pytest.mark.parametrize("folder, ticker, text", STILL_CAUSES)
def test_an_explained_move_stays_a_cause(folder: str, ticker: str, text: str) -> None:
    assert not _retyped(folder, ticker, text)
    assert "lift" not in retype._FIGURE_TALK and "lifting" not in retype._FIGURE_TALK


@pytest.mark.parametrize("word", _ROUND_2_TALK)
def test_each_round_2_figure_word_is_needed(word: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert word in retype._FIGURE_TALK
    monkeypatch.setattr(retype, "_FIGURE_TALK", retype._FIGURE_TALK - {word})
    assert not all(_retyped(folder, "REGN", text) for folder, text in REGEN_COV), word
