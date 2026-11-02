#!/usr/bin/env python3
"""Rebuild in place the filings whose excerpt the regex fallback stored in the E28 window (E28 (b)).

From early October 2026 until #1350's backport deployed (2026-10-16 04:10Z), SEC refused edgartools'
filing index, every 10-K and 10-Q excerpt fell back to the regex extractor, and a stored excerpt is
reused for good (``summary_generation_service.get_or_cache_excerpt``). The founder decided on 2026-11-01
to replace those excerpts and the summaries built on them (tasks/todo.md E28 (b)).

The cohort: ``filing_content_cache`` rows on a 10-K, 10-K/A, 10-Q or 10-Q/A whose stored excerpt still opens
with a regex builder's bytes and that were created, or last written (``updated_at``, else ``created_at``), in
[2026-10-04 09:29Z, 2026-10-16 04:10Z). The window's marks and the builders' openings are
``ops/excerpts/source_cohort.sql``'s (a test pins them equal). Its ``excerpt-cohort`` run 41227616727
(2026-10-31) gives 15 by either reading: 14 rows created in the window, one created before it and last
written in it, and none created in it and last written after it. So ``EXPECTED_COHORT`` is 15: the apply
refuses any other count and writes nothing, and the dry run exits non-zero on one.

A row's last write moves with any update of the row. A forced regeneration that reuses the stored excerpt
(the route's Pro Regenerate, the stale drain) rewrites the row's other columns and keeps its regex excerpt.
That is why a row created in the window stays selected however late it was last written. A rebuilt
excerpt leaves on its own, because it no longer opens with a regex builder's bytes. A count other than
15 has a cause to find first: read ``excerpt-cohort``'s buckets before ``EXPECTED_COHORT`` moves in a
reviewed commit. The one row created before the window is selected by its last write alone, so a
regeneration of it since would leave its regex excerpt outside the cohort.

The rebuild deletes and clears nothing. Each filing goes through ``generate_summary_background(filing_id,
None, force_regenerate=True, rebuild_excerpt=True)``, the call ``precompute_service.precompute_one``
makes, which drains the one orchestrator. So:
- the stored summary is updated in place, keeping its id and every ``saved_summaries`` bookmark;
- keep-better keeps it when the new run ranks lower, and a failed run keeps it too;
- the new excerpt is stored only with a summary that replaces, in the same commit;
- no user is metered (``user_id`` None).

Deleting a summary for a lazy rebuild instead would leave the page blank. A GET never generates
(routers/summaries.py): only a signed-in viewer's generate-stream request would rebuild it, metered to that
viewer, and a guest would meet the signup gate meanwhile.

Output is counts only, JSON lines prefixed ``E28_REBUILD``: no filing id, accession, ticker or error text.
The apply prints one ``rebuilt``/``of``/``outcome`` line as each filing finishes, then the run's line with
the ``outcomes`` counts. The outcome classes split ``precompute_one``'s comparison of the summary's
(id, updated_at) before and after the run, and a replacement by the stored excerpt's opening:
- ``replaced``: the summary changed and its excerpt opens with a native section's label;
- ``replaced_regex``: the summary changed but the rebuilt excerpt is regex again (a size cap, a parse timeout
  or a thin parse; the cohort SQL cannot tell these from the 403);
- ``replaced_unclassified``: the summary changed and its excerpt opens with neither (the regex path's last
  resort, the cleaned document's head, or an unknown builder);
- ``replaced_without_excerpt``: the summary changed and the run stored no excerpt;
- ``kept``: keep-better kept the stored summary, and its regex excerpt stays;
- ``failed``: a terminal error event, or an exception in the run or in reading its result, whose text is
  withheld.

The apply refuses while ``SUMMARY_DURABLE_GENERATION_ENABLED`` is on, since the orchestrator refuses a
lease-less run then.

Only a task's first attempt runs. A non-zero exit, an out-of-memory kill or a task timeout makes Cloud Run
retry the task: the pregenerate job sets no ``--max-retries``, so its default of three applies
(docs/OPERATIONS.md). A kept or failed filing's cache row is left as it was, so a retry would select it again,
and when no filing was replaced the count guard would pass and every paid rebuild would run again under the
one approval. So an attempt whose ``CLOUD_RUN_TASK_ATTEMPT`` is set and is not ``0`` reads nothing, writes
nothing, prints a ``retry_attempt`` refusal and exits non-zero, and the execution fails. The record is the
first attempt's lines. A first attempt that was killed prints no ``outcomes`` line: its ``rebuilt`` lines
count what finished, and ``status.retriedCount`` and the container's log say why it stopped
(lessons/ops-bound-drain-batches-to-job-memory.md, whose cap of 15 regenerations an execution this run
meets).

Cost: about one paid model call per filing, about USD 0.005 each. Read the balance and reserve first.

Founder commands (the DB is reachable only from Cloud Run; .github/workflows/ops.yml runs these as
``rebuild-e28-excerpts-dry-run`` and ``rebuild-e28-excerpts-apply``, the apply behind ``approve-apply``).
The pregenerate job carries the model key and the SEC budget:
  gcloud run jobs execute earningsnerd-pregenerate --region=us-west1 \\
    --args=scripts/rebuild_e28_window_excerpts.py --wait             # dry run: counts only
  gcloud run jobs execute earningsnerd-pregenerate --region=us-west1 \\
    --args=scripts/rebuild_e28_window_excerpts.py,--apply --wait     # only after sign-off

Local usage:
  python scripts/rebuild_e28_window_excerpts.py            # dry run
  python scripts/rebuild_e28_window_excerpts.py --apply    # rebuild each filing of the cohort
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ops/excerpts/source_cohort.sql's marks: its last native eval report and #1350's deploy.
WINDOW_START = datetime(2026, 10, 4, 9, 29, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 10, 16, 4, 10, tzinfo=timezone.utc)
FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A"})
# excerpt-cohort run 41227616727 (2026-10-31): 13 10-Q, one 10-K and one 10-K/A.
EXPECTED_COHORT = 15
# The two regex builders' openings, as source_cohort.sql's CASE reads them (ai/extraction.py writes them).
REGEX_TARGETED_OPENING = "\n\n" + "=" * 50
REGEX_RECOVERED_OPENINGS = (
    "RISK & NARRATIVE CONTEXT (recovered from filing):\n",
    "FINANCIAL & MD&A CONTEXT (recovered from filing):\n",
)
REGEX_BUILDERS = frozenset({"regex_targeted", "regex_recovered"})
# A native excerpt's opening: one of _SECTION_LAYOUT's labels (ai/extraction.py), ":" and a newline, the
# labels source_cohort.sql's native arm lists. Literal here, as the regex openings are, because importing the
# extraction module would build the settings before the entry block skips Redis; a test pins them equal.
NATIVE_OPENINGS = (
    "ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\n",
    "ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n",
    "ITEM 1A - RISK FACTORS:\n",
    "ITEM 1 - FINANCIAL STATEMENTS:\n",
    "ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\n",
    "ITEM 18 - FINANCIAL STATEMENTS:\n",
    "ITEM 5 - OPERATING AND FINANCIAL REVIEW AND PROSPECTS:\n",
    "ITEM 3.D - RISK FACTORS:\n",
)
OPENING_CHARS = 64
OUTCOMES = ("replaced", "replaced_regex", "replaced_unclassified", "replaced_without_excerpt", "kept", "failed")
_REPLACED = {"native": "replaced", "regex_targeted": "replaced_regex", "regex_recovered": "replaced_regex",
             "unclassified": "replaced_unclassified", "none": "replaced_without_excerpt"}


def builder(opening: Optional[str]) -> str:
    """The builder an excerpt's first characters name, as source_cohort.sql's CASE does (its native arm also
    reads the row's age, which a rebuilt excerpt does not need)."""
    if not opening:
        return "none"
    if opening[:52] == REGEX_TARGETED_OPENING:
        return "regex_targeted"
    head = opening[:OPENING_CHARS]
    if head.startswith(REGEX_RECOVERED_OPENINGS):
        return "regex_recovered"
    if head.startswith(NATIVE_OPENINGS):
        return "native"
    return "unclassified"


def _in_window(column):
    return (column >= WINDOW_START) & (column < WINDOW_END)


def select_cohort(db) -> list[tuple[int, str, str, bool]]:
    """(filing_id, form, builder, created in the window) for each cohort row, in filing-id order."""
    from sqlalchemy import func, or_

    from app.models import Filing, FilingContentCache

    created = FilingContentCache.created_at
    last_write = func.coalesce(FilingContentCache.updated_at, created)
    rows = (
        db.query(FilingContentCache.filing_id, Filing.filing_type, created,
                 func.substr(FilingContentCache.critical_excerpt, 1, OPENING_CHARS))
        .join(Filing, Filing.id == FilingContentCache.filing_id)
        .filter(or_(_in_window(created), _in_window(last_write)))
        .order_by(FilingContentCache.filing_id)
        .all()
    )
    cohort = []
    for filing_id, filing_type, created_at, opening in rows:
        form = (filing_type or "").strip().upper()
        kind = builder(opening)
        if form in FORMS and kind in REGEX_BUILDERS:
            created_in = created_at is not None and WINDOW_START <= _aware(created_at) < WINDOW_END
            cohort.append((filing_id, form, kind, created_in))
    return cohort


def _aware(moment: datetime) -> datetime:
    """SQLite hands back the stored UTC instant naive; PostgreSQL's timestamptz comes back aware."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _summary_stamp(session_factory, filing_id: int):
    from app.models import Summary

    with session_factory() as db:
        row = db.query(Summary.id, Summary.updated_at).filter(Summary.filing_id == filing_id).first()
    return None if row is None else tuple(row)


def _stored_opening(session_factory, filing_id: int) -> Optional[str]:
    from sqlalchemy import func

    from app.models import FilingContentCache

    with session_factory() as db:
        return (
            db.query(func.substr(FilingContentCache.critical_excerpt, 1, OPENING_CHARS))
            .filter(FilingContentCache.filing_id == filing_id)
            .scalar()
        )


async def rebuild_one(filing_id: int, session_factory, generate) -> str:
    """One filing's forced rebuild and its outcome class, from precompute_one's comparison of the summary's
    (id, updated_at) before and after the run."""
    from app.services.summary_refresh import generation_failed

    try:
        stored = _summary_stamp(session_factory, filing_id)
        outcome = await generate(filing_id, None, force_regenerate=True, rebuild_excerpt=True)
        summary = _summary_stamp(session_factory, filing_id)
        if summary is None or outcome is None or generation_failed(outcome):
            return "failed"
        # The in-place UPDATE stamps updated_at, so an unchanged (id, updated_at) was not replaced.
        if stored is not None and summary == stored:
            return "kept"
        kind = builder(_stored_opening(session_factory, filing_id))
    except Exception:  # noqa: BLE001 - the orchestrator converts errors to events; anything else is a failure
        return "failed"
    return _REPLACED[kind]


def first_attempt(env: Mapping[str, str]) -> bool:
    """Whether this is a task's first attempt: Cloud Run sets ``CLOUD_RUN_TASK_ATTEMPT`` from 0, and a local run
    sets none. Any other value, an unreadable one included, counts as a retry."""
    return env.get("CLOUD_RUN_TASK_ATTEMPT", "0") == "0"


def run(args: argparse.Namespace, emit: Callable[[dict[str, Any]], None], *,
        session_factory=None, generate=None, env: Mapping[str, str] = os.environ) -> int:
    """Select the cohort, report it, and on --apply rebuild each filing; return the exit code."""
    mode = "apply" if args.apply else "dry_run"
    if not first_attempt(env):
        emit({"mode": mode, "expected": EXPECTED_COHORT, "refused": "retry_attempt"})
        return 2

    from app.config import settings
    from app.models import Summary
    from app.utils.datetimes import iso_z

    if session_factory is None:
        from app.database import SessionLocal as session_factory
    if generate is None:
        from app.services.summary_generation_service import generate_summary_background as generate

    with session_factory() as db:
        cohort = select_cohort(db)
        ids = [filing_id for filing_id, _, _, _ in cohort]
        with_summary = db.query(Summary.filing_id).filter(Summary.filing_id.in_(ids)).count() if ids else 0
    durable = bool(settings.SUMMARY_DURABLE_GENERATION_ENABLED)
    report: dict[str, Any] = {
        "mode": mode,
        "window": [iso_z(WINDOW_START), iso_z(WINDOW_END)],
        "expected": EXPECTED_COHORT,
        "cohort": len(cohort),
        "created_in_window": sum(1 for *_, created_in in cohort if created_in),
        "by_form": dict(sorted(Counter(form for _, form, _, _ in cohort).items())),
        "by_builder": dict(sorted(Counter(kind for _, _, kind, _ in cohort).items())),
        "with_summary": with_summary,
        "durable_generation": durable,
    }
    if len(cohort) != EXPECTED_COHORT:
        report["refused"] = "cohort_differs_from_expected"
        emit(report)
        return 2
    if not args.apply:
        emit(report)
        return 0
    if durable:
        report["refused"] = "durable_generation_enabled"
        emit(report)
        return 2

    async def rebuild_all() -> Counter:
        counts: Counter = Counter()
        for done, filing_id in enumerate(ids, start=1):  # one at a time: one model call and one SEC fetch in flight
            outcome = await rebuild_one(filing_id, session_factory, generate)
            counts[outcome] += 1
            # Printed as each filing finishes, so an attempt killed partway still counts what ran.
            emit({"mode": mode, "rebuilt": done, "of": len(ids), "outcome": outcome})
        return counts

    counts = asyncio.run(rebuild_all())
    report["outcomes"] = {name: counts.get(name, 0) for name in OUTCOMES}
    emit(report)
    return 1 if counts.get("failed") else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the E28 window's regex-excerpt filings in place (dry run).")
    parser.add_argument("--apply", action="store_true", help="Rebuild each filing of the cohort (default: dry run).")
    return parser


def main(argv: list[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    args = build_parser().parse_args(argv)

    def emit(report: dict[str, Any]) -> None:
        print("E28_REBUILD " + json.dumps(report, sort_keys=True), flush=True)

    return run(args, emit, env=env)


if __name__ == "__main__":
    # The pregenerate job's other scripts start the same way: the ai_call spend reads as the job's, the provenance
    # and spend lines (INFO) reach the job's Cloud Run logs, and Redis, which production does not run, is skipped.
    import logging

    os.environ.setdefault("SKIP_REDIS_INIT", "true")  # before any app import builds the settings
    from app.services import ai_metrics

    ai_metrics.set_trigger("job")
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
