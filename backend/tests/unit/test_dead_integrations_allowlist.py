"""Structural gate for tombstoned third-party integrations (homepage-sections review, PR #571).

FMP was declared dead in writing on 2026-07-03 (legacy /api/v3 cut off; display use prohibited —
tasks/earnings-calendar-strategy.md) and the calendar was rewired off it, but its two other
consumers (trending_service, hot_filings) kept riding the corpse onto the public homepage for
three more days. Finnhub's self-serve tiers are personal-use-only, so its one consumer is equally
tombstoned. See lessons/arch-sweep-dead-integration-consumers.md.

This test encodes the sweep structurally (the naive-utcnow allowlist move): the ONLY modules
allowed to import a tombstoned integration are the legacy consumers awaiting the teardown PR.
A NEW import anywhere fails here; the teardown PR shrinks the allowlist to empty in the same
change that deletes the consumers.
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# integration module -> the only app/ files still allowed to import it (legacy, pending teardown).
TOMBSTONED_INTEGRATIONS: dict[str, set[str]] = {
    "app.integrations.fmp": {
        "integrations/__init__.py",      # package re-export only
        "services/hot_filings.py",       # legacy Trending Filings scoring (surface unmounted)
        "services/trending_service.py",  # legacy Market Movers pipeline (surface flag-hidden)
    },
    "app.integrations.finnhub": {
        "integrations/__init__.py",
        "services/hot_filings.py",
    },
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
            f"  missing (teardown landed? shrink the allowlist in the same PR): {sorted(allowed - found)}\n"
            "FMP's legacy API is dead and its ToS prohibits display use; Finnhub's self-serve tiers "
            "are personal-use-only (tasks/homepage-sections-review-findings.md §2.4/§4). New market/"
            "news data needs a licensed source; EDGAR (public domain) is the sanctioned $0 default."
        )
