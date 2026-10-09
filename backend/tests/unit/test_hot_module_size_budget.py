"""Rule-12 size-budget gate for the hot-module refactor (``tasks/refactor-plan-2026-10.md``).

The six most-changed backend modules are also the largest. While the refactor moves and splits them,
this gate stops any lane from growing them, and stops the moved code from re-accreting in its new home.
Each module has one budget file, ``tests/fixtures/size_budgets/<module>.json``, so a PR that shrinks a
module edits only its own budget file. The gate enforces:

* file ceilings: each of the six base files stays at or under its ``files`` row; a NEW module in one of
  the refactor's destinations (``FAMILIES``) is held to 600 lines. A base file's row above its W0.G
  value (``W0G_FILE_CEILINGS``) needs a dated raise line in the note;
* function ceilings (decision 6): every function in a budgeted file stays at or under 80 lines. Only the
  twenty long functions in ``FROZEN_LONG_FUNCTIONS`` may have a ``functions`` row, one row each, never
  above the W0.G size frozen there, so letting any other function past 80, or a long one past its W0.G
  size, means editing this gate. The freeze follows a long function anywhere in ``app/``: a function
  bearing one of the twenty names stays at or under that name's W0.G size wherever it lives;
* the ratchet: a row whose file or function no longer exists is stale, as is a row more than 100 file
  lines or 20 function lines above the actual size, or a function row at or under 80 (the default
  already covers it);
* the façade contract: every name a base file defined at W0.G (module-level names, and the members of
  its module-level classes, annotation-only dataclass fields included) still resolves on the base
  module. A module-level name with no mapping must still be defined in the base file itself; once a
  move maps it to the module that now defines it, the façade's binding must be that module's object;
* ``forbidden_imports`` rows ``[file glob, module]`` or ``[file glob, module, "exact"]``: no import
  statement in a matching file, lazy imports inside functions included and relative imports resolved
  against the file's package, may import that module (or, without ``"exact"``, anything under it).

Counting rule (pinned by ``test_the_counting_rule``): a file's size is its count of newline bytes (what
``wc -l`` prints). A function's size is ``end_lineno - lineno + 1`` from its ``def`` line, decorators
excluded, blanks, comments and docstring included, for every ``def``/``async def`` that is not inside
another function: at module level, in a class body (a nested class keys as ``Outer.Inner.name``), and
inside any block (``if``/``try``/``except``/``with``/``for``/``while``/``match``). Nested functions and
lambdas count inside their parent.

To change a ceiling: lower it in the commit that shrinks the code; a move re-keys a function row to its
new path at the same number. To raise a FILE ceiling, append a dated raise line to the budget file's
``note``, ``YYYY-MM-DD PR #N: <path> <old> -> <new> (<why extraction was not possible>)``, and add a
"Ceiling raise" paragraph to the PR body. A long function's ceiling never goes above its W0.G size.
Stated limits: dynamic imports (``importlib``, ``__import__``) and attribute access through a parent
package's import (``import app.services.edgar.compat``, then ``app.services.edgar.xbrl_service.x``) are
invisible to the import rows; names bound only by import statements are not part of the façade contract
(whoever imports such a name fails on its own import); removing a name from ``names``, and a file raise
that stays at or under the W0.G value, are not machine-checked: the note records why, and review checks it.
"""
from __future__ import annotations

import ast
import fnmatch
import importlib
import json
import re
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"
BUDGET_DIR = BACKEND_DIR / "tests" / "fixtures" / "size_budgets"

NEW_FUNCTION_CEILING = 80
NEW_MODULE_CEILING = 600
FILE_SLACK = 100
FUNCTION_SLACK = 20
BUDGET_KEYS = {"files", "functions", "names", "forbidden_imports", "note"}

