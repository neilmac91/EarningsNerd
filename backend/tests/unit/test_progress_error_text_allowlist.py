"""Structural gate: the progress row's ``error`` is a fixed code or sentence, never text built where it is written.

``GET /api/summaries/filing/{id}/progress`` serves the row without authentication, and the watchlist repeats it. The
generic failure handler wrote ``error=error_msg[:200]`` there, where ``error_msg`` was ``str(e)``: a database error's
SQL, a provider's response body or a URL, readable by anyone who polled a filing id. The row now carries the code the
durable job records for the same outcome, and the exception stays in the server log.

An AST walk over ``app/**/*.py`` finds every call that names ``record_progress`` or ``record_progress_sync`` (as the
function called, or handed to a runner: ``run.run_sync_db(run.record_progress_sync, ...)``) and passes ``error=``.
The value must be fixed by its shape: a string literal or ``None``, a constant's name (``UPPER_CASE``, plain or
dotted) or an enum member's ``.value``. Any other shape (a variable, a slice, a call, an f-string) is listed below
with its count and where its text comes from; the counts are equalities
(lessons/test-allowlist-caps-are-equalities.md), so a new site fails and a removed one must lower its count.

Not covered: a write of the column that does not go through these two functions (``mark_stalled_progress`` sets
``STALLED_ERROR`` in an UPDATE of its own); what a listed variable holds, which its reason states and review checks;
a constant whose value is built from runtime text; an attribute named ``value`` on something that is not an enum; a call that
passes ``error`` inside ``**kwargs``.
"""
import ast
import re
from pathlib import Path

from tests.support.caught_exception_text import calls_in, name_of

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"
WRITERS = {"record_progress", "record_progress_sync"}
_CONSTANT_NAME = re.compile(r"[A-Z][A-Z0-9_]*")

# (file relative to backend/, enclosing function) -> (sites, where the text comes from).
ALLOWED: dict[tuple[str, str], tuple[int, str]] = {
    ("app/services/summary_stages/generation.py", "generate"): (
        1, "the provider's error payload message, which ai/summary_finalize.extraction_failure writes as a fixed "
           "sentence; a payload without one gets the generic sentence",
    ),
}


def fixed_by_shape(value: ast.expr) -> bool:
    """Whether an ``error=`` value is a literal, a constant's name or an enum member's ``.value``."""
    if isinstance(value, ast.Constant):
        return value.value is None or isinstance(value.value, str)
    if isinstance(value, ast.Attribute) and value.attr == "value":
        return True
    return bool(_CONSTANT_NAME.fullmatch(name_of(value)))


def sites_in(source: str) -> list[tuple[str, int]]:
    """(enclosing function, lineno) of each progress write in ``source`` whose ``error=`` is not fixed by its shape."""
    hits = []
    for scope, _caught, call in calls_in(source):
        if not ({name_of(call.func)} | {name_of(argument) for argument in call.args}) & WRITERS:
            continue
        if any(keyword.arg == "error" and not fixed_by_shape(keyword.value) for keyword in call.keywords):
            hits.append((scope, call.lineno))
    return hits


def test_progress_errors_not_fixed_by_their_shape_match_the_allowlist():
    found: dict[tuple[str, str], list[int]] = {}
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = path.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in sites_in(path.read_text(encoding="utf-8")):
            found.setdefault((relative, scope), []).append(lineno)

    unlisted = {key: lines for key, lines in found.items() if key not in ALLOWED}
    assert not unlisted, (
        "A progress write passes an error that is not a literal, a constant or an enum member's value. The row is "
        "served without authentication, so store a fixed code and keep the exception's text in the log: "
        + ", ".join(f"{file}:{lines} in {scope}" for (file, scope), lines in sorted(unlisted.items()))
    )
    counts = {key: len(lines) for key, lines in found.items()}
    expected = {key: count for key, (count, _reason) in ALLOWED.items()}
    assert counts == expected, (
        "A listed site's count changed or it is gone; lower or remove its entry in ALLOWED: "
        f"found {dict(sorted(counts.items()))}"
    )


def test_each_shape_of_an_error_built_at_the_call_is_found():
    built = ["error_msg[:200]", "str(e)", "str(e)[:200]", 'f"failed: {e}"', "message", "payload.get('message')", "e"]
    calls = (
        "pipeline.record_progress(session, filing_id, 'error', error={value}, starts_run=True)",
        "record_progress(session, filing_id, 'error', error={value})",
        "await run.run_sync_db(run.record_progress_sync, filing_id, 'error', error={value})",
    )
    for value in built:
        for call in calls:
            source = f"async def failed(run, e):\n    {call.format(value=value)}\n"
            assert sites_in(source) == [("failed", 2)], source


def test_a_fixed_error_or_another_functions_error_is_not_found():
    fixed = ["'Pipeline timeout'", "None", "GENERATION_FAILED_CODE", "failure.GENERATION_FAILED_CODE", "code.value",
             "ErrorCode.SOURCE_UNAVAILABLE.value"]
    for value in fixed:
        source = f"def failed(run, e):\n    pipeline.record_progress(session, 1, 'error', error={value})\n"
        assert sites_in(source) == [], source
    other = "def failed(run, e):\n    run.emit_funnel(distinct_id, EVENT, error=str(e))\n    record_progress(db, 1, 'x')\n"
    assert sites_in(other) == []
