"""Sitemap for the www frontend.

Consumed by the frontend's `app/sitemap.ts`, which proxies this hourly (ISR) and re-bases
every URL onto the canonical www origin — crawlers read the frontend copy, not this endpoint
directly (the API host's robots.txt disallows crawling).

Crawler-facing correctness rules:
- `lastmod` must be truthful. Company pages use their newest filing's date; filing pages use
  the filing date; static pages emit none. (The old behavior — stamping "today" on every
  entry, every day — teaches Google to distrust the field sitemap-wide.)
- Only advertise pages that really have content: companies with at least one filing, and
  filings with a generated summary. Summary-less filing pages are noindex stubs on the
  frontend, and a sitemap must never list noindex'd URLs.
- The whole document is served from a per-process cache: the previous implementation ran two
  unbounded full-table scans per request with no cache, which made `GET /sitemap.xml` the
  cheapest way for a crawler to hammer the shared-core Cloud SQL instance.
"""

import threading
import time

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, Filing, Summary

router = APIRouter()

BASE_URL = "https://www.earningsnerd.io"

# Static frontend routes worth indexing: (path, changefreq, priority)
STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/pricing", "weekly", "0.8"),
    ("/contact", "monthly", "0.5"),
    ("/privacy", "yearly", "0.3"),
    ("/terms", "yearly", "0.3"),
    ("/security", "yearly", "0.3"),
]

# The sitemap protocol caps a file at 50k URLs; stay under it with headroom. Newest filings
# win (the query orders by filing_date DESC). Past this, move to a sitemap index — roadmap.
MAX_FILING_URLS = 45_000

_CACHE_TTL_SECONDS = 3600
_cache_lock = threading.Lock()
# Single-flight guard for cold-cache rebuilds: concurrent requests that miss the cache queue
# here while ONE of them runs the DB build, then serve its result via the double-check below.
# Deliberately a sync endpoint + threading.Lock (NOT async def + asyncio.Lock): the build's
# synchronous SQLAlchemy queries would block the event loop inside an async endpoint, stalling
# every request on the instance; in the threadpool they only occupy worker threads.
_build_lock = threading.Lock()
_cached_xml: str | None = None
_cached_at: float = 0.0


def reset_sitemap_cache() -> None:
    """Test hook: drop the cached document so the next request rebuilds it."""
    global _cached_xml, _cached_at
    with _cache_lock:
        _cached_xml = None
        _cached_at = 0.0


def _url_entry(loc: str, changefreq: str, priority: str, lastmod: str | None = None) -> str:
    lastmod_line = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    return (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"{lastmod_line}"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>\n"
    )


def _build_sitemap(db: Session) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n',
    ]

    for path, changefreq, priority in STATIC_PAGES:
        parts.append(_url_entry(f"{BASE_URL}{path}", changefreq, priority))

    # Companies with at least one filing (an empty company page is a stub not worth crawling);
    # lastmod = the newest filing's date, i.e. the last time the page's content actually changed.
    company_rows = (
        db.query(Company.ticker, func.max(Filing.filing_date))
        .join(Filing, Filing.company_id == Company.id)
        .group_by(Company.ticker)
        .all()
    )
    for ticker, latest_filing_date in company_rows:
        if not ticker:
            continue
        lastmod = latest_filing_date.strftime("%Y-%m-%d") if latest_filing_date else None
        parts.append(
            _url_entry(f"{BASE_URL}/company/{ticker.upper()}", "weekly", "0.7", lastmod)
        )

    # Only filings with a generated summary: the frontend noindexes summary-less filing pages
    # (they are signup-gate stubs), and advertising noindex'd URLs wastes crawl budget.
    filing_rows = (
        db.query(Filing.id, Filing.filing_date)
        .join(Summary, Summary.filing_id == Filing.id)
        .filter(Summary.business_overview.isnot(None))
        .filter(Summary.business_overview != "")
        .order_by(Filing.filing_date.desc())
        .limit(MAX_FILING_URLS)
        .all()
    )
    for filing_id, filing_date in filing_rows:
        lastmod = filing_date.strftime("%Y-%m-%d") if filing_date else None
        parts.append(_url_entry(f"{BASE_URL}/filing/{filing_id}", "monthly", "0.6", lastmod))

    parts.append("</urlset>")
    return "".join(parts)


def _fresh_cached_response() -> Response | None:
    with _cache_lock:
        if _cached_xml is not None and time.monotonic() - _cached_at < _CACHE_TTL_SECONDS:
            return Response(content=_cached_xml, media_type="application/xml")
    return None


@router.get("/sitemap.xml")
def generate_sitemap(db: Session = Depends(get_db)):
    """XML sitemap: static pages + company pages + summarized-filing pages, cached 1h."""
    global _cached_xml, _cached_at
    cached = _fresh_cached_response()
    if cached is not None:
        return cached

    with _build_lock:
        # Double-check: whoever acquired the lock first already rebuilt for everyone queued.
        cached = _fresh_cached_response()
        if cached is not None:
            return cached

        xml = _build_sitemap(db)
        with _cache_lock:
            _cached_xml = xml
            _cached_at = time.monotonic()
    return Response(content=xml, media_type="application/xml")
