"""Structural gate: no GET endpoints NAMED as mutations (WS-8 (e), security audit).

Scope: this checks handler-name verbs only — it cannot see what a body does. A GET named ``get_x``
that writes is not caught here; that is a code-review concern.

The API authenticates with cookies as well as bearer tokens, so a GET that mutates state is a
CSRF vector (a cross-site top-level navigation carries SameSite=Lax cookies) and — unauthenticated —
a free-abuse vector (the audit's ``/trending_tickers/refresh-prices`` fanned out to a paid API on
every hit). The crisp, low-false-positive form of the rule: a ``@<router>.get`` handler must not be
NAMED with a state-changing verb. Read-only verbs that merely sound active (``generate_sitemap``
renders XML, ``export_*`` streams a download) are deliberately not in the list, so the check has no
false positives on today's routers and needs no auth heuristics.

One-directional on purpose: the allow-list is tolerated legacy, and a legacy entry vanishing (the
handler was deleted or fixed) is pure improvement, so it does not fail the gate — prune it when seen.
"""
import ast
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parents[2] / "app" / "routers"

# Verbs that unambiguously change state. Matched as the handler name's first `_`-separated word.
MUTATING_VERBS = {
    "create", "update", "delete", "remove", "add", "set", "reset", "send", "resend", "refresh",
    "sync", "trigger", "regenerate", "mark", "toggle", "upsert", "revoke", "cancel", "purge",
    "clear", "invalidate", "save", "store", "write", "submit", "redeem", "activate", "deactivate",
    "enable", "disable", "start", "stop", "run", "retry", "rotate", "assign", "unassign", "archive",
}

# (router file, handler) -> why it is tolerated for now. Shrink, never grow.
ALLOWED_MUTATING_GETS: dict[tuple[str, str], str] = {
    ("trending.py", "refresh_ticker_prices"): (
        "legacy unauthenticated price refresh; removed by the WS-8 (a) dead-integration teardown — "
        "delete this entry when trending.py goes"
    ),
}


def _get_handlers(path: Path) -> list[tuple[str, int]]:
    """(handler name, lineno) for every function decorated with ``<anything>.get(...)``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "get"
            ):
                out.append((node.name, node.lineno))
    return out


def _is_mutating_name(name: str) -> bool:
    return name.split("_", 1)[0].lower() in MUTATING_VERBS


def test_get_handlers_are_not_named_as_mutations():
    offenders: list[str] = []
    for py in sorted(ROUTERS_DIR.rglob("*.py")):
        rel = py.relative_to(ROUTERS_DIR).as_posix()
        for name, lineno in _get_handlers(py):
            if _is_mutating_name(name) and (rel, name) not in ALLOWED_MUTATING_GETS:
                offenders.append(f"app/routers/{rel}:{lineno} {name}")

    assert not offenders, (
        "GET handlers named with a state-changing verb:\n  "
        + "\n  ".join(offenders)
        + "\nA GET must be safe and idempotent (cookie auth makes a mutating GET a CSRF vector). "
        "Make it a POST/PUT/DELETE, or — if the handler really is read-only and merely misnamed — "
        "rename it. Extending ALLOWED_MUTATING_GETS needs a documented reason in the same PR."
    )


def test_allowlist_entries_are_actually_mutating_names():
    """Guards the gate itself: an allow-list entry that the verb rule would not flag is dead weight."""
    for (_, name) in ALLOWED_MUTATING_GETS:
        assert _is_mutating_name(name), f"{name!r} is not flagged by MUTATING_VERBS — prune it"
