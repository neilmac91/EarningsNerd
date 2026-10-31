"""Normalize and persist filing facts while preserving writer transaction ownership."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Optional, Sequence

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Company, Filing, FinancialFact
from app.services.facts.concepts import (
    _QUARTER_PERIODS, _duration_start, _fiscal_period, _parse_date, _unit_for,
)
from app.services.facts.fiscal_evidence import adopt_trusted_fiscal_years
from app.services.facts.lineage import annotate_filing_calculations
from app.services.facts.own_reports import insert_history_rows
from app.services.facts.reconcile import _prior_values, cross_check_facts, reconcile_facts
from app.utils.datetimes import utcnow


def normalize_standardized_to_facts(
    company_id: int,
    filing_id: Optional[int],
    accession: Optional[str],
    form: Optional[str],
    standardized: Optional[dict],
) -> list[dict[str, Any]]:
    """Turn standardized metrics into fact dicts — one row per concept *per reported period*.

    A 10-K's XBRL carries the current year plus comparative prior years, so each concept's
    ``series`` (from ``extract_standardized_metrics``) yields several periods, each a row attributed
    to this filing's accession; ``period_end`` in the identity keeps them distinct, and ``is_latest``
    in ``upsert_facts`` keeps the newest filing's value current when periods overlap across filings.
    The fiscal year is the calendar year of ``period_end`` unless the point carries the one its
    filing's DEI focus names (``edgar/fiscal_periods``). Falls back to the single ``current`` entry
    when no ``series`` is present. Tolerant of missing/malformed entries (skipped, never raised).
    """
    if not accession or not isinstance(standardized, dict):
        return []
    facts: list[dict[str, Any]] = []
    for concept, entry in standardized.items():
        if not isinstance(entry, dict):
            continue
        points = entry.get("series")
        if not isinstance(points, list) or not points:
            current = entry.get("current")
            points = [current] if isinstance(current, dict) else []
        for point in points:
            if not isinstance(point, dict):
                continue
            value = point.get("value")
            # Exclude bool (a subclass of int) and non-numeric values.
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            period_end = _parse_date(point.get("period"))
            if period_end is None:
                continue
            # Each point may carry the form that reported it; fall back to the filing's form.
            point_form = point.get("form") or form
            facts.append(
                {
                    "company_id": company_id,
                    "filing_id": filing_id,
                    "concept": concept,
                    # The underlying XBRL tag this value came from (e.g. "us-gaap:InterestIncomeExpenseNet").
                    # Recorded for audit + so a concept that flips between filings can be detected.
                    "raw_tag": point.get("raw_tag"),
                    # Derived monetary metrics (e.g. free_cash_flow, computed from OCF − capex)
                    # don't carry a per-point currency, so fall back to the filing's overall
                    # reporting currency rather than silently defaulting to USD.
                    "unit": _unit_for(concept, point.get("currency") or standardized.get("reporting_currency")),
                    # The source fact's own reported start, when extraction preserved one. Absent
                    # for instant facts, computed aggregates, and any period whose equal-valued
                    # source facts disagreed — readers must treat NULL as "duration unknown" and
                    # stay conservative, never infer a year from the form or the fiscal label.
                    # Forward-only: existing rows keep their NULL, since `upsert_facts` skips an
                    # identity that already exists.
                    "period_start": _duration_start(point.get("period_start"), period_end),
                    "period_end": period_end,
                    "fiscal_year": point.get("fiscal_year") or period_end.year,
                    "fiscal_period": point.get("fiscal_period") or _fiscal_period(point_form),
                    "value": float(value),
                    "form": point_form,
                    "accession": accession,
                    "source": "edgar_xbrl",
                }
            )
    return annotate_filing_calculations(facts, initialize_reported=True)


def _lock_fact_companies(db: Session, facts: list[dict[str, Any]]) -> None:
    """Serialize both fact writers; non-key locks stay compatible with child-row FK checks."""
    if facts:
        with db.no_autoflush:
            db.query(Company.id).filter(Company.id.in_({f["company_id"] for f in facts})).order_by(
                Company.id
            ).with_for_update(key_share=True).all()


def upsert_facts(
    db: Session,
    facts: list[dict[str, Any]],
    *,
    period_of_report: Optional[date] = None,
    reconcile: bool = True,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
    commit: bool = True,
    refresh_flags: bool = False,
    flags_only: bool = False,
) -> dict[str, int]:
    """Insert fact rows, maintaining ``is_latest`` and the reconciliation flag.

    Runs the local-invariant gate (``reconcile`` on by default) over the batch first: impossible
    facts are dropped, the rest are written with their computed ``reconciled`` value. When an
    ``authoritative`` map (from ``extract_authoritative_values``) is supplied, headline figures are
    then cross-checked against it (§3.5 step 2) — confirmed or corrected to the SEC value.
    Idempotent on the full identity key — if a row with the same (company, concept, period_end,
    fiscal_period, unit, accession) already exists it is skipped; otherwise any current ``is_latest``
    row for the same (company, concept, period_end, fiscal_period, unit) is demoted unless its
    accession is known to be newer. Untied companyfacts rows are preserved conservatively because
    their filing dates are not stored here. Older own-filing facts remain queryable by filing ID.

    ``refresh_flags`` (opt-in; the reconciliation-flag audit) re-evaluates the stored ``reconciled``
    flag of a skipped identity against the freshly computed verdict — and ONLY the flag: a row
    whose ``source`` or ``value`` differs from the incoming fact (a bulk companyfacts row occupying
    the same identity, an authoritative override, a changed extraction) is counted as a
    ``value_mismatch`` and left untouched, so an authoritative ``True`` is never overwritten by a
    heuristic verdict. ``is_latest`` is restatement state and is never touched. The result then
    also carries ``flags_refreshed`` / ``value_mismatch``; the default result shape is unchanged.

    ``flags_only`` (opt-in; the audit's write mode) confines the batch to flag columns: an identity
    that is not stored yet is counted as ``unstored`` and never inserted, so no row is added and no
    current ``is_latest`` row is demoted. Storing those identities is the full backfill re-pass's
    job (``scripts/backfill_facts.py`` without ``--only-new``), not the audit's.
    """
    _lock_fact_companies(db, facts)
    rejected = 0
    if reconcile and facts:
        company_id = facts[0]["company_id"]
        concepts = {f["concept"] for f in facts}
        period_ends = [f["period_end"] for f in facts if f.get("period_end")]
        # Seed the gate with each concept's value from before the EARLIEST batch period;
        # reconcile_facts groups by period and chains in-batch priors forward from there, so a
        # multi-period batch compares each year against the one before it (DB or in-batch).
        prior = _prior_values(db, company_id, concepts, min(period_ends) if period_ends else None)
        facts, dropped = reconcile_facts(
            facts, prior_values=prior, period_of_report=period_of_report
        )
        rejected = len(dropped)
        if authoritative:
            facts = cross_check_facts(facts, authoritative)

    inserted, skipped, flags_refreshed, value_mismatch, unstored = _write_fact_rows(
        db, facts, refresh_flags, flags_only,
    )

    if commit:  # commit=False lets a caller fold this into one per-filing transaction (remediation)
        db.commit()
    result = {"inserted": inserted, "skipped": skipped, "rejected": rejected}
    if refresh_flags:
        result["flags_refreshed"] = flags_refreshed
        result["value_mismatch"] = value_mismatch
    if flags_only:
        result["unstored"] = unstored
    return result


def process_filing_facts(
    db: Session,
    filing,
    *,
    extract=None,
    standardized: Optional[dict] = None,
    authoritative: Optional[dict[tuple[str, date], float]] = None,
    commit: bool = True,
    refresh_flags: bool = False,
    flags_only: bool = False,
) -> Optional[dict[str, int]]:
    """Normalize ONE filing's stored ``xbrl_data`` into ``financial_fact`` (extract → normalize →
    take the annual years companyfacts already names → upsert → stamp ``processed_facts_at``). The
    per-filing core shared by ``backfill_facts`` (the loop) and the post-summary event hook, so a
    freshly-summarized filing populates its own facts without waiting for a batch run.

    No network here: a supplied pre-fetched ``authoritative`` map enables the optional companyfacts
    cross-check; the backfill caller owns that fetch. The local-invariant gate runs regardless. Pass ``standardized`` to reuse metrics the caller already
    extracted (the SSE path) and skip re-extraction. Returns the upsert result, or ``None`` when the
    filing has no ``xbrl_data`` to process. The persisted ``period_end_date`` supplies the local
    current-period check. Existing fact identities are skipped, including their stored flags,
    unless ``refresh_flags`` (the reconciliation-flag audit, which re-evaluates ONLY the flag of a
    value/source-identical row — see ``upsert_facts``). Authoritative cross-checks retain their
    existing override policy. The ``processed_facts_at`` stamp is unconditional except under
    ``flags_only`` (the audit's write mode, see ``upsert_facts``): flag columns only, so unstored
    identities are counted rather than inserted and the stamp is left as it is.
    """
    if standardized is None:
        if getattr(filing, "xbrl_data", None) is None:
            return None
        if extract is None:
            from app.services.edgar.compat import xbrl_service

            extract = xbrl_service.extract_standardized_metrics
        standardized = extract(filing.xbrl_data)

    facts = normalize_standardized_to_facts(
        filing.company_id, filing.id, filing.accession_number, filing.filing_type, standardized
    )
    adopt_trusted_fiscal_years(db, filing.filing_type, facts)  # Rows only; ``standardized`` keeps its labels.
    # upsert never commits here — this function owns the single commit so the fact rows and the
    # ``processed_facts_at`` stamp land together (and a caller can defer it with commit=False for a
    # larger per-filing transaction, e.g. remediation's xbrl_data write + delete + re-insert).
    report_date = getattr(filing, "period_end_date", None)  # Calendar date, not a timestamp.
    if isinstance(report_date, datetime):
        report_date = report_date.date()
    result = upsert_facts(
        db,
        facts,
        period_of_report=report_date,
        authoritative=authoritative,
        commit=False,
        refresh_flags=refresh_flags,
        flags_only=flags_only,
    )
    if not flags_only:
        filing.processed_facts_at = utcnow()
    if commit:
        db.commit()
    return result


def upsert_facts_bulk(
    db: Session, facts: list[dict[str, Any]], *, history: Sequence[dict[str, Any]] = (), commit: bool = True
) -> dict[str, int]:
    """Batched writer for latest-filed winners from a full-history companyfacts payload.

    A full ingest is ~23 concepts × up to ~50 periods — the per-row two-query loop in
    ``upsert_facts`` would be thousands of round trips. This prefetches the company's existing
    rows once, then applies the same rules in memory: identity skip (idempotent), ``is_latest``
    demotion per (concept, period_end, fiscal_period, unit), plus the D1 rule — a labelled
    Q1..Q4 row demotes the legacy NULL-``fiscal_period`` twin for the same period so a quarter
    never has two current rows. Facts must already carry ``reconciled`` (no gate runs here —
    see ``normalize_companyfacts``). Known Filing dates also protect an already-stored newer
    accession from a delayed SEC response; rows without local Filing metadata retain the
    normalizer's latest-filed ordering within that response. ``history`` (the normalizer's
    ``meta["history"]``, riding beside the batch's winners) is stored apart, non-current, by
    ``own_reports.insert_history_rows``; the result's ``history`` counts those rows.
    """
    if not facts:
        return {"inserted": 0, "skipped": 0, "demoted": 0, "history": 0}
    _lock_fact_companies(db, facts)
    company_id = facts[0]["company_id"]
    concepts = {f["concept"] for f in (*facts, *history)}
    rows = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id, FinancialFact.concept.in_(list(concepts))
    ).all()
    accessions = {f["accession"] for f in facts} | {row.accession for row in rows}
    filing_dates = dict(db.query(Filing.accession_number, Filing.filing_date).filter(
        Filing.accession_number.in_(accessions)
    ).all())
    existing_identity: set[tuple] = set()
    latest_by_key: dict[tuple, list[FinancialFact]] = {}
    null_fp_latest: dict[tuple, list[FinancialFact]] = {}
    for row in rows:
        existing_identity.add((row.concept, row.period_end, row.fiscal_period, row.unit, row.accession))
        if row.is_latest:
            latest_by_key.setdefault(
                (row.concept, row.period_end, row.fiscal_period, row.unit), []
            ).append(row)
            if row.fiscal_period is None:
                null_fp_latest.setdefault((row.concept, row.period_end, row.unit), []).append(row)

    inserted = skipped = demoted = 0
    for fact in facts:
        fact = dict(fact)
        reconciled = bool(fact.pop("reconciled", False))
        identity = (
            fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"], fact["accession"]
        )
        if identity in existing_identity:
            skipped += 1
            continue
        existing_identity.add(identity)

        key = (fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"])
        null_key = (fact["concept"], fact["period_end"], fact["unit"])
        current = list(latest_by_key.get(key, []))
        if fact["fiscal_period"] in _QUARTER_PERIODS:
            current.extend(null_fp_latest.get(null_key, []))
        incoming_date = filing_dates.get(fact["accession"])
        newer = any(
            row.is_latest and row.accession != fact["accession"]
            and filing_dates.get(row.accession) is not None
            and (incoming_date is None or
                 (filing_dates[row.accession], row.accession) > (incoming_date, fact["accession"]))
            for row in current
        )
        if not newer:
            for row in current:
                if row.is_latest:
                    row.is_latest = False
                    demoted += 1
        inserted_row = FinancialFact(**fact, is_latest=not newer, reconciled=reconciled)
        db.add(inserted_row)
        if not newer:
            latest_by_key[key] = [inserted_row]
            if fact["fiscal_period"] is None:
                null_fp_latest[null_key] = [inserted_row]
        inserted += 1

    history_inserted = insert_history_rows(db, history, existing_identity)
    if commit:
        db.commit()
    return {"inserted": inserted, "skipped": skipped, "demoted": demoted, "history": history_inserted}


def _write_fact_rows(
    db: Session, facts: list[dict[str, Any]], refresh_flags: bool, flags_only: bool,
) -> tuple[int, int, int, int, int]:
    """Write reconciled rows and return counters; the caller owns the transaction."""
    inserted = 0
    skipped = 0
    flags_refreshed = 0
    value_mismatch = 0
    unstored = 0
    filing_dates = dict(db.query(Filing.accession_number, Filing.filing_date).filter(
        Filing.accession_number.in_({f["accession"] for f in facts})
    ).all()) if facts else {}
    for fact in facts:
        fact = dict(fact)
        reconciled = fact.pop("reconciled", False)
        hit = (
            db.query(FinancialFact.id)
            .filter_by(
                company_id=fact["company_id"],
                concept=fact["concept"],
                period_end=fact["period_end"],
                fiscal_period=fact["fiscal_period"],
                unit=fact["unit"],
                accession=fact["accession"],
            )
            .first()
        )
        if hit:
            skipped += 1
            if refresh_flags:
                existing = db.get(FinancialFact, hit[0])
                same = existing.source == fact.get("source") and math.isclose(
                    float(existing.value), float(fact["value"]), rel_tol=1e-9, abs_tol=0.0
                )
                if not same:
                    value_mismatch += 1
                elif bool(existing.reconciled) != bool(reconciled):
                    existing.reconciled = reconciled
                    flags_refreshed += 1
            continue
        if flags_only:
            unstored += 1  # flag columns only: never insert, never demote a current row
            continue

        # A labelled quarter also replaces its legacy unlabelled twin; otherwise deriving a
        # period would leave two current rows for the same reported figure.
        period_filter = FinancialFact.fiscal_period == fact["fiscal_period"]
        if fact["fiscal_period"] in ("Q1", "Q2", "Q3", "Q4"):
            period_filter = or_(period_filter, FinancialFact.fiscal_period.is_(None))
        current = db.query(FinancialFact).filter_by(
            company_id=fact["company_id"],
            concept=fact["concept"],
            period_end=fact["period_end"],
            unit=fact["unit"],
            is_latest=True,
        ).filter(period_filter)
        incoming_date = filing_dates.get(fact["accession"])
        newer_filing = Filing.id.isnot(None) if incoming_date is None else or_(
            Filing.filing_date > incoming_date,
            and_(Filing.filing_date == incoming_date, Filing.accession_number > fact["accession"]),
        )
        newer = current.outerjoin(Filing, FinancialFact.accession == Filing.accession_number).filter(
            FinancialFact.accession != fact["accession"],
            or_(newer_filing, and_(FinancialFact.source == "companyfacts", Filing.id.is_(None))),
        ).first() is not None
        if not newer:
            current.update({"is_latest": False})

        db.add(FinancialFact(**fact, is_latest=not newer, reconciled=reconciled))
        inserted += 1
    return inserted, skipped, flags_refreshed, value_mismatch, unstored
