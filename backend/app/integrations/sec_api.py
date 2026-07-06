"""SEC EDGAR full-text search (EFTS) integration.

Wraps the public, keyless EDGAR full-text search endpoint
(``https://efts.sec.gov/LATEST/search-index``) which indexes the text of
filings *and* their exhibits since 2001. All requests carry the SEC-required
descriptive ``User-Agent`` and are routed through the shared
``sec_rate_limiter`` so we honour SEC's 10 req/sec fair-access policy.

This is intentionally a thin, direct ``httpx`` client rather than going through
EdgarTools: EFTS is a stable JSON API, and keeping it separate avoids stacking
another rate limiter on top of EdgarTools' internal one.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx

from app.config import settings
from app.services.sec_rate_limiter import sec_rate_limiter

logger = logging.getLogger(__name__)

# Display names come back as "Company Name (TICKER) (CIK 0000000000)" or
# "Company Name (CIK 0000000000)". Anchoring on the trailing CIK group means a
# parenthesised share class in the name (e.g. "Alphabet Inc. (Class A)") is kept
# with the company rather than mistaken for the ticker.
_DISPLAY_NAME_RE = re.compile(
    r"^(?P<company>.*?)(?:\s+\((?P<ticker>[^)]+)\))?\s+\(CIK\s+\d+\)\s*$"
)
_TICKER_RE = re.compile(r"[A-Za-z0-9.\-]{1,6}")


def _coerce_int(value: object) -> Optional[int]:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _first_str(items: object) -> Optional[str]:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _parse_display_name(name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split an EFTS display name into (company, ticker).

    Examples::

        "Apple Inc. (AAPL) (CIK 0000320193)"            -> ("Apple Inc.", "AAPL")
        "Alphabet Inc. (Class A) (GOOGL) (CIK 1652044)" -> ("Alphabet Inc. (Class A)", "GOOGL")
        "SOME TRUST (CIK 0001234567)"                   -> ("SOME TRUST", None)

    The token before the trailing ``(CIK ...)`` group is treated as the ticker
    only if it looks like one; otherwise (e.g. a share-class phrase) it is kept
    as part of the company name.
    """

    if not name:
        return None, None

    match = _DISPLAY_NAME_RE.match(name)
    if not match:
        return name.strip() or None, None

    company = (match.group("company") or "").strip() or None
    ticker = match.group("ticker")
    if ticker:
        ticker = ticker.strip()
        if _TICKER_RE.fullmatch(ticker):
            ticker = ticker.upper()
        else:
            # Not a real ticker (e.g. "Class A") — fold it back into the name.
            company = f"{company} ({ticker})" if company else f"({ticker})"
            ticker = None

    return company, ticker


