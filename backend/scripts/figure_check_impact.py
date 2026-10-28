#!/usr/bin/env python3
"""Count what the strict figure check changes for stored summaries (E184; read-only, counts only).

#1530 replaced the figure chip's substring check (a row read "Matches filing" when its current-period
text contained any rendering of the filed value) with the strict check, ``provenance_service.
build_metric_source``: scale, both years, the label's own filed line and, since E184, the fact's own
filing. This counts, over an explicit cohort of stored summaries, what that changes on each financial
highlights row, read as the summary page reads it (``enrich_financial_highlights`` on the filing's stored
XBRL, ``standardized_xbrl``):

- ``transitions``: each row's label under the old check -> under the strict one. The old labels are
  ``matched``, ``unmatched`` (checked, not found) and ``unchecked``; the strict ones add ``replaced`` (a
  figure that differed is shown as filed). A no-total bank's revenue row, which both checks drop from the
  page, counts as ``dropped->dropped``.
- ``swapped_fields``: how many current- and prior-period figures the strict check replaced.
- ``withheld_takeaways``: takeaways withheld beside a replaced figure.
- ``unavailable``: summaries with nothing to count, by reason (no filing XBRL, no highlights table);
  ``unreadable``: summaries whose stored data the check could not read, counted, never guessed.

Output is one JSON object of aggregate counts: no filing text, prompt, summary body, identifier or
setting. Nothing is written and no model is called: every statement the session runs must start with
SELECT (anything else raises before it reaches the database), on PostgreSQL its transaction is also READ
ONLY, and the session is rolled back at the end. A summary counts whole or not at all: one that cannot be
read adds nothing but its ``unreadable`` count.
The script exits 1 when any summary in the cohort was unreadable, or when an id ``--summary-ids`` names
is missing, so a partial count is never read as a whole one; a range's absent ids (deleted or never made)
are its ordinary gaps, reported as ``missing`` with ``range`` true and no failure.

The cohort is explicit and bounded: ``--summary-ids`` (comma- or space-separated), or ``--from-id`` with
``--to-id`` spanning at most ``MAX_COHORT`` ids, never both. A live count is run only through the approved
read-only operations path (Agent E), never against production from a laptop.

Local usage:
  python scripts/figure_check_impact.py --summary-ids 101,102,103
  python scripts/figure_check_impact.py --from-id 1 --to-id 2000
"""
import argparse
import copy
import json
import os
import sys
from collections import Counter
from typing import Any, Iterable, Optional

# Make the backend root importable as `app.*` when run directly (see retention_purge.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAX_COHORT = 5000
_PERIOD_FIELDS = ("current_period", "prior_period")


def _value_appears_in_text(value: float, text_lower: str) -> bool:
    """The retired substring check, copied from ``provenance_service`` before #1530 (751ce417^).

    Whether an XBRL float value appears in text, in common renderings (billions/millions/grouped)."""
    if not text_lower:
        return False
    av = abs(value)
    candidates: set[str] = set()
    if av >= 1e9:
        for d in range(0, 4):  # "383", "383.3", "383.29", "383.285"
            candidates.add(f"{av / 1e9:.{d}f}")
    if av >= 1e6:
        for d in range(0, 4):  # grouped + ungrouped millions
            candidates.add(f"{av / 1e6:.{d}f}")
            candidates.add(f"{av / 1e6:,.{d}f}")
    candidates.add(f"{int(round(av)):,}")
    return any(c in text_lower for c in candidates if len(c.replace(",", "")) >= 2)


def old_label(row: dict, xbrl_standardized: dict) -> str:
    """A row's label under the retired check (``build_metric_source`` before #1530)."""
    from app.services import provenance_service as prov

    mapping = prov.map_metric_to_xbrl_key(row.get("metric"))
    if not mapping:
        return "unchecked"
    entry = xbrl_standardized.get(mapping[0])
    current = entry.get("current") if isinstance(entry, dict) else None
    value = current.get("value") if isinstance(current, dict) else None
    if not isinstance(value, (int, float)) or abs(value) < prov._MIN_VERIFIABLE_XBRL_VALUE:
        return "unchecked"
    displayed = str(row.get("current_period") or "").lower()
    return "matched" if _value_appears_in_text(float(value), displayed) else "unmatched"


def new_label(row: dict) -> str:
    """A row's label once ``enrich_financial_highlights`` has run the strict check on it."""
    if row.get("source_replaced"):
        return "replaced"
    if row.get("source_verified") is True:
        return "matched"
    return "unmatched" if row.get("source_checkable") is True else "unchecked"


def highlights_of(summary: Any) -> Optional[dict]:
    """The highlights block the page reads: the stored sections' (``results_that_matter`` from schema 2), else the
    compatibility column."""
    raw = getattr(summary, "raw_summary", None)
    if isinstance(raw, dict) and isinstance(raw.get("sections"), dict):
        try:
            version = int(raw.get("schema_version") or 1)
        except (TypeError, ValueError):
            version = 1
        block = raw["sections"].get("results_that_matter" if version >= 2 else "financial_highlights")
        if isinstance(block, dict) and isinstance(block.get("table"), list):
            return block
    block = getattr(summary, "financial_highlights", None)
    return block if isinstance(block, dict) and isinstance(block.get("table"), list) else None


