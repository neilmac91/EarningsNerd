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
from datetime import datetime
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
    """
    from app.config import settings
    from app.database import SessionLocal
    from app.models import Company, Filing, FilingContentCache, Summary
    from app.services.company_resolution import resolve_or_create_company_by_cik
    from app.services.edgar.compat import sec_edgar_service
    from app.services.summary_generation_service import generate_summary_background

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
        sec_results = await sec_edgar_service.search_company(ticker_u)  # network, no session held
        if not sec_results:
            result["status"] = "company_not_found"
            return result
        sec_company = sec_results[0]
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
    sec_filings = await sec_edgar_service.get_filings(cik, filing_types=[form_u], limit=1)
    if not sec_filings:
        result["status"] = "no_filings"
        return result
    sf = sec_filings[0]
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
        with SessionLocal() as db:
            filing = (
                db.query(Filing).filter(Filing.accession_number == sf["accession_number"]).first()
            )
            if not filing:
                filing = Filing(
                    company_id=company_id,
                    accession_number=sf["accession_number"],
                    filing_type=sf["filing_type"],
                    filing_date=datetime.fromisoformat(sf["filing_date"]),
                    period_end_date=(
                        datetime.fromisoformat(sf["report_date"]) if sf.get("report_date") else None
                    ),
                    document_url=document_url,
                    sec_url=sec_url,
                )
                db.add(filing)
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

    if force:
        with SessionLocal() as db:
            db.query(Summary).filter(Summary.filing_id == filing_id).delete()
            cache = (
                db.query(FilingContentCache)
                .filter(FilingContentCache.filing_id == filing_id)
                .first()
            )
            if cache:
                cache.critical_excerpt = None
            db.commit()

    # Generate outside any session (it manages its own; idempotent if a Summary slipped in).
    await generate_summary_background(filing_id, user_id=None)

    with SessionLocal() as db:
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        result["status"] = "generated" if summary else "generation_failed"
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
