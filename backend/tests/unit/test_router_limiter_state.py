"""Structural gate (E13c): router rate-limit state lives ONLY in the shared ``RateLimiter``.

``contact.py`` and ``feedback.py`` each used to keep a private ``dict[key, list[datetime]]`` as a
sliding-window store: unbounded key cardinality on a public route (a bucket was pruned only when
the same key came back), no ``Retry-After``, and a second copy of the window logic. The shared
``app.services.rate_limiter.RateLimiter`` already bounds keys, expires idle buckets lazily and
emits ``Retry-After`` through ``enforce_rate_limit``.

This AST walk fails when any router re-grows the ad-hoc shape: a module-level assignment whose
annotation is a mapping (``dict``/``Dict``/``defaultdict``/``DefaultDict``/``MutableMapping``)
to a sequence (``list``/``List``/``deque``/``Deque``), or whose value is a ``defaultdict`` call
over such a sequence. Plain module-level caches that map to a scalar/tuple (``companies``'
quote cache, ``filings``' sync timestamps) are deliberately outside this gate.
"""
import ast
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parents[2] / "app" / "routers"

_MAPPING_NAMES = {"dict", "Dict", "defaultdict", "DefaultDict", "MutableMapping"}
_SEQUENCE_NAMES = {"list", "List", "deque", "Deque"}


def _base_name(node: ast.expr) -> str | None:
    """Unqualified name of ``x``, ``typing.x`` or ``x[...]``."""
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _annotation_is_mapping_of_sequences(annotation: ast.expr) -> bool:
    if not isinstance(annotation, ast.Subscript) or _base_name(annotation.value) not in _MAPPING_NAMES:
        return False
    params = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
    return any(_base_name(param) in _SEQUENCE_NAMES for param in params)


def _value_is_defaultdict_of_sequences(value: ast.expr | None) -> bool:
    if not isinstance(value, ast.Call) or _base_name(value.func) != "defaultdict":
        return False
    return any(_base_name(arg) in _SEQUENCE_NAMES for arg in value.args)


def _ad_hoc_limiter_stores(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in tree.body:  # module level only — that is where per-process state leaks
        if isinstance(node, ast.AnnAssign):
            if _annotation_is_mapping_of_sequences(node.annotation) or _value_is_defaultdict_of_sequences(node.value):
                offenders.append(ast.unparse(node.target))
        elif isinstance(node, ast.Assign) and _value_is_defaultdict_of_sequences(node.value):
            offenders.extend(ast.unparse(t) for t in node.targets)
    return offenders


def test_routers_keep_no_ad_hoc_limiter_store():
    found = {
        f"{py.name}::{name}"
        for py in sorted(ROUTERS_DIR.glob("*.py"))
        for name in _ad_hoc_limiter_stores(py)
    }
    assert not found, (
        f"Ad-hoc rate-limit store(s) in app/routers: {sorted(found)}. Router limiter state lives "
        "ONLY in app.services.rate_limiter.RateLimiter (bounded keys, lazy expiry, Retry-After): "
        "declare `X_LIMITER = RateLimiter(limit=..., window_seconds=...)` and call "
        "`enforce_rate_limit(request, X_LIMITER, key, error_detail=...)`."
    )


def test_gate_detects_the_removed_contact_store_shape(tmp_path):
    """The gate must be able to go red: the exact store contact.py used to declare trips it."""
    sample = tmp_path / "contact.py"
    sample.write_text(
        "from datetime import datetime\n"
        "_rate_limit_store: dict[str, list[datetime]] = {}\n"
        "_quote_cache: dict[str, tuple[int, datetime]] = {}\n",
        encoding="utf-8",
    )
    assert _ad_hoc_limiter_stores(sample) == ["_rate_limit_store"]
