"""Structural gate for tombstoned third-party integrations (homepage-sections review, PR #571).

FMP was declared dead in writing on 2026-07-03 (legacy /api/v3 cut off; display use prohibited —
tasks/earnings-calendar-strategy.md) and the calendar was rewired off it, but its two other
consumers (trending_service, hot_filings) kept riding the corpse onto the public homepage for
three more days. Finnhub's self-serve tiers are personal-use-only, so its one consumer was equally
tombstoned. Stocktwits' ToS (Apr 2026 §5) bars automated extraction. See
lessons/arch-sweep-dead-integration-consumers.md.

The teardown PR (WS-8a, 2026-09) deleted the integration modules and every consumer, so the
allow-list is now EMPTY: any importer of these module paths anywhere in app/ fails here. The test
stays live so a resurrected client (or a new consumer) cannot land without re-litigating the
licence question in a PR that edits this file.
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# integration module -> the only app/ files allowed to import it. Empty since WS-8a: the modules
# themselves are gone; the keys stay so a re-added `app/integrations/{fmp,finnhub,stocktwits}.py`
# with a consumer trips the gate.
TOMBSTONED_INTEGRATIONS: dict[str, set[str]] = {
    "app.integrations.fmp": set(),
    "app.integrations.finnhub": set(),
    "app.integrations.stocktwits": set(),
}


def _imports_of(path: Path) -> set[str]:
    """Fully-qualified module names imported by a file.

    Handles all three styles: ``import a.b.c``, ``from a.b import c`` (each alias is joined onto
    the base module), and relative imports (``from .fmp import x``), which are resolved against
    the file's own package so integrations/__init__.py's re-exports are counted.
    """
    # ("app", "integrations", "fmp") for a module; package = parts minus the module/`__init__` leaf.
    rel_parts = path.relative_to(APP_DIR.parent).with_suffix("").parts
    package_parts = rel_parts[:-1]

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # level=1 → current package, each extra level strips one package segment.
                base_parts = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join(base_parts)
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            if module:
                modules.add(module)
                modules.update(f"{module}.{alias.name}" for alias in node.names)
    return modules


def test_tombstoned_integrations_have_no_new_importers():
    importers: dict[str, set[str]] = {name: set() for name in TOMBSTONED_INTEGRATIONS}
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        modules = _imports_of(py)
        for name in TOMBSTONED_INTEGRATIONS:
            if name in modules:
                importers[name].add(rel)

    for name, allowed in TOMBSTONED_INTEGRATIONS.items():
        found = importers[name]
        assert found == allowed, (
            f"Importers of tombstoned integration `{name}` drifted from the allowlist.\n"
            f"  unexpected (do NOT build on a dead/unlicensed integration): {sorted(found - allowed)}\n"
            f"  missing: {sorted(allowed - found)}\n"
            "FMP's legacy API is dead and its ToS prohibits display use; Finnhub's self-serve tiers "
            "are personal-use-only; Stocktwits' ToS bars automated extraction "
            "(tasks/homepage-sections-review-findings.md §2.4/§4). New market/news data needs a "
            "licensed source; EDGAR (public domain) is the sanctioned $0 default."
        )


def test_tombstoned_integration_modules_are_deleted():
    """The clients themselves must stay deleted — not merely unimported (WS-8a teardown).

    Both spellings of the module path are checked: `integrations/fmp.py` AND the package form
    `integrations/fmp/__init__.py`, which resolves to the same `app.integrations.fmp` and slipped
    past the file-only check under mutation.
    """
    for name in TOMBSTONED_INTEGRATIONS:
        rel = Path(*name.split(".")[1:])
        assert not (APP_DIR / rel.with_suffix(".py")).exists(), f"{rel}.py was resurrected; see this file's docstring"
        assert not (APP_DIR / rel).is_dir(), (
            f"{rel}/ was resurrected as a package (same module path as {rel}.py); see this file's docstring"
        )


def test_tombstoned_integrations_are_not_named_as_strings_in_app():
    """Dynamic imports — importlib.import_module("app.integrations.fmp"), __import__, a lazy-loader
    table — are string literals the AST importer scan above cannot see. A plain-text scan of every
    app/ source file for the dotted module names closes that hole."""
    hits: dict[str, list[str]] = {}
    for py in APP_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for name in TOMBSTONED_INTEGRATIONS:
            if name in text:
                hits.setdefault(name, []).append(py.relative_to(APP_DIR).as_posix())
    assert hits == {}, (
        f"app/ source mentions tombstoned integration module path(s): {hits}\n"
        "Static imports are caught by test_tombstoned_integrations_have_no_new_importers; this catches "
        "importlib/__import__/string-keyed loaders. Do NOT build on a dead/unlicensed integration."
    )
