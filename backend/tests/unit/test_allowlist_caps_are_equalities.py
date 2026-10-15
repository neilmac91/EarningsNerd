"""An allowlist or residue cap is an equality, never a ceiling: the backend half of
frontend/tests/unit/allowlistCapsAreEqualities.spec.ts (D-040; lessons/test-allowlist-caps-are-equalities.md;
CLAUDE.md rule 12).

``assert len(EXEMPT) <= EXEMPT_CAP`` lets a deletion leave the cap where it was, after which a later entry fits
under it with no change to the cap line and the test never refuses the growth it exists to refuse;
``assert len(EXEMPT) == EXEMPT_CAP`` makes every deletion lower the cap in the same commit and every addition
raise it, in review.

The scan reads every Python file git tracks under backend/tests through ``ast`` and reports each ``assert`` that
compares ``len(...)`` with a named constant (CONSTANT_CASE, or one attribute of one) by ``<=``, or the mirrored
``CAP >= len(...)``, chained comparisons included. A literal bound, a lower-case name and the strict ``<`` are
not read as a cap, and neither is a comparison inside ``all(...)`` or any other expression that is not the
assert's own test; this docstring says so rather than claiming more. CEILINGS names each site that bounds a
value rather than a list's size, by file with its count and why. Shrink-only: its total equals CEILINGS_MAX,
lowered in the same commit as a line, and a line whose sites left fails.
"""

from __future__ import annotations

import ast
import re
import subprocess  # nosec B404 - runs git ls-files on this checkout, fixed arguments
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
CONSTANT = re.compile(r"^[A-Z][A-Z0-9_]*$")

CEILINGS: dict[str, tuple[int, str]] = {
    "tests/unit/test_agent_workflow_rules.py": (
        1,
        "TODO_MAX_LINES bounds the open-items page's length (AGENTS.md §7), a value ceiling, not a list's size",
    ),
    "tests/unit/test_attribution_verify.py": (
        1,
        "MAX_VERIFIABLE_CLAUSES is the batch bound verify.verifiable enforces; the test proves the bound holds",
    ),
}
# Equal to the sites listed, never above them: lower it with a line in the same commit.
CEILINGS_MAX = 2


def _named(node: ast.expr) -> str | None:
    """The named constant a bound reads, or None for a literal, a lower-case name or an expression."""
    if isinstance(node, ast.Name) and CONSTANT.match(node.id):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and CONSTANT.match(node.value.id):
        return f"{node.value.id}.{node.attr}"
    return None


def _is_len(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len"


def ceiling_sites(source: str, file: str = "probe.py") -> list[str]:
    """Every assert in one source that holds a list's size under a named constant, as ``file:line form``."""
    sites: list[str] = []
    for node in ast.walk(ast.parse(source, filename=file)):
        if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
            continue
        operands = [node.test.left, *node.test.comparators]
        for i, op in enumerate(node.test.ops):
            low, high = operands[i], operands[i + 1]
            if isinstance(op, ast.LtE) and _is_len(low) and (name := _named(high)):
                sites.append(f"{file}:{node.lineno} len(...) <= {name}")
            elif isinstance(op, ast.GtE) and _is_len(high) and (name := _named(low)):
                sites.append(f"{file}:{node.lineno} {name} >= len(...)")
    return sites


def _tracked_tests() -> list[str]:
    listing = subprocess.run(  # nosec B603 B607 - git on this checkout, fixed arguments
        ["git", "ls-files", "-z", "tests"], cwd=BACKEND, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return sorted(path for path in listing.split("\0") if path.endswith(".py"))


def test_the_scan_reads_the_cap_idiom_and_nothing_else():
    assert ceiling_sites(
        "assert len(EXEMPT) <= EXEMPT_CAP\n"
        "assert len(PINNED) <= LIMITS.files, 'message'\n"
        "assert MAX_SIZE >= len(ALLOWED)\n"
        "assert 0 < len(EXEMPT) <= EXEMPT_CAP\n"
    ) == [
        "probe.py:1 len(...) <= EXEMPT_CAP",
        "probe.py:2 len(...) <= LIMITS.files",
        "probe.py:3 MAX_SIZE >= len(...)",
        "probe.py:4 len(...) <= EXEMPT_CAP",
    ]
    assert ceiling_sites(
        "assert len(EXEMPT) == EXEMPT_CAP\n"
        "assert len(found) <= 5\n"
        "assert len(found) < LIMIT\n"
        "assert total <= SEC_CAP\n"
        "assert len(found) <= limit\n"
        "assert all(len(x) <= CAP for x in groups)\n"
        "if len(found) <= CAP:\n    pass\n"
    ) == []


def test_every_list_cap_in_the_backend_tests_is_an_equality():
    found: dict[str, int] = {}
    unlisted: list[str] = []
    for rel in _tracked_tests():
        sites = ceiling_sites((BACKEND / rel).read_text(encoding="utf-8"), rel)
        if sites:
            found[rel] = len(sites)
            if rel not in CEILINGS:
                unlisted += sites
    assert not unlisted, (
        "A list cap written as a ceiling: make it ==, so a deletion lowers the cap in the same commit "
        f"(D-040), or list a value bound in CEILINGS with its reason: {unlisted}"
    )
    assert found == {path: count for path, (count, _why) in CEILINGS.items()}, (
        f"CEILINGS no longer matches the tree; move each line with its sites: {found}"
    )
    assert sum(count for count, _why in CEILINGS.values()) == CEILINGS_MAX
