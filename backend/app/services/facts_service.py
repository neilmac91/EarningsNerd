"""Normalize the standardized XBRL metrics we already extract into queryable `financial_fact` rows.

`normalize_standardized_to_facts` is pure (dict in → list[dict] out, unit-testable). `upsert_facts`
writes them while maintaining the restatement-safe `is_latest` flag.

Per-filing facts reuse `xbrl_service.extract_standardized_metrics`. The local reconciliation
gate rejects impossible values and records warnings for implausible ones. Companyfacts supplies
FY and fiscal quarters, with compatible cumulative-flow calculations and reported-only EPS.
Both paths retain calculation operands and source-check evidence.
"""
from __future__ import annotations

import asyncio
import logging  # noqa: F401 - preserve the facade import surface
import math  # noqa: F401 - preserve the facade import surface
from concurrent.futures import TimeoutError as FuturesTimeoutError  # noqa: F401 - preserve the facade import surface
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

from app.services.event_loop import get_app_loop  # noqa: F401 - preserve the facade import surface
from app.services.fact_provenance import fact_operand, provenance_for_fact, published_value  # noqa: F401 - preserve the facade import surface
from app.services.facts.calendar import (
    _fiscal_year_windows, _label_quarters, fiscal_duration_values, fiscal_year_labels, reported_fiscal_year,  # noqa: F401 - preserve the facade import surface
)
from app.services.facts.lineage import (
    annotate_filing_calculations, authoritative_reconciliation, local_reconciliation,  # noqa: F401 - preserve the facade import surface
)
from app.services.facts.quarterly import (
    FINAL_QUARTER_WINDOW, QUARTER_WINDOW, derive_cumulative_quarters, derive_quarter_sum_fallback,  # noqa: F401 - preserve the facade import surface
    reported_fact, same_period_provenance, same_scope,  # noqa: F401 - preserve the facade import surface
)

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_  # noqa: F401 - preserve the facade import surface

from app.models import Company, Filing, FinancialFact, Watchlist

from app.services.facts.concepts import (
    AFFECTED_FINANCIAL_CONCEPTS,
    COMPANYFACTS_DURATION_TAGS,
    COMPANYFACTS_INFLIGHT_WAIT_SECONDS,
    COMPANYFACTS_INSTANT_TAGS,
    COMPANYFACTS_SYNC_TIMEOUT_SECONDS,
    CROSS_CHECK_TOLERANCE,
    HEADLINE_GAAP_TAGS,
    NON_NEGATIVE_CONCEPTS,
    _CF_ANNUAL_WINDOW,
    _CF_QUARTER_WINDOW,
    _CF_YTD6_WINDOW,
    _CF_YTD9_WINDOW,
    _CONCEPT_UNITS,
    _FI_SKIPPED_CONCEPTS,
    _INSTANT_HEADLINE,
    _MAGNITUDE_TOLERANCE,
    _QUARTER_PERIODS,
    _VALID_FP,
    _classify_duration,
    _duration_start,
    _fiscal_period,
    _is_financial_sic,
    _parse_date,
    _unit_for,
)
from app.services.facts.companyfacts import _collect_companyfacts_values, normalize_companyfacts
from app.services.facts.derive import derive_q4_facts, derive_same_period_metrics
from app.services.facts.reconcile import (
    _prior_values, cross_check_facts, extract_authoritative_values, reconcile_facts,
)
from app.services.facts.upsert import (
    _lock_fact_companies, normalize_standardized_to_facts, process_filing_facts,
    upsert_facts, upsert_facts_bulk,
)
from app.services.facts.transport import (
    _fetch_companyfacts_async,
    _fetch_companyfacts_sync,
    _running_loop_in_this_thread,
    logger,
)

