#!/usr/bin/env python3
"""Relabel filing-owned FY facts whose fiscal year contradicts companyfacts (bug hunt 2026-10-15 #8).

Before P5 (#1364) the per-filing writer named every annual fact by the calendar year of its period
end (``facts/upsert.normalize_standardized_to_facts``: ``point.get("fiscal_year") or
period_end.year``), while the companyfacts writer names the same period by the issuer's fiscal
year. The two differ for a year ending around 1 February that is named for the year it starts in
(Target, Home Depot) and for a 52-week year ending on 1 January (Johnson & Johnson). The fact
identity leaves ``fiscal_year`` out, so neither writer ever corrects a row the other stored.

This one-off copies the companyfacts year onto each FY row that has a filing owner (any source: a
headline value the cross-check corrected is stored as ``companyfacts`` but keeps its owner), and
only a year it can trust. The evidence for a (company, period_end) is every companyfacts-reported
FY row there (source ``companyfacts``, a raw tag, no filing owner, not retired by a quarterly repair
as ``validation: unavailable``) that the fiscal-year-window writer stored or a repair corrected
(provenance version 1: #1191 brought those labels and versioned provenance together), current or
not. A row stored before #1191 (NULL provenance) names every FY period by the calendar year of its
end, so it is no evidence. Where no stored row is evidence at a period end, the evidence is the FY
rows the same writer names from the company's companyfacts as read from SEC on this run, which
nothing stores. A resync rarely helps: a sync skips every identity already stored, whichever writer
stored it, and never rewrites a stored row's label or provenance, so a pre-#1191 row or a period the
per-filing writer stored first gains a current twin only when a later report re-reports the period
under an accession not yet stored. Where a stored row vouches for a period end its year is the one
used; the read can still clear, or cause, a neighbour's ``label_collision``:
  - no evidence, only pre-#1191 rows    -> skipped ``legacy_companyfacts_only``
  - no companyfacts row, stored or read -> skipped ``no_companyfacts_fy``
  - they name more than one year      -> skipped ``companyfacts_disagree`` (never pick one)
  - they are all instants (balances)  -> skipped ``untrusted_instant_only``: the companyfacts
    writer names an instant older than every fiscal year it knows (its oldest opening balance) by
    one report's fy or by calendar year (``facts/companyfacts.py``: ``reported_fiscal_year(record,
    end) or end.year``), with no window chain behind it; a duration's year comes from its window
  - otherwise that one year: a row already carrying it counts ``already_agrees``. A row whose label
    is not the calendar default (``period_end.year``) was named by a labeller (P5's annual label, a
    NULL), not by the defect, and is never overwritten: ``not_calendar_default``. The rest relabel,
    unless the new label is one another period end of the same filing and concept carries, or one
    another current row of the concept carries (readers index current annual rows by year and
    concept): ``label_collision``. The whole period end then holds, every concept and filing at it,
    so no end is left on two fiscal years; re-checked until none is left, since a held row keeps
    its label. The read is not used where a current pre-#1191 row keeps the calendar label.
The evidence and trust rule is ``app/services/facts/fiscal_evidence.py`` (``evidence_kind``,
``trusted_year``), the rule #1364's per-filing writer adopts years by, so the two cannot drift.
Durations and instants are both relabelled: an FY balance closes the year that ends on its date.
Only ``fiscal_year`` changes, never period_end, value, unit, accession or is_latest; quarter rows
and companyfacts, derived and reported-EPS rows without a filing owner are never touched and
nothing is deleted. A filing whose verified fiscal years (relabelled now, or agreeing after an
earlier run) sit beside held calendar-default rows is listed under ``partial_filings`` on every run:
its chart may skip a year. The identity (company, concept, period_end,
fiscal_period, unit, accession) and every index on ``financial_fact`` leave ``fiscal_year`` out, so a
relabel cannot collide. Re-running is safe: a relabelled row agrees on the next run.

DRY RUN BY DEFAULT: nothing is written and each company's transaction is rolled back. ``--apply``
re-plans each company from live data and a fresh SEC read, in its own transaction under the company
lock both fact writers take, and journals every changed row in ``financial_fact_revision`` (action
``apply``), so ``scripts/repair_quarterly_facts.py --tickers T --rollback-run RUN_ID [--apply]``
reverts one company's run. Output: one JSON line per company scanned (``sec_evidence`` counts its rows judged on
the read), then one summary line. Network: one companyfacts read per company through
``facts/transport`` (the shared SEC limiter; its backoff may retry a 429), before the company's
session opens; a failed read, or one with no ``facts`` object, fails that company and changes nothing,
and for a failed read the transport's warning on standard error says why.

Founder commands (the DB is only reachable from Cloud Run; runbook docs/fiscal-year-label-repair.md):
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/relabel_filing_fy_facts.py --wait              # dry run: counts only
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/relabel_filing_fy_facts.py,--apply --wait      # only after sign-off

Local usage:
  python scripts/relabel_filing_fy_facts.py                       # dry run, every company
  python scripts/relabel_filing_fy_facts.py --tickers TGT,JNJ     # dry run, a cohort
  python scripts/relabel_filing_fy_facts.py --apply --limit 10    # write the first 10 companies
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any, Callable, Iterable
from uuid import uuid4

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import FinancialFact

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RELABEL_VERSION = "fy-relabel-v1"
SKIP_REASONS = (
    "already_agrees", "companyfacts_disagree", "label_collision", "legacy_companyfacts_only",
    "no_companyfacts_fy", "not_calendar_default", "untrusted_instant_only",
)


def _collisions(rows: list[FinancialFact], planned: dict[FinancialFact, int]) -> list[FinancialFact]:
    """Planned relabels whose label another period end of the same filing and concept, or another
    current row of the concept, would carry once every planned relabel is written."""
    by_label: dict[tuple[str, int | None], list[FinancialFact]] = defaultdict(list)
    for row in rows:
        by_label[(row.concept, planned.get(row, row.fiscal_year))].append(row)
    return [row for row, year in planned.items() if any(
        other.period_end != row.period_end
        and (other.filing_id == row.filing_id or (row.is_latest and other.is_latest))
        for other in by_label[(row.concept, year)]
    )]


def plan_company(rows: Iterable[FinancialFact], read: Iterable[Any] = ()) -> dict[str, Any]:
    """Split one company's FY rows into relabels and skips; reads attributes only. ``read`` holds the
    FY facts the companyfacts writer names from this run's SEC read: evidence where no stored row is."""
    from app.services.facts.fiscal_evidence import evidence_kind, trusted_year

    rows = [row for row in rows if row.fiscal_period == "FY"]
    evidence: dict[date, list[tuple[int, bool]]] = defaultdict(list)
    from_read: dict[date, list[tuple[int, bool]]] = defaultdict(list)
    legacy: set[date] = set()
    legacy_current: set[date] = set()  # a pre-#1191 row readers still pick keeps its calendar label here
    targets = []
    for row in rows:
        kind = evidence_kind(row)
        if kind == "current":
            evidence[row.period_end].append((row.fiscal_year, row.period_start is not None))
        elif kind == "legacy":
            legacy.add(row.period_end)
            if row.is_latest:
                legacy_current.add(row.period_end)
        elif row.filing_id is not None:
            targets.append(row)
    for fact in read:
        if fact.fiscal_period == "FY" and evidence_kind(fact) == "current":
            from_read[fact.period_end].append((fact.fiscal_year, fact.period_start is not None))
    skipped = Counter({reason: 0 for reason in SKIP_REASONS})
    held: dict[str, set[str]] = defaultdict(set)
    held_rows: list[FinancialFact] = []

    def hold(row: FinancialFact, reason: str) -> None:
        skipped[reason] += 1
        held[reason].add(row.period_end.isoformat())
        held_rows.append(row)

    planned: dict[FinancialFact, int] = {}
    agreeing: list[FinancialFact] = []
    sec_evidence = 0
    for row in targets:
        stored = evidence.get(row.period_end)
        # The read stands in only where no stored row vouches, and not where a current pre-#1191 row would
        # keep the calendar label beside the relabelled rows (readers pick current rows by year and concept).
        read_here = [] if stored or row.period_end in legacy_current else from_read.get(row.period_end, [])
        if read_here:
            sec_evidence += 1
        year, reason = trusted_year(stored or read_here, row.period_end in legacy)
        if reason is not None:
            hold(row, reason)
        elif year == row.fiscal_year:
            skipped["already_agrees"] += 1
            agreeing.append(row)
        elif row.fiscal_year != row.period_end.year:
            hold(row, "not_calendar_default")
        else:
            planned[row] = year
    # A held row keeps its label, so holding one relabel can make another collide: repeat. The whole
    # period end holds, every concept and filing at it, so no end is left on two fiscal years.
    while clashing := _collisions(rows, planned):
        ends = {row.period_end for row in clashing}
        for row in [row for row in planned if row.period_end in ends]:
            del planned[row]
            hold(row, "label_collision")
    # A filing whose verified fiscal years (relabelled now, or agreeing from an earlier run) sit
    # beside held calendar defaults: its chart may skip a year. Listed on every run, not just once.
    fiscal = [*planned, *(row for row in agreeing if row.fiscal_year != row.period_end.year)]
    partial = {row.accession for row in fiscal} & {
        row.accession for row in held_rows if row.fiscal_year == row.period_end.year
    }
    return {
        "scanned": len(targets), "sec_evidence": sec_evidence, "relabel": list(planned.items()),
        "skipped": dict(sorted(skipped.items())),
        "held": {reason: sorted(ends) for reason, ends in sorted(held.items())},
        "partial_filings": sorted(partial),
    }