def _build_urls(
    cik: Optional[str], accession_no: str, document: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Construct (filing index URL, matched-document URL) for a hit.

    Mirrors the archive-URL convention in ``edgar/client.py:_transform_filing``:
    CIK has leading zeros stripped, accession has dashes removed.
    """

    if not cik or not accession_no:
        return None, None

    cik_clean = cik.lstrip("0") or "0"
    accession_nodash = accession_no.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_nodash}/"
    document_url = index_url + document if document else index_url
    return index_url, document_url


@dataclass
class EftsHit:
    """A single filing matched by EDGAR full-text search."""

    accession_no: str
    form: Optional[str]
    filed_date: Optional[str]
    period_ending: Optional[str]
    cik: Optional[str]
    company: Optional[str]
    ticker: Optional[str]
    document: Optional[str]
    sec_url: Optional[str]
    document_url: Optional[str]
    # 8-K item numbers from `_source.items` (e.g. ["2.02", "9.01"]). Used to precisely detect
    # earnings-results 8-Ks (Item 2.02) — the request-side `&items=` EFTS param is undocumented and
    # behaves inconsistently, so we filter these client-side (strategy §appendix).
    items: List[str] = None  # type: ignore[assignment]  # defaulted to [] in _parse_hit


@dataclass
class EftsSearchResult:
    """Normalized EFTS response: total matches plus the current page of hits."""

    query: str
    total: int
    hits: List[EftsHit]


class SECFullTextSearchClient:
    """Asynchronous client for the EDGAR full-text search endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        user_agent: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._base_url = (base_url or settings.SEC_EFTS_BASE_URL).rstrip("/")
        timeout_value = timeout_seconds or settings.SEC_EFTS_TIMEOUT_SECONDS
        self._timeout = httpx.Timeout(timeout_value)
        self._user_agent = user_agent or settings.SEC_USER_AGENT
        # `transport` is an injection seam for tests (e.g. httpx.MockTransport).
        self._transport = transport

    def _headers(self) -> dict:
        return {"User-Agent": self._user_agent, "Accept": "application/json"}

    @staticmethod
    def _build_params(
        query: Optional[str],
        forms: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        ciks: Optional[str],
        from_offset: int,
    ) -> dict:
        # `q` is optional: EFTS accepts forms+date-only queries (live-verified 2026-07-06),
        # which is how the notable-filings scan pulls low-volume forms market-wide.
        params: dict = {"q": query} if query else {}
        if forms:
            params["forms"] = forms
        if start_date:
            params["startdt"] = start_date
        if end_date:
            params["enddt"] = end_date
        if ciks:
            params["ciks"] = ciks
        if from_offset:
            params["from"] = from_offset
        return params

    async def search(
        self,
        query: Optional[str] = None,
        forms: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ciks: Optional[str] = None,
        from_offset: int = 0,
    ) -> EftsSearchResult:
        """Run a full-text search against EDGAR.

        ``query`` may be omitted for forms+date-only listings, but only on the
        first page: EFTS returns HTTP 500 for ``from>0`` without a query term
        (observed live 2026-07-06), so that combination is rejected here.

        Raises ``SECRateLimitError`` if the rate limiter exhausts retries, or
        ``httpx.HTTPError`` on other transport/HTTP failures — callers map these
        to HTTP responses.
        """

        if from_offset and not query:
            raise ValueError("EFTS rejects pagination (from>0) on query-less searches")

        params = self._build_params(query, forms, start_date, end_date, ciks, from_offset)

        async def _do_request() -> dict:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(
                    self._base_url, params=params, headers=self._headers()
                )
                response.raise_for_status()
                return response.json()

        payload = await sec_rate_limiter.execute_with_backoff(_do_request)
        return self._parse_response(query or "", payload)

    @staticmethod
    def _parse_response(query: str, payload: object) -> EftsSearchResult:
        if not isinstance(payload, dict):
            return EftsSearchResult(query=query, total=0, hits=[])

        hits_root = payload.get("hits") if isinstance(payload.get("hits"), dict) else {}
        total_obj = hits_root.get("total") if isinstance(hits_root.get("total"), dict) else {}
        total = _coerce_int(total_obj.get("value")) or 0

        raw_hits = hits_root.get("hits") if isinstance(hits_root.get("hits"), list) else []
        hits: List[EftsHit] = []
        for item in raw_hits:
            hit = SECFullTextSearchClient._parse_hit(item)
            if hit:
                hits.append(hit)

        return EftsSearchResult(query=query, total=total, hits=hits)

    @staticmethod
    def _parse_hit(item: object) -> Optional[EftsHit]:
        if not isinstance(item, dict):
            return None

        source = item.get("_source") if isinstance(item.get("_source"), dict) else {}

        # `_id` is "{accession-with-dashes}:{matched-document-filename}".
        raw_id = item.get("_id")
        accession_no = ""
        document: Optional[str] = None
        if isinstance(raw_id, str) and raw_id:
            if ":" in raw_id:
                accession_no, document = raw_id.split(":", 1)
            else:
                accession_no = raw_id

        if not accession_no:
            return None

        form = source.get("root_form") or source.get("file_type") or None
        filed_date = source.get("file_date")
        period_ending = source.get("period_ending")

        cik = _first_str(source.get("ciks"))
        company, ticker = _parse_display_name(_first_str(source.get("display_names")))
        sec_url, document_url = _build_urls(cik, accession_no, document)

        raw_items = source.get("items")
        items = [str(i).strip() for i in raw_items if str(i).strip()] if isinstance(raw_items, list) else []

        return EftsHit(
            accession_no=accession_no,
            form=form,
            filed_date=filed_date,
            period_ending=period_ending,
            cik=cik,
            company=company,
            ticker=ticker,
            document=document,
            sec_url=sec_url,
            document_url=document_url,
            items=items,
        )


sec_full_text_search_client = SECFullTextSearchClient()
