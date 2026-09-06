"""Bound SEC URL-literal homes and keep URL-text exemptions free of HTTP imports.

This app-only AST gate locates ``sec.gov`` string constants (including f-string fragments,
excluding docstrings/comments). It is not a request-callgraph or universal pacing/breaker proof:
existing facts-service companyfacts requests use a pure URL helper, and filing documents can
arrive as dynamic URLs. Review those transport paths separately under CLAUDE rule 5.

Sanctioned literal homes beyond ``services/edgar/**``:
- ``integrations/sec_api.py`` — EFTS; existing shared limiter/backoff, no breaker.
- ``utils/sec_urls.py`` — pure URL construction/validation, no I/O.
- ``config.py`` — Settings URL defaults, not a call site.
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

ALLOWED_SEC_GOV_FILES = {
    "integrations/sec_api.py",
    "utils/sec_urls.py",
    "config.py",
}
ALLOWED_SEC_GOV_DIRS = ("services/edgar/",)

NEEDLE = "sec.gov"


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of the Constant nodes that are docstrings (module/class/function leading string Expr)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _sec_gov_string_sites(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and NEEDLE in node.value
        and id(node) not in docstrings
    ]


def _is_allowed(rel: str) -> bool:
    return rel in ALLOWED_SEC_GOV_FILES or rel.startswith(ALLOWED_SEC_GOV_DIRS)


def test_sec_gov_literals_only_in_the_edgar_layer():
    offenders: list[str] = []
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(APP_DIR).as_posix()
        if _is_allowed(rel):
            continue
        offenders.extend(f"app/{rel}:{lineno}" for lineno in _sec_gov_string_sites(py))

    assert not offenders, (
        "`sec.gov` URL literals found outside sanctioned literal homes:\n  "
        + "\n  ".join(offenders)
        + "\nUse the existing paced SEC transports; this gate checks URL text, not request routing "
        "or universal breaker coverage — see lessons/sec-edgar-resilience-layer.md. "
        "Build archive/companyfacts URLs with app.utils.sec_urls. If you are adding a genuinely new "
        "sanctioned home, extend the allow-list in this test in the same PR with the reason."
    )


def test_allowlisted_files_still_exist():
    """A stale allow-list entry is a smell (a sanctioned home moved without the gate following)."""
    missing = [rel for rel in ALLOWED_SEC_GOV_FILES if not (APP_DIR / rel).exists()]
    assert not missing, f"Prune ALLOWED_SEC_GOV_FILES: {missing}"


# The two non-edgar files sanctioned for `sec.gov` literals are sanctioned as URL *text* only —
# a pure builder and Settings defaults. Neither may import an HTTP client, or a raw fetcher could
# hide behind the exemption. (`urllib.parse` is fine: it parses, it does not fetch.)
NO_FETCHER_FILES = {"utils/sec_urls.py", "config.py"}
FETCHER_MODULES = ("httpx", "requests", "aiohttp", "urllib.request", "urllib3", "http.client")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_url_text_exemptions_import_no_http_client():
    offenders: list[str] = []
    for rel in sorted(NO_FETCHER_FILES):
        for module in sorted(_imported_modules(APP_DIR / rel)):
            if module in FETCHER_MODULES or module.startswith(tuple(f"{m}." for m in FETCHER_MODULES)):
                offenders.append(f"app/{rel} imports {module}")
    assert not offenders, (
        "Files exempted from the sec.gov gate for URL text only must not import an HTTP client:\n  "
        + "\n  ".join(offenders)
        + "\nKeep these exemptions pure; use existing paced SEC transport paths for I/O."
    )