def relabel_company(
    db: Session, company_id: int, *, apply: bool, run_id: str, read: Iterable[Any] = (),
) -> dict[str, Any]:
    """Plan one company's relabels (``read``: see ``plan_company``); with ``apply`` also write and
    journal them. The caller commits."""
    from app.models import Company, FinancialFact
    from app.models.financial_fact_revision import FinancialFactRevision
    from app.services import facts_service
    from app.services.quarterly_fact_repair import snapshot

    if apply:
        facts_service._lock_fact_companies(db, [{"company_id": company_id}])
    # Every FY row of the company: targets, evidence, and the current rows a relabel must not clash with.
    query = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id, FinancialFact.fiscal_period == "FY",
    ).order_by(FinancialFact.id)
    plan = plan_company(query.with_for_update().all() if apply else query.all(), read)
    pairs = Counter((row.period_end.isoformat(), row.fiscal_year, year) for row, year in plan["relabel"])
    revisions = 0
    if apply and plan["relabel"]:
        digest = hashlib.sha256(json.dumps(
            [[row.id, row.fiscal_year, year] for row, year in plan["relabel"]], separators=(",", ":"),
        ).encode()).hexdigest()
        for row, year in plan["relabel"]:
            before = snapshot(row)
            row.fiscal_year = year
            db.add(FinancialFactRevision(
                run_id=run_id, company_id=company_id, fact_id=row.id, action="apply",
                calculation_version=RELABEL_VERSION, payload_sha256=digest,
                before_state=before, after_state=snapshot(row),
            ))
            revisions += 1
        db.flush()
    company = db.get(Company, company_id)
    return {
        "company_id": company_id, "ticker": company.ticker if company else None, "run_id": run_id,
        "dry_run": not apply, "scanned": plan["scanned"], "sec_evidence": plan["sec_evidence"],
        "relabel_rows": len(plan["relabel"]),
        "relabels": [
            {"period_end": end, "from": old, "to": new, "rows": count}
            for (end, old, new), count in sorted(pairs.items(), key=lambda item: (item[0][0], str(item[0][1])))
        ],
        "skipped": plan["skipped"], "held": plan["held"], "partial_filings": plan["partial_filings"],
        "revisions": revisions,
    }