def guard_read_only(session: Any) -> None:
    """Refuse every statement but a SELECT on this session, before it reaches the database, and any flush.

    The guard sits on the connection the session's transaction holds (the session is never committed, so it
    keeps that connection until it is rolled back), not on the engine other sessions share. The ORM reads
    here never open with a CTE, so a ``WITH`` (which may carry a write) is refused too; on PostgreSQL the
    transaction is READ ONLY besides, so the database refuses what the guard might miss."""
    from sqlalchemy import event, text

    connection = session.connection()
    if connection.dialect.name == "postgresql":
        connection.execute(text("SET TRANSACTION READ ONLY"))

    def refuse_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
        verb = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""
        if verb != "SELECT":
            raise RuntimeError(f"figure_check_impact is read-only; refused a {verb or 'blank'} statement")

    def refuse_flush(*_args):
        raise RuntimeError("figure_check_impact is read-only; refused a flush")

    event.listen(connection, "before_cursor_execute", refuse_writes)
    event.listen(session, "before_flush", refuse_flush)


def _count_summary(block: dict, filing: Any, standardized: Any) -> tuple[Counter, Counter, int]:
    """One summary's transitions, swapped fields and withheld takeaways; raises on what it cannot read."""
    from app.services import provenance_service as prov

    transitions: Counter = Counter()
    swapped: Counter = Counter()
    withheld = 0
    originals = [copy.deepcopy(row) for row in block["table"] if isinstance(row, dict)]
    enriched = prov.enrich_financial_highlights(block, filing, standardized)
    # Rows keep their order. For a no-total bank the page drops a revenue row, as the retired check's enrichment
    # did (751ce417^), so both labels read dropped.
    bank = prov._is_no_total_bank(standardized)
    enriched_rows = iter([row for row in enriched["table"] if isinstance(row, dict)])
    for original in originals:
        if bank and (prov.map_metric_to_xbrl_key(original.get("metric")) or (None,))[0] == "revenue":
            transitions[("dropped", "dropped")] += 1
            continue
        row = next(enriched_rows)
        transitions[(old_label(original, standardized), new_label(row))] += 1
        for field in (row.get("source_replaced") or {}):
            if field in _PERIOD_FIELDS:
                swapped[field] += 1
        withheld += row.get("commentary_withheld") == "figure_replaced"
    return transitions, swapped, withheld


def count_impact(session: Any, summary_ids: Iterable[int], *, id_range: bool = False) -> dict[str, Any]:
    """Aggregate counts for the cohort; reads only, through ``session``. ``id_range`` says the ids span a range,
    whose absent ids are gaps rather than missing names."""
    from sqlalchemy.orm import joinedload

    from app.models import Summary
    from app.services.edgar.compat import xbrl_service

    wanted = sorted(set(summary_ids))
    transitions: Counter = Counter()
    swapped: Counter = Counter()
    unavailable: Counter = Counter()
    withheld = rows_counted = summaries_counted = unreadable = 0
    found = 0
    for start in range(0, len(wanted), 200):
        batch = wanted[start:start + 200]
        summaries = (
            session.query(Summary).options(joinedload(Summary.filing))
            .filter(Summary.id.in_(batch)).order_by(Summary.id).all()
        )
        found += len(summaries)
        for summary in summaries:
            try:
                filing = summary.filing
                block = highlights_of(summary)
                if block is None:
                    unavailable["no_highlights_table"] += 1
                    continue
                if filing is None or not filing.xbrl_data:
                    unavailable["no_filing_xbrl"] += 1
                    continue
                counted = _count_summary(block, filing, xbrl_service.extract_standardized_metrics(filing.xbrl_data))
            except Exception:  # noqa: BLE001 — an unreadable sample is counted, never guessed at
                unreadable += 1
                continue
            # Merged only once the whole summary has been read, so a failure part-way adds no row of it.
            row_transitions, row_swapped, row_withheld = counted
            transitions.update(row_transitions)
            swapped.update(row_swapped)
            withheld += row_withheld
            rows_counted += sum(row_transitions.values())
            summaries_counted += 1
    return {
        "cohort": {"requested": len(wanted), "found": found, "missing": len(wanted) - found, "range": id_range},
        "summaries_counted": summaries_counted,
        "rows_counted": rows_counted,
        "transitions": {f"{old}->{new}": n for (old, new), n in sorted(transitions.items())},
        "swapped_fields": dict(sorted(swapped.items())),
        "withheld_takeaways": withheld,
        "unavailable": dict(sorted(unavailable.items())),
        "unreadable": unreadable,
    }


def parse_cohort(args: argparse.Namespace) -> list[int]:
    """The explicit, bounded cohort the arguments name; raises ValueError otherwise. A range is the one
    ``--from-id``/``--to-id`` name when ``--summary-ids`` is absent."""
    if args.summary_ids and (args.from_id is not None or args.to_id is not None):
        raise ValueError("name one cohort: --summary-ids, or --from-id with --to-id, not both")
    if args.summary_ids:
        ids = [int(part) for value in args.summary_ids for part in value.split(",") if part.strip()]
    elif args.from_id is not None and args.to_id is not None:
        if args.to_id < args.from_id:
            raise ValueError("--to-id is before --from-id")
        ids = list(range(args.from_id, args.to_id + 1))
    else:
        raise ValueError("name a cohort: --summary-ids, or --from-id with --to-id")
    if not ids or len(ids) > MAX_COHORT:
        raise ValueError(f"a cohort holds 1 to {MAX_COHORT} summaries")
    return ids


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summary-ids", nargs="+")
    parser.add_argument("--from-id", type=int)
    parser.add_argument("--to-id", type=int)
    args = parser.parse_args(argv)
    try:
        cohort = parse_cohort(args)
    except ValueError as exc:
        parser.error(str(exc))

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        guard_read_only(session)
        report = count_impact(session, cohort, id_range=not args.summary_ids)
    finally:
        session.rollback()
        session.close()
    print(json.dumps(report, sort_keys=True))
    named_but_missing = report["cohort"]["missing"] and not report["cohort"]["range"]
    return 1 if report["unreadable"] or named_but_missing else 0


if __name__ == "__main__":
    sys.exit(main())
