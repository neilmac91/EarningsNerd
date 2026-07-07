"""Resolve-or-create a Company row keyed by CIK (data-quality remediation, interim safeguard 1).

CIK is the stable identity (``companies.cik`` is UNIQUE); ticker is a mutable label. The
historical miss-path bug: a ticker lookup misses (e.g. the stored ticker was overwritten to a
preferred class like JPM-PM), the caller blind-inserts a new row for the same CIK, and the
unique constraint turns a routine page view into a 500. Every miss path must be CIK-first:
reuse the existing row whatever its current ticker; insert only when the CIK is genuinely new,
under a SAVEPOINT so a concurrent-insert race degrades to a re-query instead of a poisoned
transaction (pattern: ``earnings_alert_service._resolve_company``).
"""

import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company

logger = logging.getLogger(__name__)


def _cik_forms(cik: str) -> list[str]:
    """The zero-padded and stripped spellings of a CIK. All current write paths store the
    zero-padded 10-digit form; matching both is defensive hardening, not a fix for a known
    unpadded writer (data-quality plan P0-1)."""
    raw = str(cik).strip()
    stripped = raw.lstrip("0") or "0"
    padded = stripped.zfill(10)
    return list(dict.fromkeys([raw, padded, stripped]))


def resolve_or_create_company_by_cik(
    db: Session,
    *,
    cik: str,
    ticker: str,
    name: str,
    exchange: Optional[str] = None,
    path: str,
    canonical_ticker: Optional[str] = None,
) -> Company:
    """Return the Company row for ``cik``, creating it only when the CIK is genuinely new.

    Does not commit — callers own the transaction. ``path`` labels the call site in the
    ``company_upsert_conflict`` structured log line (interim safeguard 2) so any recurrence is
    attributable in Cloud Run logs.

    ``canonical_ticker`` (P0-1): when provided, a found row whose ticker differs is self-healed
    to it — so an endpoint that resolves a corrupted row (e.g. JPMorgan stored as ``JPM-PM``)
    never serves a quote/URL under the wrong ticker between the search-fix deploy and the repair
    run, and any row the repair misses heals on first touch. Pass ONLY the true primary
    (``compat.primary_ticker_for_cik``); None (CIK not in the SEC file) leaves the ticker as-is.
    """
    forms = _cik_forms(cik)
    company = db.query(Company).filter(Company.cik.in_(forms)).first()
    if company is not None:
        if canonical_ticker and company.ticker != canonical_ticker:
            company.ticker = canonical_ticker
        return company

    company = Company(cik=cik, ticker=ticker, name=name, exchange=exchange)
    try:
        with db.begin_nested():  # SAVEPOINT: a unique-CIK clash must not poison the transaction
            db.add(company)
            db.flush()
    except IntegrityError:
        logger.warning(
            "company_upsert_conflict cik=%s ticker=%s path=%s", cik, ticker, path
        )
        company = db.query(Company).filter(Company.cik.in_(forms)).first()
        if company is None:
            raise
    return company
