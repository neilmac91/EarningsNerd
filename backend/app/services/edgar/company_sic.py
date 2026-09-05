"""Rate-limited SIC lookup for the synchronous, founder-triggered backfill."""
import asyncio

from app.services.event_loop import get_app_loop
from app.services.sec_rate_limiter import sec_rate_limiter
from .async_executor import run_with_circuit_breaker
from .client import EdgarCompany


async def fetch_company_sic(cik: str) -> tuple[str, str | None] | None:
    def fetch():
        company = EdgarCompany(cik)
        sic = company.sic
        return (str(sic), company.industry) if sic else None

    async def limited_fetch():
        return await run_with_circuit_breaker(fetch)

    return await sec_rate_limiter.execute(limited_fetch)


def fetch_company_sic_sync(cik: str) -> tuple[str, str | None] | None:
    # A synchronous caller inside a running loop would deadlock that loop.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Use fetch_company_sic from an async caller")
    loop = get_app_loop()
    if loop is None:
        return asyncio.run(fetch_company_sic(cik))
    future = asyncio.run_coroutine_threadsafe(fetch_company_sic(cik), loop)
    try:
        return future.result(timeout=600)
    except TimeoutError:
        future.cancel()
        raise
