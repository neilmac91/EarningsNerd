"""The candidate prompt's examples copy no evaluation company's figures (DEEPSEEK-ERRORS.md §3 step 0.4), its section
rules agree with its sentence budget, and its drivers comparison is a form the gate reads the gap's sign in on every
committed pack (each below the examples' tests).

Every arm on the candidate prompt reads its examples in every request, so an example that is one of the 20
companies' gate-passing sentences hands that company's figures and IDs to those arms and skews its results. The test
reads every quoted or code example of ``backend/prompts/trends-depth-analyst-agent.md``, paragraph by paragraph (a
list item is a paragraph), and fails when, in any committed pack (``packs/`` and ``packs-v2/``):

- an ID an example cites holds a value that prints as one of its paragraph's figures (REGN's
  "Revenue rose 1.0% to $14.3 billion in FY2025 [F10][D440]": F10 is $14.3 billion and D440 1.0%); or
- one year's values print as every figure of a paragraph that has two or more (REGN's FY2025 revenue, capital
  expenditure and operating-margin change: "$14.3 billion", "$898 million", "fell 3.2pp").

A lone figure is not checked by value: at the prompt's printing precision almost every percentage is some value of
some pack, so only a figure set or a cited ID makes an example a company's own. The frozen prompt is archived and
never edited, so only the candidate is checked.
"""
from __future__ import annotations

import gzip
import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth import factcheck, retype
from evals.trend_depth.factcheck import Claim

BACKEND = Path(__file__).resolve().parents[2]
CANDIDATE = BACKEND / "prompts" / "trends-depth-analyst-agent.md"
RECORDS = BACKEND.parent / "tasks" / "analysis-depth-2026-10"
FOLDERS = ("packs", "packs-v2")
_EXAMPLE = re.compile(r'"([^"]*)"|`([^`]*)`')  # an example may wrap onto the next line
_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")
REGN_EXAMPLES = """
- Put the ID of every figure you state in square brackets, for example `Revenue rose 1.0% to $14.3 billion in FY2025 [F10][D440].`
- Rounding: dollars to three significant figures ("$14.3 billion", "$898 million"). A margin change is in
  percentage points ("fell 3.2pp"), never per cent.
"""


def paragraphs(text: str) -> list[str]:
    """The prompt's paragraphs, each list item its own."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        current: list[str] = []
        for line in block.splitlines():
            if _ITEM.match(line) and current:
                out.append("\n".join(current))
                current = []
            current.append(line)
        if current:
            out.append("\n".join(current))
    return out


def examples(paragraph: str) -> tuple[list[Claim], list[str]]:
    """The figures and the cited IDs of a paragraph's quoted and code examples."""
    figures: list[Claim] = []
    ids: list[str] = []
    for quoted in _EXAMPLE.finditer(paragraph):
        example = " ".join((quoted.group(1) if quoted.group(1) is not None else quoted.group(2)).split())
        figures += [c for c in factcheck.parse_claims(example) if c.unit not in ("plain", "count", "multiple")]
        ids += retype.citations(example)
    return figures, ids


def prints_as(figure: Claim, value: dict[str, Any]) -> bool:
    """``value`` printed at the figure's unit and precision is the figure (by magnitude, as the gate compares)."""
    return (figure.unit == factcheck._value_unit(value["unit"])
            and abs(abs(value["value"]) - abs(figure.value * figure.scale)) <= factcheck._tolerance(figure))


@lru_cache(maxsize=None)
def committed_packs() -> tuple[tuple[str, dict[str, Any]], ...]:
    return tuple((f"{folder}/{path.name.split('.')[0]}", json.loads(gzip.decompress(path.read_bytes())))
                 for folder in FOLDERS for path in sorted((RECORDS / folder).glob("*.json.gz")))


def copied(text: str) -> list[str]:
    """Each way an example of ``text`` matches a committed pack (module docstring)."""
    found = []
    for paragraph in paragraphs(text):
        figures, ids = examples(paragraph)
        if not figures:
            continue
        for name, pack in committed_packs():
            values = pack["values"]
            found += [f"{name}: [{vid}] = {values[vid]['label']}, {values[vid]['period']} prints as '{figure.text}'"
                      for vid in dict.fromkeys(ids) if vid in values for figure in figures if prints_as(figure, values[vid])]
            if len(figures) < 2:
                continue
            by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for value in values.values():
                years = factcheck._periods_of(value)
                if len(years) == 1:
                    by_year[years[0]].append(value)
            found += [f"{name}: FY{year} values print as every figure of {[f.text for f in figures]}"
                      for year, held in sorted(by_year.items())
                      if all(any(prints_as(figure, value) for value in held) for figure in figures)]
    return found


