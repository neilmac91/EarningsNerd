"""The candidate prompt's examples copy no evaluation company's figures (DEEPSEEK-ERRORS.md §3 step 0.4), and its
section rules agree with its sentence budget (below the examples' tests).

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

from evals.trend_depth import autocite, factcheck
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
        ids += autocite.citations(example)
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
