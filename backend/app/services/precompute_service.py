"""Background precompute of filing analyses (roadmap A1).

Exploits filing **immutability**: a finished ``Summary`` never changes, so generating it before
the first user arrives converts the cold path (~30-60s) into a warm DB hit (<100ms). Reuses the
idempotent ``generate_summary_background`` path (which short-circuits when a ``Summary`` already
exists), so re-running is safe and cheap.

This is the reusable core behind ``scripts/pregenerate_examples.py`` and the token-gated
``POST /internal/jobs/precompute`` trigger. It is deliberately **list/limit-driven** — there is no
implicit fleet sweep here: the caller passes the tickers/forms, and ``MAX_BATCH`` hard-caps the
batch so an accidental or oversized request can never fan out unbounded generation (cost guard).

The broad top-500 cohort + Cloud Scheduler cadence is wired by the *operator* (a ticker list fed to
this service), not encoded here — keeping the "how aggressive" decision in config, not code.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Forms we can analyze today (matches the summary pipeline's XBRL-backed path).
SUPPORTED_FORMS = ("10-K", "10-Q")

# Hard ceiling on a single precompute batch (tickers x forms). Bounds blast radius / spend even if a
# caller passes a huge list; the top-500 cohort x 2 forms (1000) would be split across batches above
# this. Tune via the caller, not by raising this casually.
MAX_BATCH = 1200


def _norm(values: Iterable[str]) -> list[str]:
    return [v.strip().upper() for v in values if v and v.strip()]


async def precompute_one(
    ticker: str,
    form: str = "10-K",
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Resolve the latest ``form`` filing for ``ticker``, ensure its DB rows, and cache its summary.

    Idempotent: returns ``already_cached`` without regenerating when a ``Summary`` already exists
    (unless ``force``). ``dry_run`` resolves via SEC + reports what *would* happen, writing nothing
    and generating nothing. Returns a status dict; never raises for "expected" misses (not found,
    no filings) — the caller aggregates statuses.

    ``force`` regenerates a stored summary in place under keep-better and reports ``generated`` (the
    run replaced it), ``kept`` (keep-better kept it) or ``failed`` (the run ended in a terminal error
    or never ran; one of the job's error counters). ``generation_failed`` means the filing still has
    no summary.
    """
    from app.config import settings
    from app.database import SessionLocal
    from app.models import Company, Filing, FilingContentCache, Summary
    from app.services.company_resolution import resolve_or_create_company_by_cik
    from app.services.edgar.compat import sec_edgar_service
    from app.services.summary_generation_service import generate_summary_background
    from app.services.summary_refresh import generation_failed
    from app.utils.datetimes import utc_from_iso

    ticker_u = ticker.upper().strip()
    form_u = form.upper().strip()
    result: dict = {"ticker": ticker_u, "form": form_u, "status": "unknown", "filing_id": None, "accession": None}

    # 20-F (FPI annual report) is summarizable end-to-end (Phase 2/3) but, like the rest of the
    # FPI program, only enabled when the discovery flag is on — keeping the page-scoped discipline.
    supported = SUPPORTED_FORMS + (("20-F",) if settings.ENABLE_FPI_FILINGS else ())
    if form_u not in supported:
        result["status"] = "unsupported_form"
        return result

    # DB sessions are kept short and are NEVER held open across the (slow) SEC EDGAR network calls —
    # otherwise a pooled connection would be checked out for the whole multi-second fetch, starving
    # the pool under any batch/concurrency. So: read with a session, close it, hit SEC, reopen only
    # to write.
    cik: Optional[str] = None
    company_id: Optional[int] = None
    sec_company: Optional[dict] = None

    with SessionLocal() as db:
        company = db.query(Company).filter(Company.ticker == ticker_u).first()
        if company:
            cik = company.cik
            company_id = company.id

    if cik is None:
        # Exact ticker only: an unlisted one is company_not_found, never the first partial match
        # (a retired "X" once warmed, and paid for, Exxon's 10-K).
        sec_company = await sec_edgar_service.resolve_ticker(ticker_u)  # network, no session held
        if sec_company is None:
            result["status"] = "company_not_found"
            return result
        cik = sec_company["cik"]
        if not dry_run:
            primary = await sec_edgar_service.primary_ticker_for_cik(cik)
            with SessionLocal() as db:
                company = db.query(Company).filter(Company.ticker == ticker_u).first()
                if not company:
                    # CIK-first: reuse an existing row for this CIK (e.g. stored under a
                    # preferred ticker) instead of clashing on unique-CIK (interim safeguard 1).
                    # New rows take the canonical primary ticker (P0-1).
                    company = resolve_or_create_company_by_cik(
                        db,
                        cik=cik,
                        ticker=primary or sec_company["ticker"],
                        name=sec_company["name"],
                        exchange=sec_company.get("exchange"),
                        path="precompute.precompute_one",
                        canonical_ticker=primary,  # self-heal a stale ticker → primary (P0-1)
                    )
                    db.commit()
                    db.refresh(company)
                company_id = company.id

    # Resolve the latest filing of this form (network, no session held).
    # A late amendment can be newer by filing date but belong to an older report period.
    # One bounded recent-window fetch lets us warm the latest period, then its latest amendment.
    sec_filings = await sec_edgar_service.get_filings(cik, filing_types=[form_u], limit=20)
    if not sec_filings:
        result["status"] = "no_filings"
        return result
    sf = max(sec_filings, key=lambda row: (
        row.get("report_date") or "", row.get("filing_date") or "",
        row.get("accession_number") or "",
    ))
    result["accession"] = sf.get("accession_number")
    sec_url = sf.get("sec_url")
    document_url = sf.get("document_url")
    # sec_url/document_url are NOT NULL + validated on the Filing model — skip rather than fail.
    if not sec_url or not document_url:
        result["status"] = "missing_urls"
        return result

    # Look up the filing + whether it's already summarized (short read session).
    filing_id: Optional[int] = None
    has_summary = False
    with SessionLocal() as db:
        filing = db.query(Filing).filter(Filing.accession_number == sf["accession_number"]).first()
        if filing:
            filing_id = filing.id
            has_summary = (
                db.query(Summary).filter(Summary.filing_id == filing_id).first() is not None
            )

    if dry_run:
        result["filing_id"] = filing_id
        result["status"] = "already_cached" if (has_summary and not force) else "would_generate"
        return result

    # Get-or-create the Filing row (short write session; mirrors routers/filings.py persistence).
    if filing_id is None:
        from app.services.filing_amendment_service import (
            existing_filings_for_insert,
            lock_company_filings,
            mark_superseded_filings,
        )

        with SessionLocal() as db:
            lock_company_filings(db, company_id)  # before the check below reads whether it exists
            accession = sf["accession_number"]
            filing = existing_filings_for_insert(db, [accession]).get(accession)
            if not filing:
                filing = Filing(
                    company_id=company_id,
                    accession_number=sf["accession_number"],
                    filing_type=sf["filing_type"],
                    filing_date=utc_from_iso(sf["filing_date"]),
                    period_end_date=(
                        utc_from_iso(sf["report_date"]) if sf.get("report_date") else None
                    ),
                    document_url=document_url,
                    sec_url=sec_url,
                )
                db.add(filing)
                db.flush()
                mark_superseded_filings(db, company_id)
                db.commit()
                db.refresh(filing)
            filing_id = filing.id
            has_summary = (
                db.query(Summary).filter(Summary.filing_id == filing_id).first() is not None
            )
    result["filing_id"] = filing_id

    if has_summary and not force:
        result["status"] = "already_cached"
        return result

    # A forced refresh never deletes the stored summary: the one orchestrator regenerates it IN PLACE
    # under keep-better (force_regenerate below), so its summaries.id and any saved_summaries bookmark
    # survive, and a failed or lower-ranked run keeps it (lessons/arch-fk-safe-bulk-deletes.md). Only
    # the cached excerpt is cleared, so the run builds it with the current extraction; the stored value
    # goes back in the finally below whenever the stored summary stays (a raise or a cancellation
    # included, not a killed process), None included, so read-time verification reads that summary
    # against the same cache text as before the run. With no excerpt (stored so, or while the run is in
    # flight), provenance_service reads citations against the legacy markdown_content and Risks against
    # risk_source_text, else that column, and leaves them unverified when neither is there. A filing
    # with no cache row before the run keeps the row the run creates.
    stored = None
    stored_excerpt: Optional[str] = None
    had_cache = False
    if force:
        with SessionLocal() as db:
            stored = db.query(Summary.id, Summary.updated_at).filter(Summary.filing_id == filing_id).first()
            cache = (
                db.query(FilingContentCache)
                .filter(FilingContentCache.filing_id == filing_id)
                .first()
            )
            if cache:
                had_cache = True
                stored_excerpt, cache.critical_excerpt = cache.critical_excerpt, None
            db.commit()

    # Generate outside any session (it manages its own; idempotent if a Summary slipped in).
    outcome = None
    try:
        outcome = await generate_summary_background(filing_id, None, force_regenerate=force)
    finally:
        with SessionLocal() as db:
            summary = db.query(Summary.id, Summary.updated_at).filter(Summary.filing_id == filing_id).first()
            # The in-place UPDATE stamps updated_at, so an unchanged (id, updated_at) was not replaced.
            replaced = stored is None or summary is None or tuple(summary) != tuple(stored)
            if not replaced and had_cache:
                db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).update(
                    {FilingContentCache.critical_excerpt: stored_excerpt}, synchronize_session=False
                )
                db.commit()

    if summary is None:
        result["status"] = "generation_failed"
    elif stored is None:
        result["status"] = "generated"
    elif outcome is None or generation_failed(outcome):
        # The terminal event alone cannot tell a keep from a replace (both carry the stored id), but a
        # terminal error is a failed paid attempt, as the refresh-stale drains count it.
        result["status"] = "failed"
    else:
        result["status"] = "generated" if replaced else "kept"
    return result


