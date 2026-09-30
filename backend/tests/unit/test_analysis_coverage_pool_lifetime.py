"""Coverage sync must not reserve the serving pool while SEC or a local leader is pending."""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import Company, Filing, FinancialFact
from app.routers import analysis
from app.services import facts_service


def _companyfacts_payload():
    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "val": 100_000_000,
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "accn": "0001326801-25-000001",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-02-01",
                            }
                        ]
                    }
                }
            }
        }
    }


@pytest.mark.parametrize("successful_fetch", [False, True])
@pytest.mark.asyncio
async def test_stalled_coverage_leader_and_follower_release_pool_for_filings(
    monkeypatch, tmp_path, successful_fetch,
):
    """Two same-ticker requests used to consume all four production pool slots while waiting."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'coverage-pool.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=0.05,
    )
    Company.__table__.create(engine)
    Filing.__table__.create(engine)
    FinancialFact.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as seed:
        company = Company(cik="0001326801", ticker="META", name="Meta Platforms")
        seed.add(company)
        seed.commit()
        company_id = company.id

    fetch_started = asyncio.Event()
    release_fetch = asyncio.Event()
    fetch_calls = 0

    async def stalled_fetch(_cik):
        nonlocal fetch_calls
        fetch_calls += 1
        fetch_started.set()
        await release_fetch.wait()
        return _companyfacts_payload() if successful_fetch else None

    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(facts_service, "_fetch_companyfacts_async", stalled_fetch)
    monkeypatch.setattr(analysis, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis, "COVERAGE_SYNC_WAIT_SECONDS", 1.0)
    facts_service._inflight_syncs.clear()

    request = SimpleNamespace(client=None)
    user = SimpleNamespace(id=1)
    first_db = sessions()
    second_db = sessions()
    first = asyncio.create_task(
        analysis.get_coverage("META", request=request, current_user=user, db=first_db)
    )
    second = asyncio.create_task(
        analysis.get_coverage("META", request=request, current_user=user, db=second_db)
    )
    try:
        await asyncio.wait_for(fetch_started.wait(), timeout=1.0)
        # Let the second request complete its short preflight and join the leader's event.
        for _ in range(20):
            if engine.pool.checkedout() == 0:
                break
            await asyncio.sleep(0)

        assert fetch_calls == 1
        assert engine.pool.checkedout() == 0

        # This is the checkout that GET /api/filings/company/META needs for its initial query.
        with sessions() as filings_db:
            assert filings_db.query(Company.id).filter(Company.id == company_id).scalar() == company_id

        release_fetch.set()
        responses = await asyncio.gather(first, second)
        assert all(response.ticker == "META" for response in responses)
        assert all(response.syncing is False for response in responses)
        assert fetch_calls == 1  # the follower joined the leader instead of starting another fetch

        with sessions() as verify_db:
            synced_at = verify_db.query(Company.facts_synced_at).filter_by(id=company_id).scalar()
            fact_count = verify_db.query(FinancialFact).filter_by(company_id=company_id).count()
        if successful_fetch:
            assert synced_at is not None
            assert fact_count > 0
            assert all(response.synced_at is not None for response in responses)

            # A new request reuses the persisted TTL stamp and does not call SEC again.
            ttl_db = sessions()
            try:
                ttl_response = await analysis.get_coverage(
                    "META", request=request, current_user=user, db=ttl_db
                )
            finally:
                ttl_db.close()
            assert ttl_response.synced_at is not None
            assert fetch_calls == 1
        else:
            assert synced_at is None
            assert fact_count == 0
    finally:
        release_fetch.set()
        await asyncio.gather(first, second, return_exceptions=True)
        first_db.close()
        second_db.close()
        facts_service._inflight_syncs.clear()
        engine.dispose()
