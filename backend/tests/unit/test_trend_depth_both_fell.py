"""``factcheck.both_fell``'s cost-growth term on the committed packs (review 9, tests-and-gates [1]; DEEPSEEK-ERRORS.md
fix 7).

A standing of a line named without "growth" ("operating costs outpaced revenue by 1.8pp") is read with certainty only in
a year the pack shows the two lines did not both fall. In a year both fell it is read by magnitude, as "outpaced" then
does not say which fell further. ``test_trend_depth_factcheck.py`` pins ``both_fell`` only on years revenue fell more
than costs (CVX, DE and TGT in FY2025) and on years revenue grew, where the cost-growth term never changes the answer:
a sign error in it (``growth + gap`` for ``growth - gap``) or its loss (``growth < 0`` alone) passed every test. These
pin the years on both pack versions (22 of 144 each), the gate's verdict in a year costs fell more (the true sentence
and its mirror both read by magnitude) and in a year revenue fell while costs rose (the true sentence passes, its
mirror fails), each on the committed pack. ``factcheck`` is pure, so it is imported directly.
"""
from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import factcheck

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
GAP = "Revenue growth minus operating-cost growth"
# Every committed gap whose revenue (its first two inputs) and cost growth (revenue growth less the gap) both fell,
# the same in both pack versions. Costs fell more in AMD D398, CAT D171 and D436, DE D208, DUK D301, KO D68, D119 and
# D221, NEE D82, ORCL D166 and TGT D346; revenue fell more in the other eleven.
BOTH_FELL = {
    "AMD": ["D398"], "CAT": ["D171", "D224", "D436"], "CVX": ["D135", "D171", "D295", "D379"],
    "DE": ["D208", "D389", "D431"], "DUK": ["D177", "D301"], "KO": ["D68", "D119", "D221"], "NEE": ["D82", "D222"],
    "ORCL": ["D166"], "TGT": ["D346", "D392", "D439"],
}
VERSIONS = ("packs", "packs-v2")


@lru_cache(maxsize=None)
def _pack(folder: str, ticker: str) -> dict[str, Any]:
    return json.loads(gzip.decompress((RECORDS / folder / f"{ticker}.json.gz").read_bytes()))


@pytest.mark.parametrize("folder", VERSIONS)
def test_both_lines_fell_in_exactly_these_years(folder: str) -> None:
    fell, gaps = {}, 0
    for path in sorted((RECORDS / folder).glob("*.json.gz")):
        ticker = path.name.split(".")[0]
        values = _pack(folder, ticker)["values"]
        for vid, value in values.items():
            if value["label"] == GAP:
                gaps += 1
                if factcheck.both_fell(value, values):
                    fell.setdefault(ticker, []).append(vid)
    assert gaps == 144 and {t: sorted(ids, key=lambda i: int(i[1:])) for t, ids in fell.items()} == BOTH_FELL


def _verdict(folder: str, ticker: str, text: str) -> tuple[list[str], str, str]:
    result = factcheck.check_sentence({"text": text, "type": "comparison"}, _pack(folder, ticker))
    (claim,) = result.claims
    return result.failures, claim["status"], claim["matched"]


# Both lines fell and costs fell further (revenue, cost growth, gap): TGT FY2023 -1.57%, -3.39%, +1.82pp; AMD FY2023
# -3.90%, -54.97%, +51.06pp; KO FY2018 -5.28%, -11.63%, +6.35pp; ORCL FY2020 -1.11%, -3.08%, +1.97pp.
COSTS_FELL_MORE = [
    ("TGT", "D346", "FY2023", "1.8pp"), ("AMD", "D398", "FY2023", "51.1pp"), ("KO", "D119", "FY2018", "6.3pp"),
    ("ORCL", "D166", "FY2020", "2.0pp"),
]


@pytest.mark.parametrize("folder", VERSIONS)
@pytest.mark.parametrize("ticker, gap, year, figure", COSTS_FELL_MORE)
def test_a_standing_in_a_year_costs_fell_further_is_read_by_magnitude(folder: str, ticker: str, gap: str, year: str,
                                                                     figure: str) -> None:
    # With the cost term's sign flipped, both_fell reads these years as not both falling, and the true sentence (costs
    # did fall further) fails as "matches reversed ... but the sentence says it went the other way", a repair message
    # pushing the model to the mirror.
    assert factcheck.both_fell(_pack(folder, ticker)["values"][gap], _pack(folder, ticker)["values"])
    for text in (f"Operating costs outpaced revenue by {figure} in {year} [{gap}].",
                 f"Revenue outpaced operating costs by {figure} in {year} [{gap}]."):
        assert _verdict(folder, ticker, text) == ([], "verified", "cited")


@pytest.mark.parametrize("folder", VERSIONS)
def test_a_standing_in_a_year_revenue_fell_and_costs_rose_is_read_with_certainty(folder: str) -> None:
    # REGN FY2018: revenue -12.37%, cost growth +10.12%, gap D116 -22.49pp. Not both fell, so the standing is certain:
    # the true sentence passes as the gap read the other way, its mirror fails. With the cost term dropped
    # (``growth < 0`` alone), both_fell says both fell, the mirror is read by magnitude and passes.
    values = _pack(folder, "REGN")["values"]
    assert factcheck.both_fell(values["D116"], values) is False
    assert _verdict(folder, "REGN", "Operating costs outpaced revenue by 22.5pp in FY2018 [D116].") == (
        [], "verified", "reversed D116")
    failures, status, _ = _verdict(folder, "REGN", "Revenue outpaced operating costs by 22.5pp in FY2018 [D116].")
    assert status == "direction_mismatch" and failures == [
        "'22.5pp' matches cited = -22.49 but the sentence says it went the other way"]