# Budget file stem -> (base module, where its code may move). A destination ending in "/" is a package:
# every .py file under it is a new module. The xbrl names are listed one by one on purpose: a glob such
# as xbrl_*.py would also match the base file.
FAMILIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "copilot_service": ("app/services/copilot_service.py", ("app/services/copilot/",)),
    "facts_service": ("app/services/facts_service.py", ("app/services/facts/",)),
    "trend_analysis_service": ("app/services/trend_analysis_service.py", ("app/services/trend_analysis/",)),
    "openai_service": (
        "app/services/openai_service.py",
        ("app/services/ai/summary_finalize.py", "app/services/ai/summary_prompt.py"),
    ),
    "xbrl_service": (
        "app/services/edgar/xbrl_service.py",
        (
            "app/services/edgar/xbrl_cache.py",
            "app/services/edgar/xbrl_instance.py",
            "app/services/edgar/xbrl_companyfacts.py",
            "app/services/edgar/xbrl_standardized.py",
            "app/services/edgar/xbrl_sections.py",
        ),
    ),
    "instance_extractor": ("app/services/edgar/instance_extractor.py", ("app/services/edgar/instance/",)),
}

# The six base files' ceilings at W0.G. A files row above its value needs a dated raise line in the note.
W0G_FILE_CEILINGS: dict[str, int] = {
    "app/services/copilot_service.py": 1934,
    "app/services/facts_service.py": 2153,
    "app/services/trend_analysis_service.py": 1923,
    "app/services/openai_service.py": 1252,
    "app/services/edgar/xbrl_service.py": 1316,
    "app/services/edgar/instance_extractor.py": 1229,
}

# Decision 6: the twenty long functions' sizes at W0.G, keyed by their own name (a row re-keyed to a new
# path or class keeps its freeze). These are the only names that may have a functions row, and a row
# may never go above the size here.
FROZEN_LONG_FUNCTIONS: dict[str, int] = {
    "_answer_filing_question_attempt": 297,
    "_resolve_citations": 114,
    "normalize_companyfacts": 155,
    "backfill_facts": 144,
    "upsert_facts": 129,
    "reconcile_facts": 109,
    "remediate_industry_facts": 102,
    "derive_q4_eps_facts": 97,
    "upsert_facts_bulk": 84,
    "derive_same_period_metrics": 84,
    "build_observation_catalogue": 303,
    "build_dataset": 260,
    "stream_trend_narrative": 220,
    "summarize_filing": 552,
    "generate_structured_summary": 250,
    "_assemble_structured_summary": 87,
    "extract_standardized_metrics": 259,
    "_extract_from_filing_instance_sync": 239,
    "_parse_company_facts": 162,
    "get_xbrl_data": 83,
}

_RAISE_HELP = (
    "extract code instead of growing it. To raise a FILE ceiling, append a dated raise line to the budget "
    "file's note, 'YYYY-MM-DD PR #N: <path> <old> -> <new> (<why extraction was not possible>)', and add a "
    "'Ceiling raise' paragraph to the PR body. A function stays at or under 80 lines, and a long "
    "function's ceiling never goes above its W0.G size (tasks/refactor-plan-2026-10.md, decision 6)."
)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
           ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _load_budgets() -> dict[str, dict]:
    return {path.stem: json.loads(path.read_text()) for path in sorted(BUDGET_DIR.glob("*.json"))}


def function_sizes(source: str) -> dict[str, int]:
    """``name``, ``Class.name`` or ``Outer.Inner.name`` -> size, under the counting rule above."""
    sizes: dict[str, int] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = prefix + child.name  # its body, nested defs included, counts inside it
                sizes[key] = max(sizes.get(key, 0), child.end_lineno - child.lineno + 1)
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.stmt, ast.match_case, ast.excepthandler)):
                visit(child, prefix)

    visit(ast.parse(source), "")
    return sizes


def defined_names(source: str) -> set[str]:
    """The module-level names the source binds itself (def, class, assignment target), in any block."""
    names: set[str] = set()

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                names.add(child.id)
            elif not isinstance(child, _SCOPES):
                visit(child)

    visit(ast.parse(source))
    return names