__all__ = [
    'AFFECTED_FINANCIAL_CONCEPTS',
    'COMPANYFACTS_DURATION_TAGS',
    'COMPANYFACTS_INFLIGHT_WAIT_SECONDS',
    'COMPANYFACTS_INSTANT_TAGS',
    'COMPANYFACTS_SYNC_TIMEOUT_SECONDS',
    'CROSS_CHECK_TOLERANCE',
    'HEADLINE_GAAP_TAGS',
    'NON_NEGATIVE_CONCEPTS',
    '_CF_ANNUAL_WINDOW',
    '_CF_QUARTER_WINDOW',
    '_CF_YTD6_WINDOW',
    '_CF_YTD9_WINDOW',
    '_CONCEPT_UNITS',
    '_FI_SKIPPED_CONCEPTS',
    '_INSTANT_HEADLINE',
    '_MAGNITUDE_TOLERANCE',
    '_QUARTER_PERIODS',
    '_VALID_FP',
    '_classify_duration',
    '_collect_companyfacts_values',
    '_companyfacts_fresh_result',
    '_duration_start',
    '_fetch_companyfacts_async',
    '_fetch_companyfacts_sync',
    '_fiscal_period',
    '_fiscal_year_windows',
    '_fundamentals_payload',
    '_inflight_syncs',
    '_is_financial_sic',
    '_label_quarters',
    '_lock_fact_companies',
    '_parse_date',
    '_persist_companyfacts_payload',
    '_prior_values',
    '_running_loop_in_this_thread',
    '_unit_for',
    'backfill_company_sic',
    'backfill_facts',
    'cross_check_facts',
    'derive_q4_facts',
    'derive_same_period_metrics',
    'extract_authoritative_values',
    'get_filing_fundamentals',
    'ingest_companyfacts',
    'ingest_companyfacts_by_id',
    'logger',
    'normalize_companyfacts',
    'normalize_standardized_to_facts',
    'process_filing_facts',
    'reconcile_facts',
    'remediate_industry_facts',
    'sync_companyfacts_batch',
    'upsert_facts',
    'upsert_facts_bulk',
]


