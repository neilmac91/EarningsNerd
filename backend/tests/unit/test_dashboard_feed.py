"""Dashboard feed — deterministic "what changed" delta (pure) + feed composition (DB)."""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

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
    # T1.5: chips carry the single-source display string + tone (no client-side formatting).
    assert metrics["revenue"]["display"] == "+25.0%" and metrics["revenue"]["tone"] == "gain"
    assert metrics["net_income"]["display"] == "−20.0%" and metrics["net_income"]["tone"] == "loss"


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


def test_negative_prior_revenue_is_dropped_partial():
    # A corrupt (negative) prior revenue must also invalidate the metric.
    current = {"revenue": _series(("2024-03-31", 100.0)), "net_income": _series(("2024-03-31", 20.0))}
    prior = {"revenue": _series(("2023-03-31", -80.0)), "net_income": _series(("2023-03-31", 10.0))}
    out = compute_what_changed(current, prior)
    assert out["data_quality"] == "partial"
    assert all(i["metric"] != "revenue" for i in out["items"])


def test_prior_eps_netincome_sign_mismatch_drops_both():
    # Prior period has positive EPS but a net loss → distrust both, even if current is consistent.
    current = {
        "net_income": _series(("2024-03-31", 10.0)),
        "earnings_per_share": _series(("2024-03-31", 0.5)),
    }
    prior = {
        "net_income": _series(("2023-03-31", -5.0)),
        "earnings_per_share": _series(("2023-03-31", 1.0)),
    }
    out = compute_what_changed(current, prior)
    assert out is None or out["data_quality"] == "partial"
    if out is not None:
        present = {i["metric"] for i in out["items"]}
        assert "earnings_per_share" not in present and "net_income" not in present


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


@contextmanager
def _multi_feed_scenario(company_specs, *, watchlist_all=True):
    """Build users/companies/filings/summaries for multi-company feed tests.

    ``company_specs``: one dict per company, in the order the companies are created:
        {
          "filings": [(label, filing_type, date_str, xbrl), ...],  # created in this order (id asc)
          "summary_labels": [label, ...],  # optional; filings that get a ready summary
        }
    Each filing ``label`` must be unique across the whole scenario. Yields a SimpleNamespace with
    ``user_id``, ``company_ids`` (creation order), ``tickers`` (creation order), and
    ``filing_ids`` (label -> id)."""
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"multifeed-{suffix}@example.com", hashed_password="x", email_verified=True, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    company_ids: list[int] = []
    tickers: list[str] = []
    filing_ids: dict[str, int] = {}
    for ci, spec in enumerate(company_specs):
        company = Company(cik=f"cik{suffix}{ci}", ticker=f"T{suffix[:3].upper()}{ci}", name=f"Co {suffix} {ci}")
        db.add(company)
        db.commit()
        db.refresh(company)
        company_ids.append(company.id)
        tickers.append(company.ticker)
        for label, ftype, date_str, xbrl in spec["filings"]:
            filing = Filing(
                company_id=company.id,
                accession_number=f"{suffix}-{label}",
                filing_type=ftype,
                filing_date=datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
                document_url=f"https://sec.example/{suffix}-{label}/doc.htm",
                sec_url=f"https://sec.example/{suffix}-{label}/",
                xbrl_data=xbrl,
            )
            db.add(filing)
            db.commit()  # commit per filing so ids are assigned in creation order (same-day tie-break)
            db.refresh(filing)
            filing_ids[label] = filing.id
        for label in spec.get("summary_labels", []):
            db.add(Summary(filing_id=filing_ids[label], business_overview="A real overview of the business."))
        if watchlist_all:
            db.add(Watchlist(user_id=user.id, company_id=company.id))
    db.commit()

    ns = SimpleNamespace(user_id=user.id, company_ids=company_ids, tickers=tickers, filing_ids=filing_ids)
    db.close()
    try:
        yield ns
    finally:
        db = SessionLocal()
        from app.models import Company, Filing, Summary, User, Watchlist
        fids = [f.id for f in db.query(Filing).filter(Filing.company_id.in_(company_ids)).all()]
        db.query(Summary).filter(Summary.filing_id.in_(fids)).delete(synchronize_session=False)
        db.query(Watchlist).filter(Watchlist.user_id == ns.user_id).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id == ns.user_id).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_compose_feed_orders_filters_and_annotates():
    from app.database import SessionLocal

    with _feed_scenario() as (uid, cid, newer_id, ticker):
        db = SessionLocal()
        items = compose_feed(db, uid, limit=20)
        db.close()

        # One card per company: the newest eligible filing (the newer 10-Q). The 8-K is ineligible
        # and the older 10-Q is not the company's newest, so neither surfaces.
        assert [it["filing_type"] for it in items] == ["10-Q"]
        assert items[0]["filing_id"] == newer_id
        assert items[0]["company"]["ticker"] == ticker
        # Newest has a ready summary and an "up" revenue headline computed against the prior 10-Q the
        # feed no longer returns — proving the what-changed comparison still reaches full history.
        assert items[0]["summary_status"] == "ready"
        assert items[0]["what_changed"] is not None
        assert items[0]["what_changed"]["items"][0]["direction"] == "up"