def _has_member(owner: object, member: str) -> bool:
    """An attribute, or a field that only an annotation declares (a dataclass field without a default
    is not a class attribute, so ``hasattr`` alone would miss it)."""
    return (hasattr(owner, member) or member in getattr(owner, "__dataclass_fields__", {})
            or member in getattr(owner, "__annotations__", {}))


def raise_line(path: str, ceiling: int) -> re.Pattern[str]:
    """A dated raise line that names the file and its new ceiling (the format in ``_RAISE_HELP``)."""
    return re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}} PR #\d+: {re.escape(path)} \d+ -> {ceiling}\b")


def _line_count(rel_path: str) -> int:
    return (BACKEND_DIR / rel_path).read_bytes().count(b"\n")


def _rel(path: Path) -> str:
    return path.relative_to(BACKEND_DIR).as_posix()


def _family_files(stem: str) -> list[str]:
    """The family's budgeted files that exist: the base module, then every new module."""
    base, destinations = FAMILIES[stem]
    files = [base] if (BACKEND_DIR / base).is_file() else []
    for dest in destinations:
        if dest.endswith("/"):
            files.extend(sorted(_rel(p) for p in (BACKEND_DIR / dest).rglob("*.py")))
        elif (BACKEND_DIR / dest).is_file():
            files.append(dest)
    return files


def _in_family(stem: str, rel_path: str) -> bool:
    base, destinations = FAMILIES[stem]
    return rel_path == base or any(
        rel_path.startswith(dest) if dest.endswith("/") else rel_path == dest for dest in destinations
    )