def test_the_committed_packs_are_there() -> None:
    assert len(committed_packs()) == 40


def test_the_candidate_prompts_examples_copy_no_evaluation_company() -> None:
    text = CANDIDATE.read_text()
    assert sum(len(examples(p)[0]) for p in paragraphs(text)) >= 8  # the examples are read, not skipped
    assert copied(text) == []


def test_regn_s_old_examples_are_caught() -> None:
    found = copied(REGN_EXAMPLES)
    assert any("packs/REGN: [F10]" in line and "'$14.3 billion'" in line for line in found)
    assert any("packs/REGN: [D440]" in line and "'1.0%'" in line for line in found)
    assert any(line.startswith("packs/REGN: FY2025 values print as every figure of ['$14.3 billion', '$898 million', '3.2pp']")
               for line in found)


# --- The sentence budget: every section's own count agrees with the Style line --------------------------------------
#
# DeepSeek takes a section's own count over the Style line's (eval-v1: 12 of 20 arcs had five sentences under "Three to
# five" against "the arc 3 to 4") and fills each maximum, so a section that allows more than the budget breaks the
# 30-sentence cap and §3's form target in the candidate's arms (5 + 5 + 4 + 4 + 4 + 6 + 3 = 31).

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
_BUDGET_NAMES = {"the arc": "arc", "drivers": "drivers", "margins": "margins", "cash": "cash",
                 "balance sheet": "balance_sheet", "red flags": "red_flags", "watch": "watch"}


def _number(word: str) -> int:
    return int(word) if word.isdigit() else _WORDS[word.lower()]


def style_budget(text: str) -> tuple[int, dict[str, tuple[int, int]]]:
    """The Style line's cap and each section's range: "At most 30 sentences: the arc 3 to 4, drivers 4 to 5, ..."."""
    found = re.search(r"At most (\d+) sentences: ([^.]*)\.", " ".join(text.split()))
    assert found, "the Style line's sentence budget is not where the test reads it"
    ranges = {}
    for item in found.group(2).split(", "):
        name, low, high = re.fullmatch(r"(.+?) (\d+) to (\d+)", item).groups()
        ranges[_BUDGET_NAMES[name]] = (int(low), int(high))
    return int(found.group(1)), ranges


def section_rules(text: str) -> dict[str, str]:
    """Each numbered section's rule by its key ("1. `arc` — ..." up to the next section)."""
    body = re.split(r"\s## ", " ".join(text.split("## Sections", 1)[1].split()), maxsplit=1)[0]
    parts = re.split(r"(?:^|\s)\d\. `(\w+)` — ", body)
    return dict(zip(parts[1::2], parts[2::2]))


def stated_count(rule: str) -> tuple[int, int] | None:
    """The sentence count a section's own rule states, or None: "Three or four sentences"; "Two or three items, one
    sentence each"; red flags' "Up to three" flags at "(two sentences a flag)", or "in one sentence" when none apply."""
    flags = re.search(r"\bUp to (\w+)\b", rule)
    if flags:
        per_flag = re.search(r"\((\w+) sentences a flag\)", rule)
        none = re.search(r"If none apply, say in (\w+) sentences?\b", rule)
        assert per_flag and none, f"a red-flag rule the test cannot read: {rule[:80]}"
        return (min(_number(none.group(1)), _number(per_flag.group(1))),
                _number(flags.group(1)) * _number(per_flag.group(1)))
    items = re.search(r"\b(\w+) (?:or|to) (\w+) items, (\w+) sentences? each\b", rule)
    if items:
        each = _number(items.group(3))
        return _number(items.group(1)) * each, _number(items.group(2)) * each
    sentences = re.search(r"\b(\w+) (?:or|to) (\w+) sentences\b", rule)
    if sentences:
        return _number(sentences.group(1)), _number(sentences.group(2))
    return None


