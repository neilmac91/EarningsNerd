"""Fill an unknown ``Company.sic`` from SEC before a company's companyfacts are normalized.

The SIC decides whether a filer's revenue is read as a financial filer's reported total (``fi_revenue``, SIC
6000-6799) or from the generic revenue tags, whose first is a bank's ASC 606 fee line, and the rows a sync writes stay:
a resync skips identities already stored. No code that creates a ``Company`` asks SEC for its SIC (the search path
makes no SEC call), so a company whose ``sic`` is NULL has it looked up here, after its companyfacts payload is
fetched and before anything is normalized, through the transport ``backfill_company_sic`` uses
(``edgar.company_sic``: the shared SEC limiter and the EDGAR breaker). It runs where the companyfacts fetch runs, never
inside the persist (which takes the row lock): on the request path (``ingest_companyfacts_by_id``) with no connection
checked out; on the caller-owned paths (``ingest_companyfacts``, the backfill) inside whatever read transaction the
caller's session already holds through that fetch. What SEC answers decides what is stored:

- SEC lists a SIC: it is stored with the facts, in the persist's transaction (the backfill: its filing's), and never
  looked up again.
- SEC lists none (``fetch_company_sic`` returns None, as for some BDCs and trusts): ``NO_SIC``, an empty string, is
  stored, so the company is not looked up again, and is read as a non-financial filer, as every reader of
  ``Company.sic`` reads an empty string. A WARNING names it, the one time.
- The lookup fails (a network error, a timeout, an open breaker): the sync stores nothing, as for a failed
  companyfacts fetch, so it is not stamped and its next touch retries (the backfill's cross-check counts the company
  unavailable). Storing it as a non-financial filer would read a bank's fee line as its revenue for good. A WARNING
  names the company.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from app.services.facts.concepts import _is_financial_sic
from app.services.facts.transport import logger

NO_SIC = ""  # "SEC lists no SIC for this company", where NULL is "not looked up yet"


def _sic_to_store(cik: str, found: Optional[tuple[str, Optional[str]]]) -> str:
    if found:
        return found[0]
    logger.warning("companyfacts SIC lookup: SEC lists no SIC for CIK %s; it is read as a non-financial filer", cik)
    return NO_SIC


async def fetch_with_sic(
    fetch: Callable[[str], Awaitable[Optional[dict[str, Any]]]], cik: str, sic: Optional[str],
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """``fetch(cik)``'s payload, and the SIC to store with it when the stored ``sic`` is None (else None).

    The payload is None when the fetch failed, or when the SIC is unknown and SEC could not be asked: the caller
    treats both as a failed fetch. Run it between the sync's database units, never inside one."""
    payload = await fetch(cik)
    if payload is None or sic is not None:
        return payload, None
    from app.services.edgar.company_sic import fetch_company_sic

    try:
        found = await fetch_company_sic(cik)
    except Exception as exc:  # noqa: BLE001 - a failed lookup is a failed fetch: no stamp, retry on next touch
        logger.warning("companyfacts sync stores nothing for CIK %s: its SIC is unknown and the SEC lookup failed: %s",
                       cik, exc)
        return None, None
    return payload, _sic_to_store(cik, found)


def fetch_with_sic_sync(
    fetch: Callable[[str], Optional[dict[str, Any]]], company: Any, *, store: bool,
) -> tuple[Optional[dict[str, Any]], bool]:
    """The backfill cross-check's companyfacts payload for ``company``, and whether it is a financial filer.

    An unknown SIC is looked up after the fetch, and written to ``company`` when ``store`` is set (the backfill's
    commit stores it). The payload is None when the fetch failed or the lookup did, so the cross-check counts the
    company as unavailable and leaves its flags alone, as for a failed fetch."""
    cik = getattr(company, "cik", None)
    payload = fetch(cik) if cik else None
    sic = getattr(company, "sic", None)
    if not payload or sic is not None:
        return payload, _is_financial_sic(sic)
    from app.services.edgar.company_sic import fetch_company_sic_sync

    try:
        sic = _sic_to_store(cik, fetch_company_sic_sync(cik))
    except Exception as exc:  # noqa: BLE001 - the cross-check is best-effort, never break the backfill
        logger.warning("facts backfill cross-check skipped for CIK %s: its SIC is unknown and the SEC lookup "
                       "failed: %s", cik, exc)
        return None, False
    if store:
        company.sic = sic
    return payload, _is_financial_sic(sic)
