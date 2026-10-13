"""Structural gate for CLAUDE.md rule 2 (filing-only summaries) over the section-text modules.

The "what changed in the next filing" workflow (tasks/todo.md E17) stores a filing's Item 1A text
(``filing_section_text``), diffs it against the PRIOR filing's (``section_diff``) and serves the
result on the labelled cross-filing surface, the Change Report, with a reader's review of it
(``section_review_service``). Rule 2 says that content never reaches a summary: user-visible
summary and Copilot output derives only from the filing the user chose. That was prose until now.

This test walks the import graph of ``app/`` (module-level and function-local imports alike,
relative imports resolved) from the summary orchestrator, its stages, the AI layer, the Copilot
modules and the background generation path, and fails when any of them reaches, directly or
through another service, one of the modules that hold or compare another filing's text:
``section_diff``, ``filing_section_service``, ``section_review_service`` and
``change_report_service``. The ``app.models`` package re-exports every model, so the walk does not
descend into it (a model module imports no service; the third test keeps that true). Instead every
module the walk reaches, the roots and all they import, is checked for ``FilingSectionText`` or
``SectionReview`` named in any form: imported by name (absolute, relative or through ``import *``),
used as a name, read as an attribute (``models.FilingSectionText``), or their model modules imported.
A new reach fails with the path that led there. Adding a summary stage that needs the diff is a
design change against rule 2: surface it first.
"""
import ast
from collections import deque
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

# Modules that hold or compare another filing's text. Reaching one from a root fails.
FORBIDDEN_SERVICE_MODULES = frozenset({
    "app.services.section_diff",
    "app.services.filing_section_service",
    "app.services.section_review_service",
    "app.services.change_report_service",
})
FORBIDDEN_MODEL_MODULES = frozenset({"app.models.filing_section_text", "app.models.section_review"})
FORBIDDEN_MODEL_NAMES = frozenset({"FilingSectionText", "SectionReview"})
# The walk stops at the models package: its __init__ re-exports every model, which says nothing
# about who reads section text.
LEAF_PACKAGES = frozenset({"app.models"})


def _is_root(module: str) -> bool:
    return (
        module == "app.services.summary_pipeline"
        or module.startswith("app.services.summary_stages")
        or module.startswith("app.services.ai")
        or module.startswith("app.services.copilot")
        or module in {"app.services.openai_service", "app.services.summary_generation_service"}
    )


