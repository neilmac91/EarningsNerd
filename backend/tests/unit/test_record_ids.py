"""Each open item in tasks/todo.md and each decision in docs/brand/decisions-log.md keeps one ID.

A PR takes the next free ID at its own base, so two open PRs can take the same one: on 2026-10-13, eleven IDs
were held twice across the open PRs, four of them by rows already on main. Git merges two rows that sit apart
without a conflict, so nothing else notices. The later of the two PRs to merge renumbers its row to the next
free ID, with the references to it, when it merges main; this test fails until it has.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORDS = {
    ROOT / "tasks" / "todo.md": re.compile(r"^- \[[ x]\] ([A-Z]\d+)\b", re.MULTILINE),
    ROOT / "docs" / "brand" / "decisions-log.md": re.compile(r"^\| (D-\d+) \|", re.MULTILINE),
}


def repeated(ids: list[str]) -> list[str]:
    """The IDs a record holds more than once."""
    return sorted(i for i, n in Counter(ids).items() if n > 1)


def test_repeated_names_each_id_held_more_than_once():
    assert repeated(["F1", "F2", "F1", "E1", "E1", "E1"]) == ["E1", "F1"]
    assert repeated(["D-030", "D-031"]) == []


def test_record_ids_are_unique():
    for path, row in RECORDS.items():
        name = path.relative_to(ROOT)
        ids = row.findall(path.read_text(encoding="utf-8"))
        assert ids, f"{name}: no row matched, so the ID pattern no longer fits the file"
        held = repeated(ids)
        assert not held, (
            f"{name} holds {held} more than once: the later PR to merge renumbers its row to the next free ID, "
            "with the references to it"
        )