def backfill_facts(
    db: Session,
    extract=None,
    limit: Optional[int] = None,
    *,
    only_unprocessed: bool = False,
    cross_check: bool = True,
    companyfacts_fetcher=None,
    refresh_flags: bool = False,
    flags_only: bool = False,
    tickers: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Populate ``financial_fact`` from filings that already carry ``xbrl_data``.

    Reuses the standardized-metrics extractor + the pure normalizer + the writer. Idempotent
    (``upsert_facts`` skips rows that already exist, including their stored reconciliation flags).
    A default pass does not repair historical flags; ``refresh_flags=True`` (the
    ``reconciliation-flag-audit`` script) re-evaluates ONLY the flag of value/source-identical
    existing rows and adds ``flags_refreshed`` / ``value_mismatch`` to the stats, logging one line
    per filing that would change. ``flags_only=True`` (the audit's write mode) confines the pass to
    flag columns: identities not stored yet are counted as ``facts_unstored``, never inserted, no
    current row is demoted and the stamp is not touched. ``tickers`` restricts the pass to those
    companies (uppercased). ``dry_run=True`` rolls back each filing's transaction instead of committing it (fact rows,
    flag flips AND the ``processed_facts_at`` stamp) — note that the rollback expires the loaded
    objects, so a caller must ``db.refresh()`` before reading them. Filings are processed oldest-first so the
    newest reported value wins ``is_latest``, and each is stamped with ``processed_facts_at`` so we
    can tell which filings have been normalized. ``extract`` is injectable for tests.

    ``only_unprocessed=True`` skips filings already stamped — the incremental mode for the scheduled
    cron (process just the newly-arrived filings). The default reprocesses everything (a full,
    idempotent pass), which is what a manual re-run wants.

    When ``cross_check`` is on, headline figures are reconciled against SEC's companyfacts API
    (§3.5 step 2): one fetch per company (cached for the run), best-effort. ``companyfacts_fetcher``
    is injectable for tests; pass ``cross_check=False`` (or run with no network) to skip.
    """
    if extract is None:
        from app.services.edgar.compat import xbrl_service

        extract = xbrl_service.extract_standardized_metrics

    fetch_companyfacts = companyfacts_fetcher or _fetch_companyfacts_sync
    auth_by_company: dict[int, dict[tuple[str, date], float]] = {}

    # Eager-load company so the per-filing cik lookup for the cross-check isn't an N+1.
    query = (
        db.query(Filing)
        .options(joinedload(Filing.company))
        .filter(Filing.xbrl_data.isnot(None))
    )
    if only_unprocessed:
        query = query.filter(Filing.processed_facts_at.is_(None))
    if tickers:
        query = query.filter(Filing.company_id.in_(
            db.query(Company.id).filter(Company.ticker.in_([t.upper() for t in tickers]))
        ))
    query = query.order_by(Filing.filing_date.asc())
    if limit:
        query = query.limit(limit)

    processed = 0
    inserted = 0
    skipped = 0
    rejected = 0
    errors = 0
    flags_refreshed = 0
    value_mismatch = 0
    unstored = 0
    companyfacts_unavailable = 0
    unauthorized_companies: set[int] = set()
    for filing in query.all():
        try:
            standardized = extract(filing.xbrl_data)
        except Exception:
            logger.exception("facts backfill: extract failed for filing %s", filing.id)
            errors += 1
            continue

        # Cross-check headline figures against companyfacts (one fetch per company, cached).
        authoritative: Optional[dict[tuple[str, date], float]] = None
        refresh_this_filing = refresh_flags
        if cross_check:
            if filing.company_id not in auth_by_company:
                cik = getattr(filing.company, "cik", None)
                fetched = fetch_companyfacts(cik) if cik else None
                auth_by_company[filing.company_id] = (
                    extract_authoritative_values(fetched) if fetched else {}
                )
                if not fetched:
                    companyfacts_unavailable += 1
                    unauthorized_companies.add(filing.company_id)
            authoritative = auth_by_company[filing.company_id]
            # The audit's verdicts are only trustworthy under the same authority the stored flags
            # were computed with: a row confirmed by companyfacts within tolerance keeps its
            # `edgar_xbrl` source, so without the fetch the local gate would demote it. Count the
            # miss (it fails the audit run) and leave that company's flags alone.
            if filing.company_id in unauthorized_companies:
                refresh_this_filing = False

        # Shared processing uses Filing.period_end_date for the local current-period check.
        # Reprocessing skips existing identities; only the opt-in ``refresh_flags`` audit
        # re-evaluates their stored reconciliation flag (value/source-identical rows only).
        result = process_filing_facts(
            db, filing, standardized=standardized, authoritative=authoritative,
            refresh_flags=refresh_this_filing, flags_only=flags_only, commit=not dry_run,
        )
        if dry_run:
            db.rollback()  # preview only: discard rows, flag flips and the stamp for this filing
        # result is None only when there's nothing to process (no xbrl_data) — can't happen here
        # since the query filters `xbrl_data IS NOT NULL`, but guard it (the return type is Optional).
        if result is not None:
            inserted += result["inserted"]
            skipped += result["skipped"]
            rejected += result.get("rejected", 0)
            unstored += result.get("unstored", 0)
            processed += 1
            if refresh_this_filing:
                flags_refreshed += result["flags_refreshed"]
                value_mismatch += result["value_mismatch"]
                if (result["inserted"] or result["flags_refreshed"] or result["value_mismatch"]
                        or result.get("unstored")):
                    logger.info(
                        "reconciliation_flag_audit filing_id=%s accession=%s inserted=%s "
                        "unstored=%s flags_refreshed=%s value_mismatch=%s dry_run=%s",
                        filing.id, filing.accession_number, result["inserted"],
                        result.get("unstored", 0), result["flags_refreshed"],
                        result["value_mismatch"], dry_run,
                    )

    stats = {
        "filings_processed": processed,
        "facts_inserted": inserted,
        "facts_skipped": skipped,
        "facts_rejected": rejected,
        "extract_errors": errors,
    }
    if refresh_flags:
        stats["flags_refreshed"] = flags_refreshed
        stats["value_mismatch"] = value_mismatch
        stats["companyfacts_unavailable"] = companyfacts_unavailable
    if flags_only:
        stats["facts_unstored"] = unstored
    return stats


def remediate_industry_facts(
    db: Session,
    *,
    refetch,
    tickers: Optional[list[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-extract & re-normalize FINANCIAL-INSTITUTION filings so persisted ``xbrl_data`` and
    ``financial_fact`` carry the industry-correct revenue/components (filing 528 / MCB fix).

    Existing bank filings hold a fee-income-only "revenue" subset. Because ``raw_tag`` is not in the
    fact identity key, a plain re-upsert would SKIP the stale rows, so we delete the affected
    concepts for each filing and re-insert from the corrected extraction.

    ``refetch(company, filing) -> Optional[dict]`` returns fresh ``xbrl_data`` (or None to skip) — it
    is injected so this function stays network-free and unit-testable; the CLI wires the real
    (statement-aware) XBRL extractor. Filings are processed **oldest-first per company** so corrected
    current values reconcile against corrected priors (avoiding false magnitude flags), and the
    newest filing wins ``is_latest`` — this holds only when EVERY filing that reports an overlapping
    period is remediated, so each filing is **atomic** (xbrl_data write + fact delete + re-insert in
    one transaction, rolled back on failure) and any skip is surfaced (``skipped_ids``) rather than
    silently left stale. Cross-check is intentionally OFF (authoritative=None): SEC companyfacts has
    no single authoritative tag for a bank's components/total.

    Returns stats including ``remediated_ids`` (for the regeneration companion) and ``skipped_ids``.

    Coverage note: the default cohort is the financial-services SIC band (6000–6799) in SQL. A
    blank/NULL-SIC financial filer (e.g. some BDCs) is NOT auto-selected — the edgartools
    ``is_financial_institution()`` probe the extractor uses isn't available at the DB layer — so pass
    such filers explicitly via ``tickers``.
    """
    companies_q = db.query(Company)
    if tickers:
        companies_q = companies_q.filter(Company.ticker.in_([t.upper() for t in tickers]))
    else:
        # `Company.sic` is a String column of 4-digit codes, so a lexical BETWEEN is correct here.
        companies_q = companies_q.filter(Company.sic.between("6000", "6799"))
    companies = companies_q.all()

    stats: dict[str, Any] = {
        "companies": 0, "filings_refetched": 0, "filings_skipped": 0,
        "facts_deleted": 0, "facts_inserted": 0, "errors": 0,
        "remediated_ids": [], "skipped_ids": [],
    }
    processed = 0
    for company in companies:
        filings = (
            db.query(Filing)
            .filter(Filing.company_id == company.id, Filing.xbrl_data.isnot(None))
            .order_by(Filing.filing_date.asc())
            .all()
        )
        if not filings:
            continue
        stats["companies"] += 1
        for filing in filings:
            if limit is not None and processed >= limit:
                return stats
            try:
                fresh = refetch(company, filing)
            except Exception:
                logger.exception("remediate: refetch failed for filing %s", filing.id)
                stats["errors"] += 1
                stats["skipped_ids"].append(filing.id)
                continue
            if not fresh:
                stats["filings_skipped"] += 1
                stats["skipped_ids"].append(filing.id)
                continue
            stats["filings_refetched"] += 1
            processed += 1
            if dry_run:
                continue
            # One atomic transaction per filing: overwrite the blob, delete the stale affected-concept
            # rows (raw_tag isn't in the identity, so a plain re-upsert would skip them), re-insert the
            # corrected facts, then commit. On any failure roll back so we never leave xbrl_data
            # updated with facts deleted-but-not-reinserted.
            try:
                filing.xbrl_data = fresh
                deleted = (
                    db.query(FinancialFact)
                    .filter(
                        FinancialFact.company_id == company.id,
                        FinancialFact.accession == filing.accession_number,
                        FinancialFact.concept.in_(AFFECTED_FINANCIAL_CONCEPTS),
                    )
                    .delete(synchronize_session=False)
                )
                result = process_filing_facts(db, filing, commit=False)  # cross_check off
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("remediate: write failed for filing %s", filing.id)
                stats["errors"] += 1
                stats["skipped_ids"].append(filing.id)
                continue
            stats["facts_deleted"] += deleted or 0
            if result is not None:
                stats["facts_inserted"] += result["inserted"]
            stats["remediated_ids"].append(filing.id)
    return stats


def backfill_company_sic(
    db: Session,
    *,
    fetch_sic,
    tickers: Optional[list[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Populate ``Company.sic`` (+ ``industry``) for companies missing it.

    No ingestion path wrote ``Company.sic`` (the transformer used non-existent ``sic_code`` columns),
    so it is NULL in prod — which collapses the Peers cohort (``peers_service`` falls back to the
    subject alone) and makes the financial-remediation SIC-band selection match nothing. This fills
    the blanks.

    ``fetch_sic(company) -> (sic, industry) | None`` is injected so the core stays network-free and
    unit-testable; the CLI wires an EdgarTools lookup. Idempotent + resumable: by default only
    companies with a NULL/empty ``sic`` are selected, so it can be re-run (and scheduled) to catch
    newly-ingested rows. Pass ``tickers`` to (re)fill a specific set. Returns counts +
    ``updated_ids``/``skipped_ids``.
    """
    companies_q = db.query(Company)
    if tickers:
        companies_q = companies_q.filter(Company.ticker.in_([t.upper() for t in tickers]))
    else:
        companies_q = companies_q.filter((Company.sic.is_(None)) | (Company.sic == ""))
    if limit is not None:
        companies_q = companies_q.limit(limit)

    stats: dict[str, Any] = {
        "scanned": 0, "updated": 0, "skipped": 0, "errors": 0,
        "updated_ids": [], "skipped_ids": [],
    }
    # Commit in small batches so a mid-run crash of this long, SEC-rate-limited pass loses only the
    # uncommitted tail (it's resumable — re-running only re-selects still-blank rows). Disable
    # expire-on-commit for the loop so each batch commit doesn't expire the pending Company rows and
    # force an N+1 reload of ``company.cik`` on the next ``fetch_sic``; restore the prior setting after.
    prior_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    pending = 0
    try:
        for company in companies_q.all():
            stats["scanned"] += 1
            try:
                result = fetch_sic(company)
            except Exception:
                logger.exception("backfill_company_sic: fetch failed for company %s", company.id)
                stats["errors"] += 1
                continue
            sic = result[0] if result else None
            industry = result[1] if result and len(result) > 1 else None
            if not sic:  # EdgarTools returned no SIC (e.g. some BDCs) — leave as-is, surface it
                stats["skipped"] += 1
                stats["skipped_ids"].append(company.id)
                continue
            stats["updated"] += 1
            stats["updated_ids"].append(company.id)
            if dry_run:
                continue
            company.sic = str(sic)
            if industry:
                company.industry = industry
            pending += 1
            if pending >= 100:  # commit in small batches
                db.commit()
                pending = 0
        if not dry_run and pending:
            db.commit()
    finally:
        db.expire_on_commit = prior_expire_on_commit
    return stats


def _fundamentals_payload(ticker: str, company_name: str, rows, cik: str | None = None) -> dict[str, Any]:
    """Group flat ``FinancialFact`` rows into the FundamentalsResponse shape (per-concept series, in
    the order queried — oldest→newest). Shared by the company- and filing-scoped readers."""
    series: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        series.setdefault(row.concept, []).append(
            {
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "value": published_value(row),
                "unit": row.unit,
                "form": row.form,
                "accession": row.accession,
                "reconciled": bool(row.reconciled),
                "provenance": provenance_for_fact(row, cik),
            }
        )
    return {
        "ticker": ticker,
        "company_name": company_name,
        "concepts": [
            {"concept": concept, "unit": points[0]["unit"], "points": points}
            for concept, points in series.items()
        ],
    }


def get_filing_fundamentals(db: Session, filing_id: int) -> Optional[dict[str, Any]]:
    """Annual (FY) facts **as reported in a single filing**, grouped into per-concept time-series.

    Filing-scoped (roadmap B): keyed by ``filing_id`` with **no** ``is_latest`` filter, so the chart
    shows the multi-year figures *this specific filing* disclosed (its comparative years) — an
    immutable snapshot faithful to the document, even if a later filing restated a period. Restricted
    to ``fiscal_period == "FY"`` (the annual-report periods — 10-K / 20-F / 40-F; see
    ``_fiscal_period``): the backfill ingests every XBRL-bearing filing, so a company that has filed
    10-Qs also carries quarterly facts (``fiscal_period`` is ``None``), and without this filter a
    3-month quarterly value would surface alongside the full-year value for the same ``fiscal_year`` —
    a quarterly bar masquerading as an annual one under the chart's "Annual figures" label. Returns
    ``None`` when the filing doesn't exist.
    """
    filing = (
        db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
    )
    if filing is None:
        return None

    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.filing_id == filing_id,
            FinancialFact.fiscal_period == "FY",
        )
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.asc())
        .all()
    )

    company = filing.company
    return _fundamentals_payload(
        (company.ticker if company else "") or "",
        (company.name if company else "") or "",
        rows,
        cik=company.cik if company else None,
    )


# Per-company in-flight sync dedup (the summary_pipeline._claim_inflight pattern): concurrent
# coverage requests for the same company collapse into one SEC fetch. Process-local is the right
# scope — prod is a single Cloud Run instance with Redis off.
_inflight_syncs: dict[int, asyncio.Event] = {}


def _companyfacts_fresh_result(
    db: Session, company: Company, *, force: bool
) -> Optional[dict[str, Any]]:
    """Return the unchanged TTL result, or ``None`` when this company needs a fetch."""
    synced_at = company.facts_synced_at
    if synced_at is not None and synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes
    if force or synced_at is None:
        return None

    from app.config import settings

    if datetime.now(timezone.utc) - synced_at >= timedelta(
        hours=settings.COMPANYFACTS_SYNC_TTL_HOURS
    ):
        return None
    newer_filing = (
        db.query(Filing.id)
        .filter(Filing.company_id == company.id, Filing.filing_date > synced_at)
        .first()
    )
    if newer_filing is not None:
        return None
    return {
        "synced": True, "refreshed": False, "inserted": 0, "skipped": 0,
        "demoted": 0, "unsupported_ifrs": False,
    }


def _persist_companyfacts_payload(
    db: Session, company: Company, payload: dict[str, Any]
) -> dict[str, Any]:
    """Normalize and persist one already-fetched payload in the caller's short transaction."""
    facts, meta = normalize_companyfacts(
        company.id, payload, financial_sic=_is_financial_sic(company.sic)
    )
    result = (
        upsert_facts_bulk(db, facts, commit=False)
        if facts
        else {"inserted": 0, "skipped": 0, "demoted": 0}
    )
    company.facts_synced_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "companyfacts_sync company=%s inserted=%s skipped=%s demoted=%s ifrs=%s",
        company.id, result["inserted"], result["skipped"], result["demoted"],
        meta["unsupported_ifrs"],
    )
    return {
        "synced": True, "refreshed": True, **result,
        "unsupported_ifrs": meta["unsupported_ifrs"],
    }


async def ingest_companyfacts(
    db: Session,
    company: Company,
    *,
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Sync one company's companyfacts history into ``financial_fact`` (TTL-guarded, deduped).

    Freshness: a sync newer than ``COMPANYFACTS_SYNC_TTL_HOURS`` is a no-op UNLESS a Filing row
    newer than the stamp exists (a fresh filing shouldn't wait out the TTL) or ``force`` is set.
    ``facts_synced_at`` is stamped even for empty/IFRS-only results so unsupported filers aren't
    refetched hourly; a FAILED fetch does not stamp (retry on next touch). ``fetcher`` is
    injectable for tests (async ``cik -> dict | None``).
    """
    fresh = _companyfacts_fresh_result(db, company, force=force)
    if fresh is not None:
        return fresh

    inflight = _inflight_syncs.get(company.id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        db.expire(company)  # pick up the leader's facts_synced_at
        return {"synced": company.facts_synced_at is not None, "refreshed": False, "inserted": 0,
                "skipped": 0, "demoted": 0, "unsupported_ifrs": False, "waited": True}

    event = asyncio.Event()
    _inflight_syncs[company.id] = event
    try:
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(company.cik)
        if payload is None:
            return {"synced": False, "refreshed": False, "inserted": 0, "skipped": 0, "demoted": 0,
                    "unsupported_ifrs": False, "error": "fetch_failed"}
        return _persist_companyfacts_payload(db, company, payload)
    finally:
        if _inflight_syncs.get(company.id) is event:
            _inflight_syncs.pop(company.id, None)
        event.set()


async def ingest_companyfacts_by_id(
    company_id: int,
    *,
    session_factory: Callable[[], Session],
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Sync coverage facts without retaining a database connection during external waits.

    The coverage route can outlive its request while the SEC fetch continues in the background.
    Keep its database ownership to two short units: a freshness/snapshot read, then (for the
    leader) persistence after the fetch.  A same-company follower waits on the process-local event
    with no session of its own.  The caller-owned ``ingest_companyfacts`` contract remains intact
    for batch jobs and tests that deliberately manage a larger transaction.
    """
    with session_factory() as db:
        company = db.get(Company, company_id)
        if company is None:
            return {"synced": False}

        fresh = _companyfacts_fresh_result(db, company, force=force)
        if fresh is not None:
            return fresh

        cik = company.cik

    inflight = _inflight_syncs.get(company_id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        with session_factory() as db:
            synced_at = db.query(Company.facts_synced_at).filter(Company.id == company_id).scalar()
        return {
            "synced": synced_at is not None, "refreshed": False, "inserted": 0, "skipped": 0,
            "demoted": 0, "unsupported_ifrs": False, "waited": True,
        }

    event = asyncio.Event()
    _inflight_syncs[company_id] = event
    try:
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(cik)
        if payload is None:
            return {
                "synced": False, "refreshed": False, "inserted": 0, "skipped": 0,
                "demoted": 0, "unsupported_ifrs": False, "error": "fetch_failed",
            }
        with session_factory() as db:
            company = db.get(Company, company_id)
            if company is None:
                return {"synced": False}
            return _persist_companyfacts_payload(db, company, payload)
    finally:
        if _inflight_syncs.get(company_id) is event:
            _inflight_syncs.pop(company_id, None)
        event.set()


async def sync_companyfacts_batch(
    db: Session,
    *,
    tickers: Optional[list[str]] = None,
    watchlist_only: bool = False,
    limit: Optional[int] = None,
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Warm the companyfacts cache for a cohort (ops path: internal job / CLI script).

    Cohort: explicit ``tickers`` > ``watchlist_only`` (every company on any user's watchlist) >
    all companies. Serial on purpose — the rate limiter paces the fetches; a company's failure
    never stops the walk.
    """
    query = db.query(Company)
    if tickers:
        query = query.filter(Company.ticker.in_([t.upper() for t in tickers]))
    elif watchlist_only:
        watched_ids = db.query(Watchlist.company_id).distinct()
        query = query.filter(Company.id.in_(watched_ids))
    query = query.order_by(Company.id.asc())
    if limit is not None:
        query = query.limit(limit)

    stats: dict[str, Any] = {"companies": 0, "refreshed": 0, "fresh": 0, "failed": 0,
                             "unsupported_ifrs": 0, "inserted": 0}
    # Each per-company ingest commits; with the default expire-on-commit every loaded Company
    # would then lazy-reload on the next iteration's attribute access (N+1). Disable it for the
    # loop and restore after — the backfill_company_sic pattern.
    prior_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    try:
        for company in query.all():
            stats["companies"] += 1
            try:
                result = await ingest_companyfacts(db, company, force=force, fetcher=fetcher)
            except Exception:  # noqa: BLE001 - one bad company must not stop the walk
                logger.exception("companyfacts sync failed for company %s", company.id)
                db.rollback()
                stats["failed"] += 1
                continue
            if not result.get("synced"):
                stats["failed"] += 1
            elif result.get("refreshed"):
                stats["refreshed"] += 1
                stats["inserted"] += result.get("inserted", 0)
            else:
                stats["fresh"] += 1
            if result.get("unsupported_ifrs"):
                stats["unsupported_ifrs"] += 1
    finally:
        db.expire_on_commit = prior_expire_on_commit
    return stats