def _module_name(path: Path) -> str:
    parts = path.relative_to(BACKEND_DIR).with_suffix("").parts
    name = ".".join(parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _app_modules() -> dict[str, Path]:
    return {_module_name(py): py for py in APP_DIR.rglob("*.py")}


def resolve_from(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    """The absolute module a ``from … import`` names; a relative level is resolved against ``module``
    (``is_package`` says whether ``module`` is a package ``__init__``)."""
    if not node.level:
        return node.module or ""
    package = module if is_package else module.rsplit(".", 1)[0]
    base = package.split(".")
    if node.level > 1:
        base = base[: len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def imported_modules(tree: ast.AST, module: str, is_package: bool, known: set[str]) -> set[str]:
    """Every ``app`` module ``tree`` imports, at module level or inside a function, as module names.

    ``import app.x.y`` is the longest known prefix of the dotted name; ``from app.x import y`` is
    ``app.x.y`` when that is a module and ``app.x`` otherwise; a relative import is resolved against
    ``module``."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                while name:
                    if name in known:
                        out.add(name)
                        break
                    name = name.rsplit(".", 1)[0] if "." in name else ""
        elif isinstance(node, ast.ImportFrom):
            target = resolve_from(node, module, is_package)
            if not target.startswith("app"):
                continue
            for alias in node.names:
                full = f"{target}.{alias.name}"
                if full in known:
                    out.add(full)
                elif target in known:
                    out.add(target)
    return out


def model_references(tree: ast.AST, module: str, is_package: bool) -> list[str]:
    """Every way ``tree`` names FilingSectionText / SectionReview or imports their modules, with lines:
    an import by name (absolute or relative, or ``import *`` from the models package), a model module
    imported, a bare name, an attribute read (``models.FilingSectionText``)."""
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = resolve_from(node, module, is_package)
            if target in FORBIDDEN_MODEL_MODULES:
                hits.append((node.lineno, len(hits), f"line {node.lineno}: from {target} import …"))
            if target.startswith("app.models"):
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODEL_NAMES or alias.name == "*":
                        hits.append((node.lineno, len(hits), f"line {node.lineno}: from {target} import {alias.name}"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN_MODEL_MODULES:
                    hits.append((node.lineno, len(hits), f"line {node.lineno}: import {alias.name}"))
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_MODEL_NAMES:
            hits.append((node.lineno, len(hits), f"line {node.lineno}: {node.id}"))
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_MODEL_NAMES:
            hits.append((node.lineno, len(hits), f"line {node.lineno}: .{node.attr}"))
    return [text for _, _, text in sorted(hits)]


def reach_paths(graph: dict[str, set[str]], roots: list[str], forbidden: frozenset[str], leaves: frozenset[str]) -> list[str]:
    """For each root that reaches a forbidden module, the import path that gets there (one per root)."""
    paths: list[str] = []
    for root in sorted(roots):
        parent: dict[str, str | None] = {root: None}
        queue = deque([root])
        while queue:
            module = queue.popleft()
            if module in forbidden:
                chain = []
                while module is not None:
                    chain.append(module)
                    module = parent[module]
                paths.append(" -> ".join(reversed(chain)))
                break
            if module in leaves:
                continue
            for dep in sorted(graph.get(module, ())):
                if dep not in parent:
                    parent[dep] = module
                    queue.append(dep)
    return paths


def reached_modules(graph: dict[str, set[str]], roots: list[str], leaves: frozenset[str]) -> set[str]:
    """The roots and every module they import, transitively, not descending into the leaves."""
    seen: set[str] = set()
    queue = deque(roots)
    while queue:
        module = queue.popleft()
        if module in seen:
            continue
        seen.add(module)
        if module not in leaves:
            queue.extend(dep for dep in graph.get(module, ()) if dep not in seen)
    return seen


def _graph() -> tuple[dict[str, set[str]], list[str], dict[str, Path]]:
    modules = _app_modules()
    known = set(modules)
    graph = {
        name: imported_modules(ast.parse(path.read_text(encoding="utf-8")), name, path.name == "__init__.py", known)
        for name, path in modules.items()
    }
    return graph, [name for name in modules if _is_root(name)], modules


def test_summary_copilot_and_ai_modules_never_reach_section_text_or_the_review():
    graph, roots, modules = _graph()
    assert len(roots) > 20, "the root set should cover the pipeline, its stages, the AI layer and Copilot"
    paths = reach_paths(graph, roots, FORBIDDEN_SERVICE_MODULES, LEAF_PACKAGES)
    reached = sorted(name for name in reached_modules(graph, roots, LEAF_PACKAGES) if not name.startswith("app.models"))
    assert len(reached) > len(roots), "the roots import other app modules; the reach set should be wider than the roots"
    named = {
        name: hits
        for name in reached
        if (hits := model_references(ast.parse(modules[name].read_text(encoding="utf-8")), name, modules[name].name == "__init__.py"))
    }
    assert not paths and not named, (
        "A summary, Copilot or AI module reaches another filing's section text (CLAUDE.md rule 2: "
        "filing-only summaries; cross-filing content belongs to the Change Report only).\n"
        f"  import paths: {paths}\n"
        f"  FilingSectionText / SectionReview named in a reached module: {named}\n"
        "Keep section_diff, filing_section_service, section_review_service and change_report_service "
        "out of the orchestrator, its stages, the AI layer and Copilot, and the two models out of "
        "everything they import; the Change Report is the labelled surface for what changed between filings."
    )


def test_the_forbidden_modules_exist_so_the_rule_has_a_subject():
    modules = _app_modules()
    missing = sorted((FORBIDDEN_SERVICE_MODULES | FORBIDDEN_MODEL_MODULES) - set(modules))
    assert not missing, f"update the forbidden set: {missing} no longer exist"


def test_model_modules_import_no_service_so_the_models_leaf_hides_no_reach():
    graph, _roots, _modules = _graph()
    offenders = {
        name: sorted(dep for dep in deps if dep.startswith("app.services"))
        for name, deps in graph.items()
        if name.startswith("app.models") and any(dep.startswith("app.services") for dep in deps)
    }
    assert not offenders, (
        f"a model module imports a service: {offenders}. The walk above treats app.models as a leaf, "
        "which is sound only while the models import no service; move the import or widen the walk."
    )


def test_walk_follows_function_local_and_relative_imports_and_reports_the_path():
    known = {"app.services.a", "app.services.b", "app.services.c", "app.services.pkg", "app.services.pkg.inner", "app.models"}
    tree_a = ast.parse(
        "from app.models import Filing\n"
        "def f():\n"
        "    from app.services import b\n"
        "    return b\n"
    )
    tree_b = ast.parse("from . import c\n")
    tree_inner = ast.parse("from .. import a\n")
    graph = {
        "app.services.a": imported_modules(tree_a, "app.services.a", False, known),
        "app.services.b": imported_modules(tree_b, "app.services.b", False, known),
        "app.services.c": set(),
        "app.services.pkg.inner": imported_modules(tree_inner, "app.services.pkg.inner", False, known),
        "app.models": {"app.services.c"},  # a leaf: never followed
    }
    assert graph["app.services.a"] == {"app.models", "app.services.b"}
    assert graph["app.services.b"] == {"app.services.c"}
    assert graph["app.services.pkg.inner"] == {"app.services.a"}
    assert reach_paths(graph, ["app.services.pkg.inner"], frozenset({"app.services.c"}), frozenset({"app.models"})) == [
        "app.services.pkg.inner -> app.services.a -> app.services.b -> app.services.c"
    ]
    assert reached_modules(graph, ["app.services.pkg.inner"], frozenset({"app.models"})) == {
        "app.services.pkg.inner", "app.services.a", "app.models", "app.services.b", "app.services.c",
    }
    # Through the models leaf only: not a reach.
    assert reach_paths({"r": {"app.models"}, "app.models": {"app.services.c"}}, ["r"], frozenset({"app.services.c"}), frozenset({"app.models"})) == []
    assert reached_modules({"r": {"app.models"}, "app.models": {"app.services.c"}}, ["r"], frozenset({"app.models"})) == {"r", "app.models"}


def test_model_reference_finder_sees_every_form_including_relative_imports_and_attributes():
    tree = ast.parse(
        "from app.models import Filing, SectionReview\n"
        "from app.models.filing_section_text import FilingSectionText\n"
        "import app.models.section_review\n"
        "from ...models import FilingSectionText\n"
        "from app import models\n"
        "rows = db.query(models.FilingSectionText).all()\n"
        "other = SectionReview\n"
        "from app.models import Summary\n"
        "note = 'FilingSectionText'\n"
    )
    assert model_references(tree, "app.services.ai.cash_claims", False) == [
        "line 1: from app.models import SectionReview",
        "line 2: from app.models.filing_section_text import …",
        "line 2: from app.models.filing_section_text import FilingSectionText",
        "line 3: import app.models.section_review",
        "line 4: from app.models import FilingSectionText",
        "line 6: .FilingSectionText",
        "line 7: SectionReview",
    ]
    # A package __init__ resolves one level less: ``from .section_review import …`` inside app/models.
    tree_pkg = ast.parse("from .section_review import SectionReview\n")
    assert model_references(tree_pkg, "app.models", True) == [
        "line 1: from app.models.section_review import …",
        "line 1: from app.models.section_review import SectionReview",
    ]