def companyfacts_read(company_id: int, cik: str, sic: str | None) -> list[Any]:
    """The facts the companyfacts writer names from the company's companyfacts as read from SEC now,
    through ``facts/transport`` (the shared limiter and backoff); nothing stores them, and
    ``plan_company`` keeps the FY rows. A failed read, or a payload with no ``facts`` object, raises,
    so the company fails and changes nothing rather than being planned without it."""
    from types import SimpleNamespace

    from app.services import facts_service

    payload = facts_service._fetch_companyfacts_sync(cik)
    if payload is None:
        raise RuntimeError("companyfacts read from SEC failed; company unchanged")
    if not isinstance(payload.get("facts"), dict):
        raise RuntimeError("companyfacts read from SEC had no facts object; company unchanged")
    facts, _meta = facts_service.normalize_companyfacts(
        company_id, payload, financial_sic=facts_service._is_financial_sic(sic),
    )
    return [SimpleNamespace(**fact) for fact in facts]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relabel filing-owned FY facts from companyfacts (dry run).")
    parser.add_argument("--apply", action="store_true", help="Write and journal the relabels (default: dry run).")
    parser.add_argument("--tickers", help="Comma-separated cohort, each reported (default: every company with filing FY rows).")
    parser.add_argument("--limit", type=int, help="Process at most this many companies, in company-id order.")
    return parser


