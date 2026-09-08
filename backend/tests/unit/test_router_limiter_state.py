"""Structural gate (E13c): router rate-limit state lives ONLY in the shared ``RateLimiter``.

``contact.py`` and ``feedback.py`` each used to keep a private ``dict[key, list[datetime]]`` as a
sliding-window store: unbounded key cardinality on a public route (a bucket was pruned only when
the same key came back), no ``Retry-After``, and a second copy of the window logic. The shared
``app.services.rate_limiter.RateLimiter`` already bounds keys, expires idle buckets lazily and
emits ``Retry-After`` through ``enforce_rate_limit``.

Allow-list gate, like the other structural specs: EVERY module-level assignment in
``app/routers/*.py`` whose value is a dict display, ``dict(...)``, ``defaultdict(...)`` or
``OrderedDict(...)``, or whose annotation is a mapping type, is an offender unless it is named in
``ALLOWED`` (the two module caches that map to a scalar/tuple and are not limiter state). An
unannotated ``_store = {}`` or a fixed-window ``dict[str, int]`` counter trips it just like the
removed sliding-window shape; a non-empty literal (request headers, an opaque response body) is
a constant and is not a store. A new legitimate cache is added to ``ALLOWED`` in the same PR,
with its reason.
"""
import ast
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parents[2] / "app" / "routers"

# file::name -> why it is not limiter state
ALLOWED = {
    "companies.py::_quote_cache": "per-process quote cache keyed by ticker, values are (quote, stamp)",
    "filings.py::_filings_synced_at": "per-process sync stamp per company, values are datetimes",
}

_MAPPING_NAMES = {"dict", "Dict", "defaultdict", "DefaultDict", "OrderedDict", "MutableMapping", "Mapping"}
_MAPPING_CALLS = {"dict", "defaultdict", "OrderedDict"}


def _base_name(node: ast.expr) -> str | None:
    """Unqualified name of ``x``, ``typing.x`` or ``x[...]``."""
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):  # string annotation
        try:
            return _base_name(ast.parse(node.value, mode="eval").body)
        except SyntaxError:
            return None
    return None


def _is_mapping_value(value: ast.expr | None) -> bool:
    """An empty dict display or a mapping constructor: the shapes a store starts from. A
    non-empty literal (request headers, an opaque response body) is a constant, not state."""
    if isinstance(value, ast.Dict):
        return not value.keys
    return isinstance(value, ast.Call) and _base_name(value.func) in _MAPPING_CALLS


def _module_level_mappings(path: Path) -> list[str]:
    """Names of every module-level mapping assignment in ``path`` (annotation or value)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:  # module level only: that is where per-process state leaks
        if isinstance(node, ast.AnnAssign):
            if _base_name(node.annotation) in _MAPPING_NAMES or _is_mapping_value(node.value):
                names.append(ast.unparse(node.target))
        elif isinstance(node, ast.Assign) and _is_mapping_value(node.value):
            names.extend(ast.unparse(t) for t in node.targets)
    return names


def _ad_hoc_limiter_stores(path: Path) -> list[str]:
    return [name for name in _module_level_mappings(path) if f"{path.name}::{name}" not in ALLOWED]


def test_routers_keep_no_ad_hoc_limiter_store():
    found = {
        f"{py.name}::{name}"
        for py in sorted(ROUTERS_DIR.glob("*.py"))
        for name in _ad_hoc_limiter_stores(py)
    }
    assert not found, (
        f"Module-level mapping(s) in app/routers outside the allow-list: {sorted(found)}. Router "
        "limiter state lives ONLY in app.services.rate_limiter.RateLimiter (bounded keys, lazy "
        "expiry, Retry-After): declare `X_LIMITER = RateLimiter(limit=..., window_seconds=...)` and "
        "call `enforce_rate_limit(request, X_LIMITER, key, error_detail=...)`. A genuine cache is "
        "added to ALLOWED with its reason."
    )


def test_allow_list_names_only_mappings_that_exist():
    """A stale allow-list entry would silently widen the gate."""
    present = {
        f"{py.name}::{name}" for py in ROUTERS_DIR.glob("*.py") for name in _module_level_mappings(py)
    }
    assert set(ALLOWED) <= present, sorted(set(ALLOWED) - present)


def test_gate_detects_every_ad_hoc_store_shape(tmp_path):
    """The gate must be able to go red: the removed contact shape, an unannotated store, a
    fixed-window counter and a string-annotated store all trip it; only allow-listed names pass."""
    sample = tmp_path / "contact.py"
    sample.write_text(
        "from collections import defaultdict\n"
        "from datetime import datetime\n"
        "_rate_limit_store: dict[str, list[datetime]] = {}\n"
        "_plain = {}\n"
        "_counter: dict[str, int] = {}\n"
        "_stringed: 'dict[str, list[float]]' = {}\n"
        "_dd = defaultdict(list)\n"
        "_built = dict()\n"
        "_quote_cache: dict[str, tuple[int, datetime]] = {}\n"
        "NOT_A_STORE = 3\n"
        "HEADERS = {'User-Agent': 'x'}\n",
        encoding="utf-8",
    )
    assert _ad_hoc_limiter_stores(sample) == [
        "_rate_limit_store", "_plain", "_counter", "_stringed", "_dd", "_built", "_quote_cache",
    ]
    companies = tmp_path / "companies.py"
    companies.write_text("_quote_cache: dict[str, tuple[int, float]] = {}\n", encoding="utf-8")
    assert _ad_hoc_limiter_stores(companies) == []
