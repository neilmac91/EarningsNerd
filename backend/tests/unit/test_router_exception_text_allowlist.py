"""Structural gate: a router never builds an ``HTTPException`` detail from the exception it caught.

``GET /api/companies/{ticker}`` and ``GET /api/filings/company/{ticker}`` answered an unexpected failure with
``detail=f"Error fetching company: {str(e)}"``: a database or driver error's text (its SQL, its parameters) went to an
unauthenticated caller in every environment, past ``main.global_exception_handler``, which hides ``str(exc)`` in
production. A route logs the error with ``logger.exception`` and answers a fixed detail.

An AST walk over ``app/routers/**/*.py`` finds every call to ``HTTPException`` or a class named for it (any callee
whose name ends in ``HTTPException``: ``CodedHTTPException``, which ``app/api_errors.py`` has routers raise in its
place, takes its detail in the same second position) inside an ``except ... as <name>:`` whose detail (the ``detail=``
keyword or the second positional argument) is built from ``<name>``: in an f-string, in a ``+`` or ``%`` expression (a
tuple or dict on the right of ``%`` included), as an argument to ``.format``, ``str()`` or ``repr()``, or the bare
name. Each (file, enclosing function) holding such a site is listed below with its count and why it stays; the counts
are equalities (lessons/test-allowlist-caps-are-equalities.md), so a new site fails and a removed one must lower its
count.

Not covered: a detail built from the caught exception in a variable first, or from an attribute of it (``exc.detail``,
``exc.args``); one built without naming it (``traceback.format_exc()``, ``sys.exc_info()``, a handler with no
``as``); a 500 handled by ``JSONResponse`` rather than ``HTTPException``; an exception class whose name does not end
in ``HTTPException``.
"""
from pathlib import Path

from tests.support.caught_exception_text import calls_in, name_of, uses_caught_text

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# (file relative to backend/, enclosing function) -> (sites, why the caught exception's text may be the detail).
ALLOWED: dict[tuple[str, str], tuple[int, str]] = {
    ("app/routers/analysis.py", "get_dataset.dataset_for_reader"): (
        1, "the 400 carries build_dataset's ValueError messages (period range, mode, period key) to a Pro reader",
    ),
    ("app/routers/analysis.py", "export_analysis_xlsx.dataset_for_export"): (
        2, "the 400s carry build_dataset's ValueError and IncompatibleUnitsError messages to a Pro reader",
    ),
    ("app/routers/feedback.py", "submit_feedback_with_attachments"): (
        1, "the 422 carries FeedbackImageError's fixed code (format, animation, dimensions, input_size, ...), never "
           "a library's text",
    ),
    ("app/routers/auth.py", "_require_new_collection"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/auth.py", "register"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/auth.py", "google_start"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/auth.py", "apple_start"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/admin.py", "create_free_account"): (
        1, "high-risk file, admin only: the 409 carries AccountInvitationRequired's message; not changed here",
    ),
    ("app/routers/internal.py", "_enqueue_durable"): (
        1, "high-risk file, cron token only: the 400 carries enqueue_internal_job's ValueError; not changed here",
    ),
    ("app/routers/summaries.py", "generate_summary_stream"): (
        1, "high-risk file: the coded refusal carries SummaryJobUnavailable's message, a sentence summary_job_store "
           "writes for the reader (its docstring: a safe typed route refusal); not changed here",
    ),
}


def sites_in(source: str) -> list[tuple[str, int]]:
    """(enclosing function, lineno) of each HTTPException in ``source`` whose detail is built from a caught exception."""
    hits = []
    for scope, caught, call in calls_in(source):
        if not caught or not name_of(call.func).endswith("HTTPException"):
            continue
        details = [keyword.value for keyword in call.keywords if keyword.arg == "detail"] + call.args[1:2]
        if any(uses_caught_text(detail, name) for detail in details for name in caught):
            hits.append((scope, call.lineno))
    return hits


def test_router_details_built_from_a_caught_exception_match_the_allowlist():
    found: dict[tuple[str, str], list[int]] = {}
    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        relative = path.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in sites_in(path.read_text(encoding="utf-8")):
            found.setdefault((relative, scope), []).append(lineno)

    unlisted = {key: lines for key, lines in found.items() if key not in ALLOWED}
    assert not unlisted, (
        "A router builds an HTTPException detail from the exception it caught, which sends the error's text "
        "(SQL, parameters, provider bodies) to the caller. Log it with logger.exception and answer a fixed detail: "
        + ", ".join(f"{file}:{lines} in {scope}" for (file, scope), lines in sorted(unlisted.items()))
    )
    counts = {key: len(lines) for key, lines in found.items()}
    expected = {key: count for key, (count, _reason) in ALLOWED.items()}
    assert counts == expected, (
        "A listed site's count changed or it is gone; lower or remove its entry in ALLOWED: "
        f"found {dict(sorted(counts.items()))}"
    )


def test_each_form_of_a_detail_built_from_the_caught_exception_is_found():
    forms = [
        'f"Error: {exc}"',
        'f"Error: {str(exc)}"',
        'f"Error: {repr(exc)}"',
        '"Error: " + str(exc)',
        '"Error: %s" % exc',
        '"Error: %s" % (exc,)',
        '"%s: %s" % (label, exc)',
        '"%(error)s" % {"error": exc}',
        '"Error: {}".format(exc)',
        '"Error: {e}".format(e=exc)',
        "str(exc)",
        "repr(exc)",
        "exc",
    ]
    for form in forms:
        for call in (
            f"HTTPException(status_code=500, detail={form})", f"HTTPException(500, {form})",
            f"CodedHTTPException(ErrorCode.JOB_UNAVAILABLE, {form})", f"status.HTTPException(500, detail={form})",
        ):
            source = f"def route():\n    try:\n        pass\n    except Exception as exc:\n        raise {call} from exc\n"
            assert sites_in(source) == [("route", 5)], call


def test_a_fixed_detail_or_a_detail_outside_the_handler_is_not_found():
    fixed = (
        "def route(name):\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as exc:\n"
        "        logger.exception('failed')\n"
        "        raise HTTPException(status_code=500, detail='We could not load this.') from exc\n"
        "    raise HTTPException(status_code=404, detail=f'No {name}')\n"
    )
    assert sites_in(fixed) == []
