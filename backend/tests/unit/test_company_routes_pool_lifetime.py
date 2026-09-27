"""Company routes must release serving connections before SEC and Yahoo waits."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.models import Company, Filing
from app.routers import companies


class _Stall:
    def __init__(self, expected: int, result):
        self.expected = expected
        self.result = result
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == self.expected:
            self.started.set()
        await self.release.wait()
        return self.result(*_args, **_kwargs) if callable(self.result) else self.result


def _sessions(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _assert_competing_checkout(sessions, company_id):
    with sessions() as competing:
        assert competing.query(Company.id).filter_by(id=company_id).scalar() == company_id


async def _wait_for_released_pool(stall, engine, sessions, company_id):
    await asyncio.wait_for(stall.started.wait(), timeout=1.0)
    for _ in range(20):
        if engine.pool.checkedout() == 0:
            break
        await asyncio.sleep(0)
    assert engine.pool.checkedout() == 0
    _assert_competing_checkout(sessions, company_id)


@pytest.mark.asyncio
async def test_company_route_network_phases_release_pool(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'company-route-pool.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=0.05,
    )
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    sessions = _sessions(engine)
    with sessions() as seed:
        anchor = Company(cik="0000000001", ticker="ANCH", name="Anchor")
        seed.add(anchor)
        seed.commit()
        anchor_id = anchor.id

    async def primary_ticker(cik):
        return f"MISS{int(cik[-1])}"

    monkeypatch.setattr(companies.sec_edgar_service, "primary_ticker_for_cik", primary_ticker)

    # A successful company miss has two network boundaries: SEC resolution before persistence,
    # then Yahoo after persistence. Neither may retain one of the four serving connections.
    sec_stall = _Stall(
        4,
        lambda ticker: [{
            "cik": f"000000010{ticker[-1]}",
            "ticker": ticker,
            "name": f"Missing {ticker[-1]}",
            "exchange": "NASDAQ",
        }],
    )
    quote_stall = _Stall(4, None)
    monkeypatch.setattr(companies.sec_edgar_service, "search_company", sec_stall)
    monkeypatch.setattr(companies, "get_stock_quote", quote_stall)
    miss_sessions = [sessions() for _ in range(4)]
    miss_tasks = [
        asyncio.create_task(companies.get_company(f"MISS{index}", db=miss_sessions[index]))
        for index in range(4)
    ]
    try:
        await _wait_for_released_pool(sec_stall, engine, sessions, anchor_id)
        sec_stall.release.set()
        await _wait_for_released_pool(quote_stall, engine, sessions, anchor_id)
        quote_stall.release.set()
        miss_responses = await asyncio.gather(*miss_tasks)
        assert [response.ticker for response in miss_responses] == [
            "MISS0", "MISS1", "MISS2", "MISS3",
        ]
    finally:
        sec_stall.release.set()
        quote_stall.release.set()
        await asyncio.gather(*miss_tasks, return_exceptions=True)
        for db in miss_sessions:
            db.close()

    with sessions() as verify:
        assert verify.query(Company).filter(Company.ticker.like("MISS%")).count() == 4

    # Search preserves SEC result order and releases its completed read/upsert transaction before
    # the bounded quote fan-out.
    async def search_results(_query):
        return [
            {"cik": "0000000101", "ticker": "MISS1", "name": "Missing 1", "exchange": "NASDAQ"},
            {"cik": "0000000100", "ticker": "MISS0", "name": "Missing 0", "exchange": "NASDAQ"},
        ]

    search_quote_stall = _Stall(8, None)
    monkeypatch.setattr(companies.sec_edgar_service, "search_company", search_results)
    monkeypatch.setattr(companies, "get_stock_quote", search_quote_stall)
    search_sessions = [sessions() for _ in range(4)]
    search_tasks = [
        asyncio.create_task(companies.search_companies("Missing", db=db))
        for db in search_sessions
    ]
    try:
        await _wait_for_released_pool(search_quote_stall, engine, sessions, anchor_id)
        search_quote_stall.release.set()
        search_responses = await asyncio.gather(*search_tasks)
        assert all([row.ticker for row in response] == ["MISS1", "MISS0"] for response in search_responses)
    finally:
        search_quote_stall.release.set()
        await asyncio.gather(*search_tasks, return_exceptions=True)
        for db in search_sessions:
            db.close()

    # Trending materializes scalar rows, closes its read transaction, then awaits Yahoo.
    with sessions() as seed:
        company = seed.query(Company).filter_by(ticker="MISS0").one()
        seed.add(Filing(
            company_id=company.id,
            accession_number="0000000100-26-000001",
            filing_type="10-K",
            filing_date=datetime.now(timezone.utc),
            document_url="https://example.test/filing",
            sec_url="https://example.test/filing/",
        ))
        seed.commit()

    trending_quote_stall = _Stall(4, None)
    monkeypatch.setattr(companies, "get_stock_quote", trending_quote_stall)
    trending_sessions = [sessions() for _ in range(4)]
    trending_tasks = [
        asyncio.create_task(companies.get_trending_companies(limit=10, db=db))
        for db in trending_sessions
    ]
    try:
        await _wait_for_released_pool(trending_quote_stall, engine, sessions, anchor_id)
        trending_quote_stall.release.set()
        trending_responses = await asyncio.gather(*trending_tasks)
        assert all([row.ticker for row in response] == ["MISS0"] for response in trending_responses)
    finally:
        trending_quote_stall.release.set()
        await asyncio.gather(*trending_tasks, return_exceptions=True)
        for db in trending_sessions:
            db.close()
        engine.dispose()
