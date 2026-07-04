"""One-time purge of non-index earnings rows: dry-run/execute semantics + the empty-list safety guard."""
from datetime import date

import pytest

from scripts.purge_non_index_earnings import purge


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _seed(db, ticker):
    from app.models import EarningsEvent

    db.add(EarningsEvent(
        ticker=ticker, company_name="x", fiscal_period_end=date(2026, 3, 31),
        event_date=date(2026, 7, 20), status="estimated", confidence="medium", source="alpha_vantage",
    ))


@pytest.mark.requires_db
def test_purge_dry_run_then_execute_removes_only_non_members():
    from app.database import SessionLocal
    from app.models import EarningsEvent
    from app.services import index_membership_service as idx

    db = SessionLocal()
    try:
        db.query(EarningsEvent).filter(EarningsEvent.ticker.in_(["PMEMBER", "PTAIL"])).delete(
            synchronize_session=False
        )
        db.commit()
        _seed(db, "PMEMBER")
        _seed(db, "PTAIL")
        db.commit()

        # Members = every ticker currently present EXCEPT our non-member sentinel, unioned with the
        # real universe so the set clears the sanity floor. Keeps the test isolated: only PTAIL is a
        # "non-member," so the purge can't disturb rows other tests left behind.
        keep = {t for (t,) in db.query(EarningsEvent.ticker).distinct() if t != "PTAIL"}
        members = frozenset(keep | idx.member_tickers())

        # Dry run: reports 1 would-delete, mutates nothing.
        res = purge(db, dry_run=True, members=members)
        assert res["deleted"] == 1
        assert db.query(EarningsEvent).filter(EarningsEvent.ticker == "PTAIL").count() == 1

        # Execute: the non-member is gone, the member stays.
        res = purge(db, dry_run=False, members=members)
        assert res["deleted"] == 1
        assert db.query(EarningsEvent).filter(EarningsEvent.ticker == "PTAIL").count() == 0
        assert db.query(EarningsEvent).filter(EarningsEvent.ticker == "PMEMBER").count() == 1
    finally:
        db.query(EarningsEvent).filter(EarningsEvent.ticker.in_(["PMEMBER", "PTAIL"])).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_purge_refuses_to_run_against_a_short_member_set():
    """The critical guard: purging against an empty/short member set would delete the whole calendar,
    so it must raise instead of running."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            purge(db, dry_run=True, members=frozenset({"AAPL"}))
    finally:
        db.close()
