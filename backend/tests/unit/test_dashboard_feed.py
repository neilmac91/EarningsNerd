"""Dashboard feed — deterministic "what changed" delta (pure) + feed composition (DB)."""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from app.services.dashboard_feed_service import compose_feed, compute_what_changed


def _series(*pairs):
    """[(period, value), ...] -> xbrl series list."""
    return [{"period": p, "value": v, "form": "10-Q", "accn": "x"} for p, v in pairs]


# --------------------------------------------------------------------------- pure delta

def test_revenue_and_net_income_headline():
    current = {"revenue": _series(("2024-03-31", 100.0)), "net_income": _series(("2024-03-31", 20.0))}
    prior = {"revenue": _series(("2023-03-31", 80.0)), "net_income": _series(("2023-03-31", 25.0))}
    out = compute_what_changed(current, prior)
    assert out is not None
    assert out["data_quality"] == "ok"
    assert "Revenue up 25.0%" in out["headline"]
    assert "Net income down 20.0%" in out["headline"]
    metrics = {i["metric"]: i for i in out["items"]}
    assert metrics["revenue"]["direction"] == "up"
    assert metrics["net_income"]["direction"] == "down"


def test_negative_revenue_is_dropped_partial():
    current = {"revenue": _series(("2024-03-31", -5.0)), "net_income": _series(("2024-03-31", 20.0))}
    prior = {"revenue": _series(("2023-03-31", 80.0)), "net_income": _series(("2023-03-31", 10.0))}
    out = compute_what_changed(current, prior)
    assert out["data_quality"] == "partial"
    assert all(i["metric"] != "revenue" for i in out["items"])
    assert any(i["metric"] == "net_income" for i in out["items"])


def test_eps_netincome_sign_mismatch_drops_both():
    # Positive EPS but a net loss → distrust both.
    current = {
        "revenue": _series(("2024-03-31", 100.0)),
        "net_income": _series(("2024-03-31", -10.0)),
        "earnings_per_share": _series(("2024-03-31", 1.5)),
    }
    prior = {
        "revenue": _series(("2023-03-31", 90.0)),
        "net_income": _series(("2023-03-31", -5.0)),
        "earnings_per_share": _series(("2023-03-31", 1.0)),
    }
    out = compute_what_changed(current, prior)
    assert out["data_quality"] == "partial"
    present = {i["metric"] for i in out["items"]}
    assert "earnings_per_share" not in present
    assert "net_income" not in present
    assert "revenue" in present  # revenue survives


def test_matching_negative_signs_are_kept():
    # Net loss with negative EPS is internally consistent → kept.
    current = {"net_income": _series(("2024-03-31", -10.0)), "earnings_per_share": _series(("2024-03-31", -0.5))}
    prior = {"net_income": _series(("2023-03-31", -5.0)), "earnings_per_share": _series(("2023-03-31", -0.2))}
    out = compute_what_changed(current, prior)
    assert {i["metric"] for i in out["items"]} == {"net_income", "earnings_per_share"}


def test_in_instance_comparative_used_when_no_prior_filing():
    # No prior filing, but the current filing's own series carries an older comparative period.
    current = {"revenue": _series(("2024-03-31", 120.0), ("2023-03-31", 100.0))}
    out = compute_what_changed(current, None)
    assert out is not None
    assert out["items"][0]["direction"] == "up"
    assert out["items"][0]["pct"] == 20.0


def test_missing_xbrl_returns_none():
    assert compute_what_changed(None, None) is None
    assert compute_what_changed({}, {}) is None


def test_no_prior_returns_none():
    # Single period, no prior anywhere → nothing to compare.
    assert compute_what_changed({"revenue": _series(("2024-03-31", 100.0))}, None) is None


# --------------------------------------------------------------------------- composition (DB)

@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@contextmanager
def _feed_scenario():
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"feed-{suffix}@example.com", hashed_password="x", email_verified=True, is_active=True)
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4].upper()}", name=f"Co {suffix}")
    db.add_all([user, company])
    db.commit()
    db.refresh(user)
    db.refresh(company)

    def _filing(accession, ftype, date_str, xbrl):
        return Filing(
            company_id=company.id,
            accession_number=accession,
            filing_type=ftype,
            filing_date=datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
            document_url=f"https://sec.example/{accession}/doc.htm",
            sec_url=f"https://sec.example/{accession}/",
            xbrl_data=xbrl,
        )

    older = _filing(f"{suffix}-old", "10-Q", "2023-03-31", {"revenue": _series(("2023-03-31", 80.0))})
    newer = _filing(f"{suffix}-new", "10-Q", "2024-03-31", {"revenue": _series(("2024-03-31", 100.0))})
    eightk = _filing(f"{suffix}-8k", "8-K", "2024-04-01", None)
    db.add_all([older, newer, eightk])
    db.commit()
    db.refresh(newer)
    # A ready summary for the newest filing.
    db.add(Summary(filing_id=newer.id, business_overview="A real overview of the business."))
    db.add(Watchlist(user_id=user.id, company_id=company.id))
    db.commit()

    ids = (user.id, company.id, newer.id, company.ticker)
    db.close()
    try:
        yield ids
    finally:
        db = SessionLocal()
        from app.models import Company, Filing, Summary, User, Watchlist
        fids = [f.id for f in db.query(Filing).filter(Filing.company_id == ids[1]).all()]
        db.query(Summary).filter(Summary.filing_id.in_(fids)).delete(synchronize_session=False)
        db.query(Watchlist).filter(Watchlist.user_id == ids[0]).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.company_id == ids[1]).delete(synchronize_session=False)
        db.query(Company).filter(Company.id == ids[1]).delete(synchronize_session=False)
        db.query(User).filter(User.id == ids[0]).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_compose_feed_orders_filters_and_annotates():
    from app.database import SessionLocal

    with _feed_scenario() as (uid, cid, newer_id, ticker):
        db = SessionLocal()
        items = compose_feed(db, uid, limit=20)
        db.close()

        # 8-K excluded; both 10-Qs present; newest first.
        assert [it["filing_type"] for it in items] == ["10-Q", "10-Q"]
        assert items[0]["filing_id"] == newer_id
        assert items[0]["company"]["ticker"] == ticker
        # Newest has a ready summary and an "up" revenue headline vs the prior 10-Q.
        assert items[0]["summary_status"] == "ready"
        assert items[0]["what_changed"] is not None
        assert items[0]["what_changed"]["items"][0]["direction"] == "up"
        # Oldest has no prior → no headline, missing summary.
        assert items[1]["what_changed"] is None
        assert items[1]["summary_status"] == "missing"


@pytest.mark.requires_db
def test_compose_feed_empty_for_no_watchlist():
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = User(email=f"nofeed-{uuid.uuid4().hex}@example.com", hashed_password="x", email_verified=True)
    db.add(user)
    db.commit()
    uid = user.id
    try:
        assert compose_feed(db, uid, limit=20) == []
    finally:
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()