@pytest.mark.requires_db
def test_compose_feed_one_item_per_company():
    # The regression test for the old "newest N filings across the whole watchlist" bug: two
    # companies with two eligible filings each must yield exactly two items (one per company), each
    # that company's newest filing.
    from app.database import SessionLocal

    specs = [
        {"filings": [
            ("a-old", "10-Q", "2023-06-30", {"revenue": _series(("2023-06-30", 80.0))}),
            ("a-new", "10-Q", "2024-06-30", {"revenue": _series(("2024-06-30", 100.0))}),
        ]},
        {"filings": [
            ("b-old", "10-K", "2023-12-31", {"revenue": _series(("2023-12-31", 200.0))}),
            ("b-new", "10-K", "2024-12-31", {"revenue": _series(("2024-12-31", 250.0))}),
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert len(items) == 2
        assert sorted(it["company"]["id"] for it in items) == sorted(ns.company_ids)  # each once
        by_company = {it["company"]["id"]: it for it in items}
        assert by_company[ns.company_ids[0]]["filing_id"] == ns.filing_ids["a-new"]
        assert by_company[ns.company_ids[1]]["filing_id"] == ns.filing_ids["b-new"]


@pytest.mark.requires_db
def test_compose_feed_orders_companies_by_latest_filing_desc():
    from app.database import SessionLocal

    # Company A carries an extra older filing so the old "newest N filings across the watchlist" bug
    # would return three items (b-new, a-new, a-old); the fix returns two heads ordered by date desc.
    specs = [
        {"filings": [
            ("a-old", "10-Q", "2023-06-30", None),
            ("a-new", "10-Q", "2024-06-30", None),  # A's head (older than B's head)
        ]},
        {"filings": [("b-new", "10-K", "2024-12-31", None)]},  # newest head -> first
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert [it["filing_id"] for it in items] == [ns.filing_ids["b-new"], ns.filing_ids["a-new"]]


@pytest.mark.requires_db
def test_compose_feed_same_day_tie_breaks_by_id_desc():
    from app.database import SessionLocal

    # 10-Q created first, then a same-day 10-K -> the 10-K has the higher id and wins the tie.
    specs = [
        {"filings": [
            ("tie-q", "10-Q", "2024-03-31", None),
            ("tie-k", "10-K", "2024-03-31", None),
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert len(items) == 1
        assert items[0]["filing_id"] == max(ns.filing_ids["tie-q"], ns.filing_ids["tie-k"])
        assert items[0]["filing_id"] == ns.filing_ids["tie-k"]


@pytest.mark.requires_db
def test_compose_feed_limit_caps_company_count():
    from app.database import SessionLocal

    # Company C carries two filings, both newer than A and B. The old "newest N filings across the
    # watchlist" bug with limit=2 would return C's two filings (c, c-old) and drop B entirely; the
    # fix caps COMPANIES, so it returns one head each for the two newest companies (C, B).
    specs = [
        {"filings": [("a", "10-Q", "2024-01-31", None)]},  # stalest company -> dropped by limit=2
        {"filings": [("b", "10-Q", "2024-06-30", None)]},
        {"filings": [
            ("c-old", "10-K", "2024-11-30", None),
            ("c", "10-K", "2024-12-31", None),  # newest company's head
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=2)
        db.close()

        assert [it["filing_id"] for it in items] == [ns.filing_ids["c"], ns.filing_ids["b"]]
        assert ns.filing_ids["a"] not in {it["filing_id"] for it in items}
        assert ns.filing_ids["c-old"] not in {it["filing_id"] for it in items}


@pytest.mark.requires_db
def test_compose_feed_skips_companies_without_eligible_filings():
    from app.database import SessionLocal

    # Company A has an eligible 10-Q; company B has only an ineligible 8-K -> B is absent.
    specs = [
        {"filings": [("a-10q", "10-Q", "2024-06-30", None)]},
        {"filings": [("b-8k", "8-K", "2024-07-01", None)]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert [it["filing_id"] for it in items] == [ns.filing_ids["a-10q"]]
        assert ns.company_ids[1] not in {it["company"]["id"] for it in items}

    # A watchlist carrying only ineligible forms yields an empty feed.
    with _multi_feed_scenario([{"filings": [("only-8k", "8-K", "2024-07-01", None)]}]) as ns:
        db = SessionLocal()
        assert compose_feed(db, ns.user_id, limit=20) == []
        db.close()


@pytest.mark.requires_db
def test_compose_feed_what_changed_uses_prior_same_form_not_feed():
    from app.database import SessionLocal

    # Newest is a 10-Q (rev 120). Its prior SAME-FORM is the older 10-Q (rev 100) -> "up 20%". A
    # 10-K sits between them (rev 200); if the comparison used the nearest prior filing regardless of
    # form, the delta would read "down". Single-period xbrl on the head forces the prior value to
    # come from the prior filing, not an in-instance comparative.
    specs = [
        {"filings": [
            ("q-older", "10-Q", "2023-06-30", {"revenue": _series(("2023-06-30", 100.0))}),
            ("k-mid", "10-K", "2024-03-31", {"revenue": _series(("2024-03-31", 200.0))}),
            ("q-newest", "10-Q", "2024-06-30", {"revenue": _series(("2024-06-30", 120.0))}),
        ]},
    ]
    with _multi_feed_scenario(specs) as ns:
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()

        assert items[0]["filing_id"] == ns.filing_ids["q-newest"]
        rev = next(i for i in items[0]["what_changed"]["items"] if i["metric"] == "revenue")
        assert rev["direction"] == "up"
        assert rev["pct"] == 20.0


@pytest.mark.requires_db
def test_compose_feed_fpi_form_behind_flag(monkeypatch):
    from app.config import settings
    from app.database import SessionLocal

    specs = [{"filings": [("f-20f", "20-F", "2024-04-30", None)]}]
    with _multi_feed_scenario(specs) as ns:
        # Flag off (the default): the 20-F is ineligible, so the feed is empty.
        monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
        db = SessionLocal()
        assert compose_feed(db, ns.user_id, limit=20) == []
        db.close()

        # Flag on: the FPI annual report surfaces.
        monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
        db = SessionLocal()
        items = compose_feed(db, ns.user_id, limit=20)
        db.close()
        assert [it["filing_id"] for it in items] == [ns.filing_ids["f-20f"]]
        assert items[0]["filing_type"] == "20-F"


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


def test_feed_form_types_gated_by_fpi_flag(monkeypatch):
    """The feed adds FPI ANNUAL forms (20-F/40-F) behind the flag, but never 6-K (XBRL-less/noisy)."""
    from app.config import settings
    from app.services import dashboard_feed_service as svc

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    assert svc._feed_form_types() == ("10-K", "10-Q")

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    on = svc._feed_form_types()
    assert "20-F" in on and "40-F" in on
    assert "6-K" not in on  # deliberately excluded from the what-changed feed