def _module_name(rel_path: str) -> str:
    parts = rel_path.removesuffix(".py").split("/")
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imported_modules(rel_path: str, source: str) -> list[tuple[int, set[str]]]:
    """For every import statement in the file: (line, the module names it may import).

    Relative imports are resolved against the file's own package, so ``from ..xbrl_service import x``
    in ``app/services/edgar/instance/core.py`` reads as ``app.services.edgar.xbrl_service``. A
    ``from M import a`` may import the submodule ``M.a`` as well as ``M``, so both are candidates.
    """
    module = _module_name(rel_path)
    package = module if rel_path.endswith("/__init__.py") else module.rpartition(".")[0]
    found: list[tuple[int, set[str]]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.append((node.lineno, {alias.name for alias in node.names}))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = package.split(".")
                anchor = anchor[: len(anchor) - (node.level - 1)] if node.level > 1 else anchor
                base = ".".join(anchor + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            found.append((node.lineno, {base} | {f"{base}.{a.name}" for a in node.names if a.name != "*"}))
    return found


def _forbidden(candidate: str, module: str, exact: bool) -> bool:
    return candidate == module or (not exact and candidate.startswith(module + "."))


@pytest.fixture(scope="module")
def budgets() -> dict[str, dict]:
    return _load_budgets()


def test_the_budget_directory_holds_one_well_formed_file_per_module(budgets):
    assert sorted(budgets) == sorted(FAMILIES), "one budget file per module in FAMILIES, no other"
    problems = []
    for stem, data in budgets.items():
        if set(data) != BUDGET_KEYS:
            problems.append(f"{stem}.json: keys {sorted(data)}, expected {sorted(BUDGET_KEYS)}")
            continue
        base = FAMILIES[stem][0]
        if base not in data["files"]:
            problems.append(f"{stem}.json: no files row for its base module {base}")
        for path, ceiling in data["files"].items():
            if not _in_family(stem, path) or not isinstance(ceiling, int) or ceiling <= 0:
                problems.append(f"{stem}.json: files row {path!r}: {ceiling!r} (not this module's file, or not a positive int)")
        for key, ceiling in data["functions"].items():
            path, sep, qualname = key.partition("::")
            if not sep or not qualname or not _in_family(stem, path) or not isinstance(ceiling, int):
                problems.append(f"{stem}.json: functions row {key!r}: {ceiling!r} (want 'path::name' in this module)")
        for name, home in data["names"].items():
            if home is not None and ("." in name or not isinstance(home, str)):
                problems.append(f"{stem}.json: names row {name!r} -> {home!r} (only module-level names map, to a module path)")
        for row in data["forbidden_imports"]:
            if not (isinstance(row, list) and len(row) in (2, 3) and all(isinstance(x, str) for x in row)
                    and (len(row) == 2 or row[2] == "exact")):
                problems.append(f"{stem}.json: forbidden_imports row {row!r} (want [glob, module] or [glob, module, 'exact'])")
        if not isinstance(data["note"], str) or not data["note"].strip():
            problems.append(f"{stem}.json: note must say how the ceilings were set and record every raise")
    assert problems == []


@pytest.mark.parametrize("stem", sorted(FAMILIES))
def test_files_stay_within_their_ceilings(budgets, stem):
    data = budgets[stem]
    base = FAMILIES[stem][0]
    offenders = []
    for path in _family_files(stem):
        ceiling = data["files"].get(path, NEW_MODULE_CEILING)
        if path != base and ceiling > NEW_MODULE_CEILING:
            offenders.append(f"{path}: a new module's ceiling may not exceed {NEW_MODULE_CEILING} (row says {ceiling})")
        size = _line_count(path)
        if size > ceiling:
            offenders.append(f"{path} is {size} lines; its ceiling is {ceiling}: {_RAISE_HELP}")
    assert offenders == []


@pytest.mark.parametrize("stem", sorted(FAMILIES))
def test_functions_stay_within_their_ceilings(budgets, stem):
    rows = {}
    for data in budgets.values():
        rows.update(data["functions"])
    offenders, seen = [], 0
    for path in _family_files(stem):
        for qualname, size in function_sizes((BACKEND_DIR / path).read_text()).items():
            seen += 1
            ceiling = rows.get(f"{path}::{qualname}", NEW_FUNCTION_CEILING)
            if size > ceiling:
                offenders.append(f"{path}::{qualname} is {size} lines; its ceiling is {ceiling}: {_RAISE_HELP}")
    assert seen >= 10, f"{stem}: the scan found only {seen} functions; the gate is reading the wrong files"
    assert offenders == []


@pytest.mark.parametrize("stem", sorted(FAMILIES))
def test_ceilings_ratchet_and_never_go_stale(budgets, stem):
    data = budgets[stem]
    stale = []
    for path, ceiling in data["files"].items():
        if not (BACKEND_DIR / path).is_file():
            stale.append(f"files row {path}: the file no longer exists; delete the row")
        elif ceiling - _line_count(path) > FILE_SLACK:
            stale.append(f"files row {path}: ceiling {ceiling} is more than {FILE_SLACK} lines above its "
                         f"{_line_count(path)} lines; lower the ceiling")
    sizes_by_path: dict[str, dict[str, int]] = {}
    for key, ceiling in data["functions"].items():
        path, _, qualname = key.partition("::")
        if not (BACKEND_DIR / path).is_file():
            stale.append(f"functions row {key}: the file no longer exists; re-key the row to the function's new path")
            continue
        sizes = sizes_by_path.setdefault(path, function_sizes((BACKEND_DIR / path).read_text()))
        if qualname not in sizes:
            stale.append(f"functions row {key}: no such function in {path}; re-key or delete the row")
        elif ceiling <= NEW_FUNCTION_CEILING:
            stale.append(f"functions row {key}: {ceiling} is within the {NEW_FUNCTION_CEILING}-line default; delete the row")
        elif ceiling - sizes[qualname] > FUNCTION_SLACK:
            stale.append(f"functions row {key}: ceiling {ceiling} is more than {FUNCTION_SLACK} lines above its "
                         f"{sizes[qualname]} lines; lower the ceiling")
    assert stale == []


def test_function_rows_are_the_frozen_twenty_and_never_rise(budgets):
    problems, keyed = [], {}
    for stem, data in budgets.items():
        for key, ceiling in data["functions"].items():
            name = key.partition("::")[2].rpartition(".")[2]
            frozen = FROZEN_LONG_FUNCTIONS.get(name)
            if frozen is None:
                problems.append(f"{stem}.json {key}: only the twenty W0.G long functions have rows; every other "
                                f"function is held to {NEW_FUNCTION_CEILING} lines: extract a helper (decision 6)")
            elif name in keyed:
                problems.append(f"{stem}.json {key}: {name} already has the row {keyed[name]}; "
                                "one row per long function")
            elif ceiling > frozen:
                problems.append(f"{stem}.json {key}: {ceiling} is above its W0.G size {frozen}; a long function's "
                                "ceiling never goes above it: extract a helper first (decision 6)")
            keyed.setdefault(name, key)
    assert problems == []


def test_a_long_function_stays_within_its_w0g_size_anywhere_in_app():
    grown = []
    for path in sorted(APP_DIR.rglob("*.py")):
        for qualname, size in function_sizes(path.read_text()).items():
            frozen = FROZEN_LONG_FUNCTIONS.get(qualname.rpartition(".")[2])
            if frozen is not None and size > frozen:
                grown.append(f"{_rel(path)}::{qualname} is {size} lines, above its W0.G size {frozen} (decision 6)")
    assert grown == []


def test_a_file_ceiling_above_its_w0g_value_has_a_dated_raise_line(budgets):
    unrecorded = []
    for stem, data in budgets.items():
        for path, ceiling in data["files"].items():
            w0g = W0G_FILE_CEILINGS.get(path)
            if w0g is not None and ceiling > w0g and not raise_line(path, ceiling).search(data["note"]):
                unrecorded.append(f"{stem}.json files row {path}: {ceiling} is above its W0.G value {w0g} with no "
                                  f"raise line in note: {_RAISE_HELP}")
    assert unrecorded == []


@pytest.mark.parametrize("stem", sorted(FAMILIES))
def test_facade_names_still_resolve(budgets, stem):
    base = FAMILIES[stem][0]
    facade = importlib.import_module(_module_name(base))
    defined = defined_names((BACKEND_DIR / base).read_text())
    broken = []
    for name, home in budgets[stem]["names"].items():
        owner, _, member = name.partition(".")
        target = getattr(facade, owner, None)
        if target is None and not hasattr(facade, owner):
            broken.append(f"{name}: no longer resolves on {facade.__name__}; re-export it from the façade, or, "
                          "if it was deleted on purpose, remove it from names and say why in note")
            continue
        if member and not _has_member(target, member):
            broken.append(f"{name}: {owner} lost its member {member!r}")
            continue
        if home is not None:
            module = importlib.import_module(home)
            if getattr(facade, name) is not getattr(module, name, object()):
                broken.append(f"{name}: the façade's binding is not {home}.{name}; re-export that object itself")
        elif not member and name not in defined:
            broken.append(f"{name}: {base} no longer defines it; map it in names to the module that now does")
    assert broken == []


@pytest.mark.parametrize("stem", sorted(FAMILIES))
def test_forbidden_imports(budgets, stem):
    every_file = sorted(_rel(p) for p in APP_DIR.rglob("*.py"))
    violations = []
    for row in budgets[stem]["forbidden_imports"]:
        pattern, module, exact = row[0], row[1], len(row) == 3
        matched = [path for path in every_file if fnmatch.fnmatchcase(path, pattern)]
        if not matched:
            violations.append(f"row {row}: no file matches {pattern!r}; fix or delete the row")
        for path in matched:
            for line, candidates in imported_modules(path, (BACKEND_DIR / path).read_text()):
                hits = sorted(c for c in candidates if _forbidden(c, module, exact))
                if hits:
                    violations.append(f"{path}:{line} imports {hits[0]}, which row {row} forbids")
    assert violations == []


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("from ..xbrl_service import get_xbrl_data", {"app.services.edgar.xbrl_service",
                                                       "app.services.edgar.xbrl_service.get_xbrl_data"}),
        ("from .. import xbrl_service", {"app.services.edgar", "app.services.edgar.xbrl_service"}),
        ("from . import core", {"app.services.edgar.instance", "app.services.edgar.instance.core"}),
        ("from ...facts_service import x", {"app.services.facts_service", "app.services.facts_service.x"}),
        ("import app.services.edgar.xbrl_service as xs", {"app.services.edgar.xbrl_service"}),
        ("def f():\n    from app.services.edgar import compat", {"app.services.edgar", "app.services.edgar.compat"}),
    ],
)
def test_import_resolution_reads_relative_and_lazy_imports(statement, expected):
    [(_, candidates)] = imported_modules("app/services/edgar/instance/core.py", statement)
    assert candidates == expected