def budget_disagreements(text: str) -> list[str]:
    """Each way the prompt's section rules and its Style budget disagree, or its maxima exceed its cap."""
    cap, budget = style_budget(text)
    rules = section_rules(text)
    found = [] if set(rules) == set(budget) else [f"sections {sorted(rules)} against the budget's {sorted(budget)}"]
    for key, rule in rules.items():
        count = stated_count(rule)
        if count is None and re.search(rf"\b(?:{'|'.join(_WORDS)}|\d+)\b[^.;:]{{0,40}}?\b(?:sentences?|items?)\b", rule, re.I):
            found.append(f"{key}: a count the test cannot read")
        elif count is not None and count != budget.get(key):
            found.append(f"{key}: the section says {count[0]} to {count[1]}, the Style budget {budget.get(key)}")
    if sum(high for _, high in budget.values()) > cap:
        found.append(f"the budget's maxima sum to {sum(high for _, high in budget.values())}, over the cap of {cap}")
    return found


def test_the_candidates_section_counts_agree_with_its_sentence_budget() -> None:
    text = CANDIDATE.read_text()
    assert {key for key, rule in section_rules(text).items() if stated_count(rule)} == {"arc", "red_flags", "watch"}
    assert budget_disagreements(text) == []


@pytest.mark.parametrize("old, new, found", [
    # The arc's five sentences against the budget's four: 31 at every maximum.
    ("The arc\". Three or four sentences.", "The arc\". Three to five sentences.",
     ["arc: the section says 3 to 5, the Style budget (3, 4)"]),
    # A red-flag section with none triggered is one sentence; a budget minimum of two disagrees.
    ("red flags 1 to 6", "red flags 2 to 6", ["red_flags: the section says 1 to 6, the Style budget (2, 6)"]),
    ("the arc 3 to 4", "the arc 3 to 5", ["arc: the section says 3 to 4, the Style budget (3, 5)",
                                          "the budget's maxima sum to 31, over the cap of 30"]),
    ("Two or three items, one sentence each.", "Two or three items, two sentences each.",
     ["watch: the section says 4 to 6, the Style budget (2, 3)"]),
])
def test_a_section_count_against_the_budget_is_caught(old: str, new: str, found: list[str]) -> None:
    text = CANDIDATE.read_text()
    assert old in " ".join(text.split())
    assert budget_disagreements(" ".join(text.split()).replace(old, new)) == found


# --- The drivers comparison: one form, read with certainty on every committed pack ----------------------------------
#
# The candidate asks Q and C to compare operating-cost growth with revenue growth in one form, citing the pack's
# "revenue growth minus operating-cost growth" value (review 9: 09a5b1a asked for both growths' figures, which PG, COST,
# KO and TGT do not carry, so the true sentence failed the gate there and a cost-of-revenue figure under the costs' name
# passed). The form must be one the gate reads the gap's sign in with certainty (factcheck.compared_sides, a move), so on
# every pack and every year with that value its true sentence passes and its mirror fails, with and without the
# backstops; so must the form with the pack's operating-cost growth added, and with both growths, whose unsigned
# difference is the same quantity.
_DRIVERS_FORM = re.compile(r'"operating costs (grew|fell) (\d+\.\d)pp (faster|slower|less|more) than revenue"\s*'
                           r'\(or "(faster|slower|less|more)"\)')
_FLIP = {"faster": "slower", "slower": "faster", "less": "more", "more": "less"}


def drivers_forms(text: str) -> dict[str, tuple[str, str]]:
    """The candidate's drivers comparison, by verb: (the comparative when operating costs grew more than revenue, or
    fell less; the other)."""
    rule = " ".join(section_rules(text)["drivers"].split())
    found = {verb: (ahead, other) for verb, _, ahead, other in _DRIVERS_FORM.findall(rule)}
    assert all(_FLIP[ahead] == other for ahead, other in found.values()), found
    return found