async def precompute(
    tickers: Iterable[str],
    forms: Iterable[str] = ("10-K",),
    *,
    force: bool = False,
    dry_run: bool = False,
    cap: int = MAX_BATCH,
) -> dict:
    """Precompute the latest ``forms`` filings for each ticker. Capped at ``cap`` (ticker x form)
    jobs; keeps going past per-item errors. Returns ``{"stats": {...}, "results": [...]}``."""
    tickers = _norm(tickers)
    forms = _norm(forms) or ["10-K"]
    all_jobs = [(t, f) for t in tickers for f in forms]
    cap = max(0, min(cap, MAX_BATCH))
    jobs = all_jobs[:cap]
    truncated = len(all_jobs) - len(jobs)

    results: list[dict] = []
    for ticker, form in jobs:
        try:
            results.append(await precompute_one(ticker, form, force=force, dry_run=dry_run))
        except Exception as exc:  # noqa: BLE001 — keep going for the rest of the batch
            logger.exception("Precompute failed for %s %s", ticker, form)
            results.append({"ticker": ticker, "form": form, "status": "error", "error": str(exc)[:200]})

    stats: dict = {"requested": len(all_jobs), "ran": len(jobs), "truncated_at_cap": truncated, "dry_run": dry_run}
    for r in results:
        stats[r["status"]] = stats.get(r["status"], 0) + 1
    return {"stats": stats, "results": results}