def test_forbidden_matching_distinguishes_prefix_from_exact():
    assert _forbidden("app.services.edgar.xbrl_service", "app.services.edgar", exact=False)
    assert not _forbidden("app.services.edgar.xbrl_service", "app.services.edgar", exact=True)
    assert _forbidden("app.services.edgar", "app.services.edgar", exact=True)
    assert not _forbidden("app.services.edgarx", "app.services.edgar", exact=False)


def test_the_counting_rule():
    source = (
        "import functools\n"
        "\n"
        "@functools.cache\n"
        "async def decorated():\n"   # counted from the def line: the decorator is excluded
        "    def nested():\n"         # nested defs count inside their parent and have no row
        "        return 1\n"
        "\n"
        "    return nested()\n"
        "\n"
        "if True:\n"
        "    def hidden():\n"         # inside a module-level block: still budgeted
        "        pass\n"
        "\n"
        "try:\n"
        "    pass\n"
        "except ImportError:\n"
        "    def fallback():\n"       # inside an except handler: still budgeted
        "        return 3\n"
        "\n"
        "match command:\n"
        "    case 'go':\n"
        "        def in_case():\n"    # inside a match case: still budgeted
        "            return 4\n"
        "\n"
        "class Box:\n"
        "    def method(self):\n"
        "        # comments and blanks count\n"
        "\n"
        "        return 2\n"
        "\n"
        "    class Inner:\n"
        "        def deep(self):\n"   # a nested class keys as Outer.Inner.name
        "            return 5\n"
    )
    assert function_sizes(source) == {
        "decorated": 5, "hidden": 2, "fallback": 2, "in_case": 2, "Box.method": 4, "Box.Inner.deep": 2,
    }