def drivers_sentences(pack: dict[str, Any], forms: dict[str, tuple[str, str]]) -> list[tuple[str, str, str]]:
    """(year, true sentence, its mirror) in the candidate's form for each year the pack gives the gap, and with the
    pack's operating-cost growth and revenue growth added where it gives both. A gap that prints as 0.0pp has no sign."""
    keys, values = pack["series_keys"], pack["values"]
    out = []
    for key, gap_id in sorted(keys.items()):
        if not key.startswith("operating_leverage_gap|"):
            continue
        year = key.split("|")[1]
        gap = values[gap_id]["value"]
        if f"{abs(gap):.1f}" == "0.0":
            continue
        revenue_id, cost_id = keys[f"g:revenue|{year}"], keys.get(f"g:operating_expenses|{year}")
        revenue = values[revenue_id]["value"]
        verb = "grew" if revenue - gap >= 0 else "fell"  # operating-cost growth is revenue growth less the gap
        ahead, other = forms[verb]
        said = ahead if gap < 0 else other  # costs ahead of revenue when revenue growth minus cost growth is negative
        base = f"Operating costs {verb} {abs(gap):.1f}pp {{}} than revenue in {year}"
        templates = [f"{base} [{gap_id}]."]
        if cost_id:
            cost = values[cost_id]["value"]
            templates += [f"{base}, at {abs(cost):.1f}% [{gap_id}][{cost_id}].",
                          f"{base}, {abs(cost):.1f}% against {abs(revenue):.1f}% [{gap_id}][{cost_id}][{revenue_id}]."]
        out += [(year, t.format(said), t.format(_FLIP[said])) for t in templates]
    return out


def test_the_drivers_comparison_is_the_one_form_the_gate_reads() -> None:
    assert drivers_forms(CANDIDATE.read_text()) == {"grew": ("faster", "slower"), "fell": ("less", "more")}
    # 09a5b1a's line asked for both growths' own figures, a form with no gap in it: the test finds no form there.
    old = ('Compare operating-cost growth with revenue growth by stating both, each with its own figure and direction ("revenue '
           'fell 9.4% while operating costs fell 6.1%"), citing both; do not restate the gap between them as "Xpp more" or "less".')
    text = " ".join(CANDIDATE.read_text().split())
    rule = section_rules(text)["drivers"]
    assert drivers_forms(text.replace(rule, rule.split(" Compare ")[0] + " " + old)) == {}


@pytest.mark.parametrize("name", [name for name, _ in committed_packs()])
def test_the_drivers_comparison_passes_true_and_fails_its_mirror_on_every_pack(name: str) -> None:
    pack = dict(committed_packs())[name]
    forms = drivers_forms(CANDIDATE.read_text())
    for year, true, mirror in drivers_sentences(pack, forms):
        for backstops in (False, True):
            check = factcheck.check([{"section": "drivers", "type": "comparison", "text": true}], pack, backstops=backstops)
            assert check["passed"], (name, true, check["failures"])
            failures = factcheck.check([{"section": "drivers", "type": "comparison", "text": mirror}], pack,
                                       backstops=backstops)["failures"]
            assert any("other way" in f["failure"] for f in failures), (name, mirror, failures)


def test_the_drivers_comparison_reaches_every_pack_with_a_gap() -> None:
    # Every pack that gives the gap has the form in every such year: 17 of the 20 (COP, JPM and USB give none), the four
    # without operating-cost growth (PG, COST, KO, TGT) included, in both pack versions.
    forms = drivers_forms(CANDIDATE.read_text())
    counted = {name: len(drivers_sentences(pack, forms)) for name, pack in committed_packs()}
    assert {name for name, count in counted.items() if not count} == {
        f"{folder}/{ticker}" for folder in FOLDERS for ticker in ("COP", "JPM", "USB")}
    assert sum(counted.values()) == 2 * (141 + 2 * 94)


@pytest.mark.parametrize("paragraph, figures, ids", [
    ('- Write "net debt of $12.6 billion"; compare ("net cash of -27.4% of revenue against a -19.2% median").',
     ["$12.6 billion", "-27.4%", "-19.2%"], []),
    ("for example `Revenue rose 1.0% to $14.3 billion in FY2025 [F10][D440].` Several IDs", ["1.0%", "$14.3 billion"],
     ["F10", "D440"]),
    ('the 30 words in "three to five sentences"', [], []),
])
def test_examples_are_read_from_quotes_and_code(paragraph: str, figures: list[str], ids: list[str]) -> None:
    found, cited = examples(paragraph)
    assert [f.text for f in found] == figures and cited == ids
