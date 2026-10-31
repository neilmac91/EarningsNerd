"""Company search answers from the cached SEC ticker file only (CODE RED decision record 17).

The EdgarTools fuzzy fallback that used to run when local search found nothing always failed (it
built the company model with field names the model does not have) after up to ten submissions
downloads on the event-loop thread, so it never returned a company. It is deleted; an unmatched
query now returns [] without any edgartools call.
"""
import pytest

from app.services.edgar import client as edgar_client_module
from app.services.edgar.compat import sec_edgar_service

TICKERS = {"0": {"ticker": "AAPL", "title": "Apple Inc.", "cik_str": 320193}}


class _EdgartoolsCalled(BaseException):
    """Not an Exception, so no `except Exception` in the code under test can swallow it."""


@pytest.mark.asyncio
async def test_unmatched_query_returns_empty_without_any_edgartools_call(monkeypatch):
    async def cached_tickers():
        return TICKERS

    def no_edgartools(*args, **kwargs):
        raise _EdgartoolsCalled("company search must not build an edgartools Company")

    monkeypatch.setattr(sec_edgar_service, "_get_cached_tickers", cached_tickers)
    monkeypatch.setattr(edgar_client_module, "EdgarCompany", no_edgartools)

    assert await sec_edgar_service.search_company("no such company xyz") == []
    assert [row["ticker"] for row in await sec_edgar_service.search_company("aapl")] == ["AAPL"]
    assert not hasattr(edgar_client_module.EdgarClient, "search_company")
    assert not hasattr(edgar_client_module.EdgarClient, "get_company")
