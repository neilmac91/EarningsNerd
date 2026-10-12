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
- The whole document stays under the protocol's 50,000-URL cap: static pages first, then
  companies and filings newest-first until ``MAX_SITEMAP_URLS`` is reached, so growth drops
  the least-recently-changed pages rather than producing a sitemap crawlers reject. A sitemap
  index (several files) is the next step only once the eligible set approaches the cap
  (E15b; the served document counted 574 URLs on 2026-09-07).
"""

import threading
import time

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.sitemap_service import _build_sitemap

router = APIRouter()

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
