"""Route characterization for /api/watchlist add / list / remove / insights.

These four routes had no route-level test. The suite pins their status codes, bodies, ordering and
the insights summary-status mapping so the move of their queries into
``app/services/watchlist_service.py`` is provably behaviour-neutral. Rows live in the shared test
DB (``get_generation_progress_snapshot`` opens its own ``SessionLocal``), so nothing is patched;
only ``get_current_user`` is overridden. Every row this file creates is deleted afterwards.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _cleanup_rows():
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary, SummaryGenerationProgress, User, Watchlist

    models = [User, Company, Watchlist, Filing, Summary]
    db = SessionLocal()
    before = {m: {r[0] for r in db.query(m.id).all()} for m in models}
    before_progress = {r[0] for r in db.query(SummaryGenerationProgress.filing_id).all()}
    db.close()
    yield
    db = SessionLocal()
    db.query(SummaryGenerationProgress).filter(
        ~SummaryGenerationProgress.filing_id.in_(before_progress)
    ).delete(synchronize_session=False)
    for m in (Summary, Watchlist, Filing, Company, User):
        db.query(m).filter(~m.id.in_(before[m])).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture()
def user_id():
    from main import app
    from app.database import SessionLocal
    from app.models import User
    from app.routers.auth import get_current_user

    db = SessionLocal()
    user = User(email=f"wl-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x", email_verified=True)
    db.add(user)
    db.commit()
    uid = user.id
    db.close()

    def _override():
        session = SessionLocal()
        try:
            return session.query(User).filter(User.id == uid).first()
        finally:
            session.close()

    app.dependency_overrides[get_current_user] = _override
    try:
        yield uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client():
    from main import app

    return TestClient(app)


def _company(ticker: str) -> int:
    from app.database import SessionLocal
    from app.models import Company

    db = SessionLocal()
    company = Company(cik=f"wl-{uuid.uuid4().hex[:10]}", ticker=ticker, name=f"{ticker} Inc")
    db.add(company)
    db.commit()
    cid = company.id
    db.close()
    return cid


def _watch(uid: int, cid: int, created_at: datetime) -> int:
    from app.database import SessionLocal
    from app.models import Watchlist

    db = SessionLocal()
    row = Watchlist(user_id=uid, company_id=cid, created_at=created_at)
    db.add(row)
    db.commit()
    rid = row.id
    db.close()
    return rid


def _filing(cid: int, ftype: str, filed: datetime) -> int:
    from app.database import SessionLocal
    from app.models import Filing

    db = SessionLocal()
    accession = uuid.uuid4().hex[:18]
    row = Filing(
        company_id=cid, accession_number=accession, filing_type=ftype, filing_date=filed,
        period_end_date=filed - timedelta(days=30),
        document_url=f"https://sec.example/{accession}/doc.htm", sec_url=f"https://sec.example/{accession}/",
    )
    db.add(row)
    db.commit()
    fid = row.id
    db.close()
    return fid


def _summary(fid: int, overview: str) -> int:
    from app.database import SessionLocal
    from app.models import Summary

    db = SessionLocal()
    row = Summary(filing_id=fid, business_overview=overview)
    db.add(row)
    db.commit()
    sid = row.id
    db.close()
    return sid


def _progress(fid: int, stage: str) -> None:
    from app.database import SessionLocal
    from app.models import SummaryGenerationProgress

    db = SessionLocal()
    db.add(SummaryGenerationProgress(filing_id=fid, stage=stage, elapsed_seconds=7.0, error=None))
    db.commit()
    db.close()


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_add_unknown_ticker_is_404(client, user_id):
    resp = client.post(f"/api/watchlist/ZZ{uuid.uuid4().hex[:4].upper()}")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Company not found"}


def test_add_returns_the_row_and_a_second_add_is_400(client, user_id):
    ticker = f"WA{uuid.uuid4().hex[:4].upper()}"
    cid = _company(ticker)
    resp = client.post(f"/api/watchlist/{ticker.lower()}")  # upper-cased by the lookup
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"id", "company_id", "created_at", "company"}
    assert body["company_id"] == cid and isinstance(body["id"], int) and body["created_at"]
    assert body["company"] == {"id": cid, "ticker": ticker, "name": f"{ticker} Inc"}

    again = client.post(f"/api/watchlist/{ticker}")
    assert again.status_code == 400
    assert again.json() == {"detail": "Company already in watchlist"}


def test_list_is_newest_first_with_company(client, user_id):
    older, newer = f"LO{uuid.uuid4().hex[:4].upper()}", f"LN{uuid.uuid4().hex[:4].upper()}"
    old_cid, new_cid = _company(older), _company(newer)
    old_row = _watch(user_id, old_cid, T0)
    new_row = _watch(user_id, new_cid, T0 + timedelta(days=1))

    resp = client.get("/api/watchlist/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [item["id"] for item in body] == [new_row, old_row]
    assert body[0]["company"] == {"id": new_cid, "ticker": newer, "name": f"{newer} Inc"}
    assert body[0]["company_id"] == new_cid and body[0]["created_at"].startswith("2026-01-02")


def test_remove_paths(client, user_id):
    missing = client.delete(f"/api/watchlist/ZZ{uuid.uuid4().hex[:4].upper()}")
    assert missing.status_code == 404 and missing.json() == {"detail": "Company not found"}

    ticker = f"RM{uuid.uuid4().hex[:4].upper()}"
    cid = _company(ticker)
    unwatched = client.delete(f"/api/watchlist/{ticker}")
    assert unwatched.status_code == 404 and unwatched.json() == {"detail": "Company not in watchlist"}

    _watch(user_id, cid, T0)
    resp = client.delete(f"/api/watchlist/{ticker.lower()}")
    assert resp.status_code == 200 and resp.json() == {"status": "success"}
    assert client.get("/api/watchlist/").json() == []


def test_insights_empty_watchlist(client, user_id):
    resp = client.get("/api/watchlist/insights")
    assert resp.status_code == 200 and resp.json() == []


def test_insights_status_mapping_ordering_and_tie_break(client, user_id):
    tag = uuid.uuid4().hex[:3].upper()
    tickers = {k: f"I{k}{tag}" for k in ("R", "P", "E", "G", "M", "N")}
    cids = {k: _company(t) for k, t in tickers.items()}
    for i, k in enumerate(("R", "P", "E", "G", "M", "N")):  # N is watched newest -> listed first
        _watch(user_id, cids[k], T0 + timedelta(hours=i))

    day = datetime(2026, 3, 1, tzinfo=timezone.utc)
    _filing(cids["R"], "10-Q", day - timedelta(days=90))
    low_tie = _filing(cids["R"], "10-K", day)
    high_tie = _filing(cids["R"], "10-Q", day)  # same day, higher id -> the "latest" filing
    _summary(low_tie, "A real overview.")
    ready_sid = _summary(high_tie, "A real overview of the business.")
    placeholder = _filing(cids["P"], "10-K", day)
    _summary(placeholder, "Generating summary... please wait")
    errored = _filing(cids["E"], "10-Q", day)
    _progress(errored, "error")
    generating = _filing(cids["G"], "10-Q", day)
    _progress(generating, "parsing")
    missing = _filing(cids["M"], "8-K", day)

    resp = client.get("/api/watchlist/insights")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [row["company"]["ticker"] for row in body] == [tickers[k] for k in ("N", "M", "G", "E", "P", "R")]
    by_ticker = {row["company"]["ticker"]: row for row in body}

    assert by_ticker[tickers["N"]] == {
        "company": {"id": cids["N"], "ticker": tickers["N"], "name": f"{tickers['N']} Inc"},
        "latest_filing": None,
        "total_filings": 0,
    }

    ready = by_ticker[tickers["R"]]
    assert ready["total_filings"] == 3
    snap = ready["latest_filing"]
    assert set(snap) == {
        "id", "filing_type", "filing_date", "period_end_date", "summary_id", "summary_status",
        "summary_created_at", "summary_updated_at", "needs_regeneration", "progress",
    }
    assert snap["id"] == high_tie and snap["filing_type"] == "10-Q"
    assert snap["summary_id"] == ready_sid and snap["summary_status"] == "ready"
    assert snap["needs_regeneration"] is False and snap["progress"] is None
    assert snap["filing_date"].startswith("2026-03-01") and snap["period_end_date"].startswith("2026-01-30")

    p = by_ticker[tickers["P"]]["latest_filing"]
    assert (p["id"], p["summary_status"], p["needs_regeneration"]) == (placeholder, "placeholder", True)

    e = by_ticker[tickers["E"]]["latest_filing"]
    assert (e["summary_id"], e["summary_status"], e["needs_regeneration"]) == (None, "error", True)
    assert e["progress"]["stage"] == "error" and e["progress"]["elapsedSeconds"] == 7

    g = by_ticker[tickers["G"]]["latest_filing"]
    assert (g["summary_status"], g["needs_regeneration"]) == ("generating:parsing", False)
    assert g["progress"]["stage"] == "parsing"

    m = by_ticker[tickers["M"]]["latest_filing"]
    assert (m["id"], m["summary_status"], m["needs_regeneration"], m["progress"]) == (missing, "missing", True, None)
    assert m["summary_created_at"] is None and m["summary_updated_at"] is None