def run(args: argparse.Namespace, emit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Process each selected company in its own session; emit its line, return the summary."""
    from app.database import SessionLocal
    from app.models import Company, FinancialFact

    tickers = sorted({t.strip().upper() for t in (args.tickers or "").split(",") if t.strip()})
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    # This short read session lists the cohort; each company then gets its own transaction.
    with SessionLocal() as db:
        query = db.query(Company.id, Company.ticker, Company.cik, Company.sic).order_by(Company.id)
        if tickers:
            known = {t for (t,) in db.query(Company.ticker).filter(Company.ticker.in_(tickers))}
            if set(tickers) - known:
                raise ValueError(f"Unknown tickers {sorted(set(tickers) - known)}; no company processed")
            query = query.filter(Company.ticker.in_(tickers))  # each named company gets a line
        else:
            owners = db.query(FinancialFact.company_id).filter(
                FinancialFact.fiscal_period == "FY", FinancialFact.filing_id.isnot(None),
            ).distinct()
            query = query.filter(Company.id.in_(owners))
        companies = (query.limit(args.limit) if args.limit else query).all()
    run_id = str(uuid4())
    summary: dict[str, Any] = {
        "summary": True, "run_id": run_id, "dry_run": not args.apply, "companies": len(companies),
        "companies_with_relabels": 0, "scanned": 0, "sec_evidence": 0, "relabel_rows": 0, "revisions": 0,
        "skipped": dict.fromkeys(SKIP_REASONS, 0), "partial_filings": 0, "failed": 0,
    }
    for company_id, ticker, cik, sic in companies:
        try:
            read = companyfacts_read(company_id, cik, sic)  # before the company's session opens
            with SessionLocal() as db:
                result = relabel_company(db, company_id, apply=args.apply, run_id=run_id, read=read)
                if args.apply:
                    db.commit()
                else:
                    db.rollback()
        except Exception as exc:  # One company's failure rolls back that company alone and fails the exit code.
            summary["failed"] += 1
            emit({"company_id": company_id, "ticker": ticker, "error": str(exc)})
            continue
        summary["companies_with_relabels"] += bool(result["relabel_rows"])
        for key in ("scanned", "sec_evidence", "relabel_rows", "revisions"):
            summary[key] += result[key]
        for reason, count in result["skipped"].items():
            summary["skipped"][reason] += count
        summary["partial_filings"] += len(result["partial_filings"])
        emit(result)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(line: dict[str, Any]) -> None:
        print(json.dumps(line, sort_keys=True), flush=True)

    try:
        summary = run(args, emit)
    except ValueError as exc:
        emit({"failed": 1, "error": str(exc)})
        return 1
    emit(summary)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    raise SystemExit(main())
