"""Financial-fact transport extracted from the facts_service facade."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Optional

from app.services.event_loop import get_app_loop
from app.services.facts.concepts import COMPANYFACTS_SYNC_TIMEOUT_SECONDS


logger = logging.getLogger("app.services.facts_service")


def _fetch_companyfacts_sync(cik: str) -> Optional[dict]:
    """Best-effort sync fetch of the companyfacts JSON for a CIK (used by the backfill job).

    A thin bridge onto ``_fetch_companyfacts_async`` so the backfill shares the SEC token bucket +
    backoff ladder in ``sec_rate_limiter`` (CLAUDE.md rule 5) instead of a bare ``httpx.Client`` with
    an ad-hoc sleep. Two sync callers, two loop strategies (see ``app/services/event_loop.py``):

    - API process (``/internal/jobs/backfill-facts`` BackgroundTask, run in FastAPI's threadpool
      while the app loop is live): the coroutine is handed to the registered app loop with
      ``run_coroutine_threadsafe`` — the limiter's ``asyncio.Lock`` must only ever be awaited on
      that loop, or a contended acquire could bind it to a throwaway loop and kill SEC traffic.
    - Standalone ``backfill-facts`` Cloud Run job (no loop registered): a private ``asyncio.run``.

    Returns ``None`` on any failure — the cross-check is optional and must never break the backfill.
    """
    try:
        if _running_loop_in_this_thread() is not None:
            # Blocking on .result() here would deadlock the very loop that must run the coroutine.
            logger.warning("companyfacts sync fetch skipped for CIK %s: called from inside a loop", cik)
            return None
        app_loop = get_app_loop()
        if app_loop is not None:
            future = asyncio.run_coroutine_threadsafe(_fetch_companyfacts_async(cik), app_loop)
            try:
                return future.result(timeout=COMPANYFACTS_SYNC_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                future.cancel()
                logger.warning("companyfacts sync fetch timed out for CIK %s", cik)
                return None
        return asyncio.run(_fetch_companyfacts_async(cik))
    except Exception as exc:  # noqa: BLE001 - best-effort, never break the backfill
        logger.warning("companyfacts sync fetch failed for CIK %s: %s", cik, exc)
        return None


def _running_loop_in_this_thread() -> Optional[asyncio.AbstractEventLoop]:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


async def _fetch_companyfacts_async(cik: str) -> Optional[dict]:
    """Async companyfacts fetch through the SEC rate limiter (the REQUEST-PATH fetcher).

    User-triggerable via the coverage endpoint, and also what the backfill's
    ``_fetch_companyfacts_sync`` bridges onto, so it MUST share the token bucket + exponential
    backoff in ``sec_rate_limiter``. Returns ``None`` on any failure, including a malformed CIK.
    """
    import httpx

    from app.config import settings
    from app.services.sec_rate_limiter import sec_rate_limiter
    from app.utils.sec_urls import companyfacts_url

    headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}

    try:
        url = companyfacts_url(cik)  # ValueError on a malformed CIK -> None, like any other failure

        async def _get() -> Any:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()

        data = await sec_rate_limiter.execute_with_backoff(_get)
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001 - the caller degrades gracefully (no stamp, retry later)
        logger.warning("companyfacts async fetch failed for CIK %s: %s", cik, exc)
        return None