def test_defined_names_reads_bindings_but_not_imports_or_inner_scopes():
    source = (
        "import os\n"
        "from typing import Any\n"
        "LIMIT = 3\n"
        "a, (b, *c) = 1, (2, 3)\n"
        "total: int = 0\n"
        "try:\n"
        "    import json\n"
        "    HAS_JSON = True\n"
        "except ImportError:\n"
        "    HAS_JSON = False\n"
        "def run(x):\n"
        "    inner = x\n"
        "class Box:\n"
        "    member = 1\n"
        "squares = [n * n for n in range(3)]\n"
        "os.environ['X'] = '1'\n"
    )
    assert defined_names(source) == {"LIMIT", "a", "b", "c", "total", "HAS_JSON", "run", "Box", "squares"}


@pytest.mark.parametrize(
    ("note", "matches"),
    [
        ("W0.G baseline. 2026-10-20 PR #1200: app/services/facts_service.py 2153 -> 2160 (one-off)", True),
        ("2026-10-20 PR #1200: app/services/facts_service.py 2153 -> 2161 (the row says 2160)", False),
        ("PR #1200: app/services/facts_service.py 2153 -> 2160 (undated)", False),
        ("2026-10-20 PR #1200: app/services/facts_servicexpy 2153 -> 2160 (another path)", False),
    ],
)
def test_the_raise_line_format(note, matches):
    assert bool(raise_line("app/services/facts_service.py", 2160).search(note)) is matches
