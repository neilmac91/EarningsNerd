"""Structural gate (CLAUDE.md rule 12): a burst limiter keyed on an account is keyed on the account alone.

``enforce_rate_limit`` prefixes the trusted client IP to the key by default. For a key that carries
a user id (``f"summary:{current_user.id}"``) that default makes the bucket per (IP, user), so one
account presenting several client IPs multiplies its per-minute allowance. Every such call must
pass ``include_client_ip=False``. Encoded the way the os.getenv gate is: an AST walk over
``app/routers/**/*.py`` finds every ``enforce_rate_limit(`` call, reads its key — a string
constant, an f-string, or a name assigned exactly one such literal in the enclosing function — and
fails when a user-keyed call lacks the flag, or when a key cannot be read (an opaque key is a hole
the gate would otherwise walk past). A known set of user-keyed sites must be found, so the gate
cannot pass vacuously.
"""
import ast
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# Key prefixes of the user-keyed limiters this gate is known to cover. A site that disappears or
# is renamed fails the vacuity check below, so the list cannot go stale silently.
KNOWN_USER_KEYED_PREFIXES = {
    "summary:", "ask:",  # routers/summaries.py
    "analysis-coverage:", "analysis-dataset:", "analysis-xlsx:", "analysis-stream:",  # routers/analysis.py
    "feedback:",  # routers/feedback.py
    "change-password:",  # routers/auth.py
}


def _is_enforce_call(node: ast.Call) -> bool:
    func = node.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    return name == "enforce_rate_limit"


def _key_argument(call: ast.Call) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == "key_suffix":
            return kw.value
    return call.args[2] if len(call.args) > 2 else None


def _resolve_key(expr: ast.expr | None, scope: ast.AST) -> ast.expr | None:
    """A string constant or f-string, following a plain name through its single assignment in
    ``scope``. ``None`` when the key cannot be read."""
    if isinstance(expr, (ast.Constant, ast.JoinedStr)):
        return expr if not isinstance(expr, ast.Constant) or isinstance(expr.value, str) else None
    if isinstance(expr, ast.Name):
        assigned = [
            node.value for node in ast.walk(scope)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == expr.id for t in node.targets)
        ]
        if len(assigned) == 1:
            return _resolve_key(assigned[0], scope)
    return None


def _mentions_user_id(key: ast.expr) -> bool:
    for node in ast.walk(key):
        if isinstance(node, ast.Attribute) and node.attr == "id" and isinstance(node.value, ast.Name) \
                and "user" in node.value.id.lower():
            return True
        if isinstance(node, ast.Name) and node.id.lower().endswith("user_id"):
            return True
    return False


def _excludes_client_ip(call: ast.Call) -> bool:
    return any(
        kw.arg == "include_client_ip" and isinstance(kw.value, ast.Constant) and kw.value.value is False
        for kw in call.keywords
    )


def _key_prefix(key: ast.expr) -> str:
    if isinstance(key, ast.Constant):
        return key.value
    first = key.values[0] if key.values else None
    return first.value if isinstance(first, ast.Constant) else ""


def _scan() -> tuple[list[str], list[str], set[str]]:
    """(user-keyed calls missing the flag, unreadable keys, prefixes of user-keyed calls seen)."""
    missing_flag: list[str] = []
    unreadable: list[str] = []
    user_keyed_prefixes: set[str] = set()
    for py in sorted(ROUTERS_DIR.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for scope in ast.walk(tree):
            if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(scope):
                if not (isinstance(node, ast.Call) and _is_enforce_call(node)):
                    continue
                where = f"{rel}:{node.lineno}"
                key = _resolve_key(_key_argument(node), scope)
                if key is None:
                    unreadable.append(where)
                    continue
                if _mentions_user_id(key):
                    user_keyed_prefixes.add(_key_prefix(key))
                    if not _excludes_client_ip(node):
                        missing_flag.append(f"{where} ({ast.unparse(key)})")
    return missing_flag, unreadable, user_keyed_prefixes


def test_user_keyed_rate_limits_exclude_the_client_ip():
    missing_flag, unreadable, seen = _scan()
    assert not missing_flag, (
        "enforce_rate_limit calls keyed on a user id must pass include_client_ip=False, or one account "
        f"with several client IPs multiplies its burst allowance: {missing_flag}"
    )
    assert not unreadable, (
        "enforce_rate_limit key_suffix must be a string constant or f-string (or a name assigned one "
        f"in the same function) so this gate can read it: {unreadable}"
    )
    assert KNOWN_USER_KEYED_PREFIXES <= seen, (
        f"a known user-keyed limiter site was not found (renamed or removed?): "
        f"{sorted(KNOWN_USER_KEYED_PREFIXES - seen)}; update KNOWN_USER_KEYED_PREFIXES deliberately"
    )


def test_gate_detects_a_user_keyed_call_without_the_flag(tmp_path, monkeypatch):
    """The scanner itself: a user-keyed call without the flag, and an opaque key, are both reported."""
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "sample.py").write_text(
        "def ok(request, current_user):\n"
        "    key = f'a:{current_user.id}'\n"
        "    enforce_rate_limit(request, L, key, error_detail='x', include_client_ip=False)\n"
        "def bad(request, user):\n"
        "    enforce_rate_limit(request, L, f'b:{user.id}', error_detail='x')\n"
        "def opaque(request, suffix):\n"
        "    enforce_rate_limit(request, L, suffix, error_detail='x')\n"
        "def anonymous(request):\n"
        "    enforce_rate_limit(request, L, 'login', error_detail='x')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROUTERS_DIR", routers)
    monkeypatch.setattr(sys.modules[__name__], "BACKEND_DIR", tmp_path)
    missing_flag, unreadable, seen = _scan()
    assert [m.split(" ")[0] for m in missing_flag] == ["routers/sample.py:5"]
    assert unreadable == ["routers/sample.py:7"]
    assert seen == {"a:", "b:"}
