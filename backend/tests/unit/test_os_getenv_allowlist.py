"""Structural gate for CLAUDE.md rule 8: all env access goes through ``app.config.Settings``.

Direct ``os.getenv`` / ``os.environ`` reads bypass validation, defaults, and the single documented
place where configuration lives (``docs/CONFIGURATION.md``); the audit found Sentry's init in
``main.py`` reading three variables that way. This test encodes the rule the way the naive-utcnow
gate does: an AST walk over ``app/**/*.py`` + ``main.py`` collects every env read and compares the
(file, enclosing scope) pairs against a checked-in allow-list. A NEW read anywhere fails with its
file:line and points the author at Settings; a sanctioned site that disappears also fails, so the
allow-list can never go stale.

Sanctioned sites are the pre-Settings infra bootstrap constants (rule 8's sole exception): pool
sizes and the EDGAR identity that must exist before — or independently of — the Settings object,
plus ``Settings.__init__`` itself, which is the bootstrap of that object (it reads the raw env to
special-case an IDE-injected OPENAI_API_KEY and to detect whether COOKIE_SECURE was set at all).
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

# (file relative to backend/, enclosing scope) -> why the raw env read is sanctioned.
ALLOWED_ENV_READS: dict[tuple[str, str], str] = {
    ("app/config.py", "Settings.__init__"): (
        "bootstrap of the Settings object itself (OPENAI_API_KEY override, COOKIE_SECURE presence)"
    ),
    ("app/database.py", "<module>"): "pre-Settings DB pool constants (infra bootstrap)",
    ("app/services/redis_service.py", "<module>"): "pre-Settings Redis pool constant (infra bootstrap)",
    ("app/services/edgar/config.py", "<module>"): "EDGAR identity + thread-pool/timeout constants (infra bootstrap)",
}

_ENV_ATTRS = {"getenv", "environ", "putenv", "unsetenv"}


class _EnvReadFinder(ast.NodeVisitor):
    """Collect (scope, lineno) for every ``os.getenv``/``os.environ`` access and ``from os import …``."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, int]] = []
        self._stack: list[str] = []

    def _scope(self) -> str:
        return ".".join(self._stack) if self._stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr in _ENV_ATTRS:
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "os" and any(alias.name in _ENV_ATTRS for alias in node.names):
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)


def _env_reads(path: Path) -> list[tuple[str, int]]:
    finder = _EnvReadFinder()
    finder.visit(ast.parse(path.read_text(encoding="utf-8")))
    return finder.hits


def _scanned_files() -> list[Path]:
    return [BACKEND_DIR / "main.py", *sorted(APP_DIR.rglob("*.py"))]


def test_env_reads_match_the_allowlist():
    found: dict[tuple[str, str], list[str]] = {}
    for py in _scanned_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in _env_reads(py):
            found.setdefault((rel, scope), []).append(f"{rel}:{lineno}")

    unexpected = {key: locs for key, locs in found.items() if key not in ALLOWED_ENV_READS}
    missing = set(ALLOWED_ENV_READS) - set(found)

    assert not unexpected and not missing, (
        "Raw os.getenv/os.environ reads drifted from the rule-8 allow-list.\n"
        f"  unexpected (read from app.config.settings instead): "
        f"{sorted(loc for locs in unexpected.values() for loc in locs)}\n"
        f"  missing (a sanctioned site was removed/moved — prune ALLOWED_ENV_READS): {sorted(missing)}\n"
        "Add a typed field to Settings (documented in docs/CONFIGURATION.md) and read "
        "`settings.<FIELD>`. Only pre-Settings infra bootstrap constants may read the env directly."
    )
