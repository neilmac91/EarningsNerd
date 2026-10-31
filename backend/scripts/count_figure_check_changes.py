#!/usr/bin/env python3
"""Count what the strict figure check changes for the stored summaries (E184, part 1; #1530).

#1530 replaced the figure check behind the Financial Highlights chips. Main's check matched a row by a
substring of its label and looked for the filed value's digits in the current period's text, so
"$416.2M" and "$416.9B" both read as matching Apple's $416,161M and the prior period was never read.
The strict check (``provenance_service.build_metric_source``) maps the whole label, reads the scale,
the currency and both periods, and where a checkable figure differs from the filed line its label
names, read-time enrichment shows the filed figure and withholds a takeaway that stated the old one.
Nothing is stored, so the deploy changed what every stored summary shows at once. This one-off says
how much: it runs both checks over every stored summary's highlights rows, as the page reads them, and
prints counts only.

Read-only. It opens one session, reads ``summaries`` joined to ``filings`` (``raw_summary``,
``xbrl_data``) a page at a time, each page in a transaction of its own so a read's shared lock lasts a
page, computes in memory and writes nothing; the Ops step that runs it (`.github/workflows/ops.yml`,
``figure-check-count``) also sets the session read-only through PGOPTIONS, as the relabel's dry run
does, and reads that back before the script starts.

What it prints: one JSON object, then the same as lines.
- ``summaries``, ``summaries_with_rows``, ``summaries_without_a_table``, ``summaries_without_xbrl``,
  ``summaries_xbrl_failed``, ``rows``, ``rows_by_container``: the population. A summary's rows are its
  raw summary's table (v2 ``results_that_matter``, v1 ``financial_highlights``), the rows the page
  renders; a summary with no such table has none here, the legacy ``financial_highlights`` column
  included, which the page never draws. A row with no metric label, which the renderer skips, is
  skipped; a row of a no-total bank's conflated "Revenue" line, which both checks' enrichment drops, is
  counted in ``rows_dropped_no_total_bank`` and read by neither. A filing whose XBRL fails to
  standardize counts under ``summaries_xbrl_failed``, apart from one with none stored.
- ``transitions``: ``old -> new`` per row, where old is main's label (``matched`` or ``linked``) and new
  is the strict check's (``matched``, ``linked``, or ``swapped``, a figure replaced by the filed one);
  ``transitions_by_form`` splits them by the filing's form.
- ``swapped_fields``: which period a swapped row replaces; ``takeaways_withheld``: swapped rows whose
  takeaway stated a figure; ``summaries_with_a_swap``, ``summaries_losing_a_match`` and
  ``summaries_gaining_a_match``: how many summaries each class touches.
No row content, label, figure, ticker or id is printed: the page's own XBRL read logs a filing's id when its
standardization fails, so this count standardizes with a read of its own that logs nothing.

Main's check is copied below as it stood at ae2a7844, the merge base of #1530 (``_value_appears_in_text``
and the body of its ``build_metric_source``), so the old label is computed from the same code that
served it; ``map_metric_to_xbrl_key``, which it read the label with, is still the module's.

Usage, from backend/ with ``DATABASE_URL`` set:  python scripts/count_figure_check_changes.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import provenance_service as prov  # noqa: E402
from app.services.summary_sections import _clean  # noqa: E402

# Main's threshold, the module's then as now: only large dollar figures were ever checked.
_OLD_MIN_VERIFIABLE_XBRL_VALUE = prov._MIN_VERIFIABLE_XBRL_VALUE


def _value_appears_in_text(value: float, text_lower: str) -> bool:
    """Main's substring check before #1530, verbatim: whether an XBRL float value appears in text, in
    common renderings (billions/millions/grouped), without reading the displayed scale."""
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


def old_label(row: dict[str, Any], xbrl_standardized: Optional[dict]) -> str:
    """The label main's ``build_metric_source`` gave the row before #1530: ``matched`` when a substring of
    its label mapped a concept whose filed value (at least $1M) appears in its current period's text,
    else ``linked`` (main's "Cited", checkable or not)."""
    mapping = prov.map_metric_to_xbrl_key(row.get("metric"))
    if not mapping or not isinstance(xbrl_standardized, dict):
        return "linked"
    key, _label = mapping
    entry = xbrl_standardized.get(key)
    current = entry.get("current") if isinstance(entry, dict) else None
    value = current.get("value") if isinstance(current, dict) else None
    if not isinstance(value, (int, float)) or abs(value) < _OLD_MIN_VERIFIABLE_XBRL_VALUE:
        return "linked"
    displayed = str(row.get("current_period") or "").lower()
    return "matched" if _value_appears_in_text(float(value), displayed) else "linked"


def new_outcome(
    row: dict[str, Any], filing: Any, xbrl_standardized: Optional[dict], section_ref: Optional[str]
) -> tuple[str, tuple[str, ...], bool]:
    """What the strict check does with the row: its label (``matched``, ``linked`` or ``swapped``), the
    periods a swap replaces, and whether the swap withholds the takeaway (it stated a figure). The check
    reads the row's label and its two period cells alone, so a stored row's own evidence keys cannot
    decide anything here, as they cannot on the page."""
    source = prov.build_metric_source(row, filing, xbrl_standardized, section_ref)
    mismatched = tuple(source.get("source_mismatched") or ())
    if mismatched:
        commentary = row.get("commentary")
        withheld = isinstance(commentary, str) and prov._states_a_figure(commentary)
        return "swapped", mismatched, withheld
    return ("matched" if source["source_verified"] else "linked"), (), False


def highlight_rows(summary: Any) -> tuple[list[dict[str, Any]], Optional[str], str]:
    """The highlights rows the page renders for a summary, their block's section ref, and which
    container held them: the raw summary's v2 or v1 table, or none. The legacy ``financial_highlights``
    column is never drawn (the page renders ``rendered_sections``, built from the raw summary alone), so
    a summary with no raw table has no rows here."""
    raw = prov._summary_raw_container(summary)
    sections = raw.get("sections") if isinstance(raw, dict) else None
    version = 1
    if isinstance(raw, dict):
        try:
            version = int(raw.get("schema_version") or 1)
        except (TypeError, ValueError):
            version = 1
    container = "results_that_matter" if version >= 2 else "financial_highlights"
    block = sections.get(container) if isinstance(sections, dict) else None
    if not (isinstance(block, dict) and isinstance(block.get("table"), list)):
        return [], None, "none"
    section_ref = block.get("source_section_ref") or block.get("sourceSectionRef")
    # The renderer skips a row that is not a dict or names no metric (``summary_sections._metrics_block``).
    return [row for row in block["table"] if isinstance(row, dict) and _clean(row.get("metric"))], section_ref, container


def filed_xbrl(filing: Any) -> tuple[Optional[dict], str]:
    """The filing's standardized XBRL, as ``provenance_service.standardized_xbrl`` reads it for the page, and
    why there is none: ``ok``, ``no_data`` (none stored, or nothing standardized) or ``failed``. The page's
    read logs the filing's id on a failure; this one logs nothing."""
    data = getattr(filing, "xbrl_data", None)
    if not data:
        return None, "no_data"
    try:
        from app.services.edgar.compat import xbrl_service

        standardized = xbrl_service.extract_standardized_metrics(data)
    except Exception:  # noqa: BLE001 - the page continues past a failed standardization; so does the count
        return None, "failed"
    return (standardized, "ok") if standardized else (None, "no_data")


def _is_conflated_bank_revenue(row: dict[str, Any]) -> bool:
    return (prov.map_metric_to_xbrl_key(row.get("metric")) or (None,))[0] == "revenue"


def count_summary(summary: Any, filing: Any, counts: dict[str, Any]) -> None:
    """Add one summary's rows to ``counts``."""
    counts["summaries"] += 1
    rows, section_ref, container = highlight_rows(summary)
    if not rows:
        counts["summaries_without_a_table"] += 1
        return
    counts["summaries_with_rows"] += 1
    xbrl, state = filed_xbrl(filing)
    if state == "failed":
        counts["summaries_xbrl_failed"] += 1
    elif xbrl is None:
        counts["summaries_without_xbrl"] += 1
    form = str(getattr(filing, "filing_type", None) or "unknown")
    swapped = lost = gained = False
    for row in rows:
        if prov._is_no_total_bank(xbrl) and _is_conflated_bank_revenue(row):
            counts["rows_dropped_no_total_bank"] += 1
            continue
        counts["rows"] += 1
        counts["rows_by_container"][container] += 1
        old = old_label(row, xbrl)
        new, fields, withheld = new_outcome(row, filing, xbrl, section_ref)
        transition = f"{old} -> {new}"
        counts["transitions"][transition] += 1
        counts["transitions_by_form"][f"{form}: {transition}"] += 1
        for field in fields:
            counts["swapped_fields"][field] += 1
        if withheld:
            counts["takeaways_withheld"] += 1
        swapped = swapped or new == "swapped"
        lost = lost or (old == "matched" and new == "linked")
        gained = gained or (old == "linked" and new == "matched")
    counts["summaries_with_a_swap"] += int(swapped)
    counts["summaries_losing_a_match"] += int(lost)
    counts["summaries_gaining_a_match"] += int(gained)


def new_counts() -> dict[str, Any]:
    return {
        "summaries": 0,
        "summaries_with_rows": 0,
        "summaries_without_a_table": 0,
        "summaries_without_xbrl": 0,
        "summaries_xbrl_failed": 0,
        "rows": 0,
        "rows_dropped_no_total_bank": 0,
        "rows_by_container": Counter(),
        "transitions": Counter(),
        "transitions_by_form": Counter(),
        "swapped_fields": Counter(),
        "takeaways_withheld": 0,
        "summaries_with_a_swap": 0,
        "summaries_losing_a_match": 0,
        "summaries_gaining_a_match": 0,
    }


def count_stored_summaries(session: Any, limit: Optional[int] = None, page_size: int = 200) -> dict[str, Any]:
    """Run both checks over every stored summary with its filing, in order of id, a page per transaction.

    Each page is read, counted and its transaction rolled back before the next is read, so the shared lock a
    read holds on ``summaries`` and ``filings`` lasts one page and a migration's ``ALTER`` never waits behind
    the whole run. The session is read-only (PGOPTIONS), so the rollback ends a transaction that wrote nothing."""
    from sqlalchemy import select

    from app.models import Filing, Summary

    counts = new_counts()
    last_id, seen = 0, 0
    while limit is None or seen < limit:
        page = page_size if limit is None else min(page_size, limit - seen)
        statement = (
            select(Summary, Filing).join(Filing, Summary.filing_id == Filing.id)
            .where(Summary.id > last_id).order_by(Summary.id).limit(page)
        )
        rows = session.execute(statement).all()
        for summary, filing in rows:
            count_summary(summary, filing, counts)
            last_id, seen = summary.id, seen + 1
        session.rollback()
        if len(rows) < page:
            break
    return counts


def as_json(counts: dict[str, Any]) -> str:
    plain = {key: (dict(sorted(value.items())) if isinstance(value, Counter) else value) for key, value in counts.items()}
    return json.dumps(plain, indent=2, sort_keys=True)


def as_lines(counts: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in counts.items():
        if isinstance(value, Counter):
            lines.append(f"{key}:")
            lines.extend(f"  {name}: {count}" for name, count in sorted(value.items()))
        else:
            lines.append(f"{key}: {value}")
    return lines


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Count what the strict figure check changes for stored summaries (read-only).")
    parser.add_argument("--limit", type=int, default=None, help="read only the first N summaries by id (a local rehearsal)")
    parser.add_argument("--page-size", type=int, default=200, help="summaries read per transaction")
    args = parser.parse_args(argv)
    from app.database import SessionLocal

    started = time.monotonic()
    with SessionLocal() as session:
        counts = count_stored_summaries(session, limit=args.limit, page_size=args.page_size)
    print(as_json(counts))
    print()
    print("\n".join(as_lines(counts)))
    print(f"\nread {counts['summaries']} summaries in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
