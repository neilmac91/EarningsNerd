#!/usr/bin/env python3
"""Rebuild in place the filings whose excerpt the regex fallback stored in the E28 window (E28 (b)).

From early October 2026 until #1350's backport deployed (2026-10-16 04:10Z), SEC refused edgartools'
filing index, every 10-K and 10-Q excerpt fell back to the regex extractor, and a stored excerpt is
reused for good (``summary_generation_service.get_or_cache_excerpt``). The founder decided on 2026-11-01
to replace those excerpts and the summaries built on them (tasks/todo.md E28 (b)).

The cohort: ``filing_content_cache`` rows on a 10-K, 10-K/A, 10-Q or 10-Q/A whose last write (``updated_at``,
else ``created_at``) falls in [2026-10-04 09:29Z, 2026-10-16 04:10Z) and whose stored excerpt still opens
with a regex builder's bytes. The window's marks and the builder openings are
``ops/excerpts/source_cohort.sql``'s (a test pins them equal). Its ``excerpt-cohort`` run 41227616727
(2026-10-31) counted 15, so ``EXPECTED_COHORT`` is 15: the apply refuses any other count and writes
nothing, and the dry run exits non-zero on one. A filing rebuilt since drops out on its own, because its
excerpt no longer opens with a regex builder's bytes; the constant then moves in a reviewed commit.

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

Output is counts only, one JSON line prefixed ``E28_REBUILD``: no filing id, accession, ticker or error text.
The outcome per filing, in the classes ``precompute_one`` reports:
- ``replaced``: the summary changed and its excerpt no longer opens as a regex build;
- ``replaced_regex``: the summary changed but the rebuilt excerpt is regex again (a size cap, a parse timeout
  or a thin parse; the cohort SQL cannot tell these from the 403);
- ``replaced_without_excerpt``: the summary changed and the run stored no excerpt;
- ``kept``: keep-better kept the stored summary, and its regex excerpt stays;
- ``failed``: a terminal error event, or an exception, whose text is withheld.

The apply refuses while ``SUMMARY_DURABLE_GENERATION_ENABLED`` is on, since the orchestrator refuses a
lease-less run then.

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
from typing import Any, Callable, Optional

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ops/excerpts/source_cohort.sql's marks: its last native eval report and #1350's deploy.
WINDOW_START = datetime(2026, 10, 4, 9, 29, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 10, 16, 4, 10, tzinfo=timezone.utc)
FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A"})
# excerpt-cohort run 41227616727 (2026-10-31): 13 10-Q, one 10-K and one 10-K/A, by last write.
EXPECTED_COHORT = 15
# The two regex builders' openings, as source_cohort.sql's CASE reads them (ai/extraction.py writes them).
REGEX_TARGETED_OPENING = "\n\n" + "=" * 50
REGEX_RECOVERED_OPENINGS = (
    "RISK & NARRATIVE CONTEXT (recovered from filing):\n",
    "FINANCIAL & MD&A CONTEXT (recovered from filing):\n",
)
REGEX_BUILDERS = frozenset({"regex_targeted", "regex_recovered"})
OPENING_CHARS = 64
OUTCOMES = ("replaced", "replaced_regex", "replaced_without_excerpt", "kept", "failed")


def builder(opening: Optional[str]) -> str:
    """The builder an excerpt's first characters name, as source_cohort.sql's CASE does for the regex ones."""
    if not opening:
        return "none"
    if opening[:52] == REGEX_TARGETED_OPENING:
        return "regex_targeted"
    if opening[:OPENING_CHARS].startswith(REGEX_RECOVERED_OPENINGS):
        return "regex_recovered"
    return "other"


def select_cohort(db) -> list[tuple[int, str, str]]:
    """(filing_id, form, builder) for each cohort row, in filing-id order."""
    from sqlalchemy import func

    from app.models import Filing, FilingContentCache

    last_write = func.coalesce(FilingContentCache.updated_at, FilingContentCache.created_at)
    rows = (
        db.query(FilingContentCache.filing_id, Filing.filing_type,
                 func.substr(FilingContentCache.critical_excerpt, 1, OPENING_CHARS))
        .join(Filing, Filing.id == FilingContentCache.filing_id)
        .filter(last_write >= WINDOW_START, last_write < WINDOW_END)
        .order_by(FilingContentCache.filing_id)
        .all()
    )
    cohort = []
    for filing_id, filing_type, opening in rows:
        form = (filing_type or "").strip().upper()
        kind = builder(opening)
        if form in FORMS and kind in REGEX_BUILDERS:
            cohort.append((filing_id, form, kind))
    return cohort


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
    """One filing's forced rebuild and its outcome, classified as precompute_one classifies a forced run."""
    from app.services.summary_refresh import generation_failed

    stored = _summary_stamp(session_factory, filing_id)
    try:
        outcome = await generate(filing_id, None, force_regenerate=True, rebuild_excerpt=True)
    except Exception:  # noqa: BLE001 - the orchestrator converts errors to events; anything else is a failure
        return "failed"
    summary = _summary_stamp(session_factory, filing_id)
    if summary is None or outcome is None or generation_failed(outcome):
        return "failed"
    # The in-place UPDATE stamps updated_at, so an unchanged (id, updated_at) was not replaced.
    if stored is not None and summary == stored:
        return "kept"
    kind = builder(_stored_opening(session_factory, filing_id))
    if kind == "none":
        return "replaced_without_excerpt"
    return "replaced_regex" if kind in REGEX_BUILDERS else "replaced"


def run(args: argparse.Namespace, emit: Callable[[dict[str, Any]], None], *,
        session_factory=None, generate=None) -> int:
    """Select the cohort, report it, and on --apply rebuild each filing; return the exit code."""
    from app.config import settings
    from app.models import Summary

    if session_factory is None:
        from app.database import SessionLocal as session_factory
    if generate is None:
        from app.services.summary_generation_service import generate_summary_background as generate

    with session_factory() as db:
        cohort = select_cohort(db)
        ids = [filing_id for filing_id, _, _ in cohort]
        with_summary = db.query(Summary.filing_id).filter(Summary.filing_id.in_(ids)).count() if ids else 0
    durable = bool(settings.SUMMARY_DURABLE_GENERATION_ENABLED)
    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry_run",
        "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "expected": EXPECTED_COHORT,
        "cohort": len(cohort),
        "by_form": dict(sorted(Counter(form for _, form, _ in cohort).items())),
        "by_builder": dict(sorted(Counter(kind for _, _, kind in cohort).items())),
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
        for filing_id in ids:  # one at a time: one model call and one SEC fetch in flight
            counts[await rebuild_one(filing_id, session_factory, generate)] += 1
        return counts

    counts = asyncio.run(rebuild_all())
    report["outcomes"] = {name: counts.get(name, 0) for name in OUTCOMES}
    emit(report)
    return 1 if counts.get("failed") else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the E28 window's regex-excerpt filings in place (dry run).")
    parser.add_argument("--apply", action="store_true", help="Rebuild each filing of the cohort (default: dry run).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(report: dict[str, Any]) -> None:
        print("E28_REBUILD " + json.dumps(report, sort_keys=True), flush=True)

    return run(args, emit)


if __name__ == "__main__":
    sys.exit(main())
