"""Route characterization for /api/watchlist add / list / remove / insights.

These four routes had no route-level test. The suite pins their status codes, bodies, ordering and
the insights summary-status mapping so the move of their queries into
``app/services/watchlist_service.py`` is provably behaviour-neutral. Rows live in the shared test
DB, and the insights read their generation-progress rows in the request's own session, so nothing
is patched; only ``get_current_user`` is overridden. Every row this file creates is deleted afterwards.
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


def _summary(fid: int, overview: str, raw_summary: dict | None = None, risk_factors: list | None = None) -> int:
    from app.database import SessionLocal
    from app.models import Summary

    db = SessionLocal()
    row = Summary(filing_id=fid, business_overview=overview, raw_summary=raw_summary, risk_factors=risk_factors)
    db.add(row)
    db.commit()
    sid = row.id
    db.close()
    return sid


def _progress(fid: int, stage: str, *, age_seconds: float = 0, error: str | None = None) -> None:
    """The filing's progress row, last written ``age_seconds`` ago."""
    from app.database import SessionLocal
    from app.models import SummaryGenerationProgress
    from app.utils.datetimes import utcnow

    written = utcnow() - timedelta(seconds=age_seconds)
    db = SessionLocal()
    db.add(SummaryGenerationProgress(
        filing_id=fid, stage=stage, elapsed_seconds=7.0, error=error, started_at=written, updated_at=written,
    ))
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


@pytest.mark.parametrize(
    ("overview", "stored", "ready"),
    [
        pytest.param("A real overview of the business.", {}, True, id="an overview"),
        # Prose that mentions the phrase is content on the filing page, whose in-progress marker is case-sensitive.
        pytest.param("A real overview about generating summary reports.", {}, True, id="prose naming the phrase"),
        pytest.param("Generating summary... please wait", {}, False, id="the in-progress marker"),
        pytest.param("Summary temporarily unavailable. Please retry.", {}, False, id="failure filler"),
        pytest.param("", {}, False, id="an empty body"),
        pytest.param("A real overview of the business.", {"raw_summary": {"writer_error": "timeout"}}, False,
                     id="a writer error"),
        # The page is served an empty body's sections, rendered, a legacy row's risk list as its Risks section, and a
        # stored Risks section replaced, whatever it carried.
        pytest.param("", {"raw_summary": {"sections": {"executive_snapshot": {"headline": "Revenue rose 6%."}}}},
                     True, id="an empty body with its sections"),
        pytest.param(" \n", {"risk_factors": [{"title": "Supply chain", "description": "Supply constraints persisted."}]},
                     True, id="a blank body with a legacy risk list"),
        pytest.param("## Risks\n\nGenerating summary...", {}, True, id="the marker in its Risks section alone"),
    ],
)
def test_the_watchlist_and_the_dashboard_call_ready_what_the_filing_page_shows(
    client, user_id, overview, stored, ready
):
    # The watchlist insights (the watchlist card's chip, the dashboard's Your companies rows) and the dashboard feed (its
    # card's link) read the filing page's rule on the body the page is served (E221): Ready exactly when the page shows
    # a summary, else Unavailable ("placeholder") with a regeneration to offer. The feed's status is read on a detached
    # row, as test_force_regenerate_keeps_xbrl.py reads it: the rule needs only the row's own columns.
    from app.database import SessionLocal
    from app.models import Summary
    from app.services.dashboard_feed_service import _summary_status
    from app.services.summary_placeholders import is_summary_ready

    ticker = f"S{uuid.uuid4().hex[:5].upper()}"
    cid = _company(ticker)
    _watch(user_id, cid, T0)
    fid = _filing(cid, "10-K", datetime(2026, 3, 1, tzinfo=timezone.utc))
    sid = _summary(fid, overview, **stored)
    page = client.get(f"/api/summaries/filing/{fid}").json()
    assert is_summary_ready(page["business_overview"], (page["raw_summary"] or {}).get("writer_error")) is ready
    status = "ready" if ready else "placeholder"

    [row] = client.get("/api/watchlist/insights").json()
    snap = row["latest_filing"]
    assert (snap["summary_id"], snap["summary_status"], snap["needs_regeneration"]) == (sid, status, not ready)
    with SessionLocal() as db:
        stored_row = db.get(Summary, sid)
    assert _summary_status(stored_row, None) == {"summary_id": sid, "summary_status": status}


# A run last written longer ago than the progress poll's staleness window, which the poll marks a retryable error.
STALLED_AGE = 240
READY_BODY = "A real overview of the business."
PLACEHOLDER_BODY = "Generating summary... please wait"


@pytest.mark.parametrize(
    ("body", "stage", "age", "error", "status", "progress"),
    [
        pytest.param(None, None, 0, None, "missing", None, id="no run"),
        pytest.param(None, "fetching", 0, None, "generating:fetching", ("fetching", None), id="a fresh run's first stage"),
        pytest.param(None, "summarizing", 0, None, "generating:summarizing", ("summarizing", None), id="a fresh run"),
        # The progress poll would mark these a retryable error; the read-only surfaces say so without the write.
        pytest.param(None, "fetching", STALLED_AGE, None, "error", ("error", "stalled"), id="a stalled first stage"),
        pytest.param(None, "summarizing", STALLED_AGE, None, "error", ("error", "stalled"), id="a stalled run"),
        pytest.param(None, "error", 0, "Pipeline timeout", "error", ("error", "Pipeline timeout"), id="a failed run"),
        pytest.param(None, "error", STALLED_AGE, "Pipeline timeout", "error", ("error", "Pipeline timeout"),
                     id="an old failed run"),
        # A run that ended with no summary beside it: none is being written and none failed.
        pytest.param(None, "completed", 0, None, "missing", None, id="a completed run"),
        pytest.param(None, "completed", STALLED_AGE, None, "missing", None, id="an old completed run"),
        pytest.param(None, "partial", 0, None, "missing", None, id="a partial run"),
        pytest.param(None, "partial", STALLED_AGE, None, "missing", None, id="an old partial run"),
        # A stored summary decides first, whatever its progress row says; the row is sent beside it as stored.
        pytest.param(READY_BODY, "summarizing", STALLED_AGE, None, "ready", ("summarizing", None),
                     id="a ready summary beside a stalled run"),
        pytest.param(READY_BODY, "summarizing", 0, None, "ready", ("summarizing", None),
                     id="a ready summary beside a fresh run"),
        pytest.param(READY_BODY, "completed", 0, None, "ready", ("completed", None),
                     id="a ready summary beside a completed run"),
        pytest.param(PLACEHOLDER_BODY, "summarizing", STALLED_AGE, None, "placeholder", ("summarizing", None),
                     id="a placeholder beside a stalled run"),
        pytest.param(PLACEHOLDER_BODY, "summarizing", 0, None, "placeholder", ("summarizing", None),
                     id="a placeholder beside a fresh run"),
        pytest.param(PLACEHOLDER_BODY, "error", 0, "Pipeline timeout", "placeholder", ("error", "Pipeline timeout"),
                     id="a placeholder beside a failed run"),
    ],
)
def test_the_watchlist_and_the_feed_read_a_run_the_same_way(client, user_id, body, stage, age, error, status, progress):
    # A stale or ended run without a summary reached the watchlist card as `generating:*` ("A summary is being
    # written.", no action) and the feed's link as "Generating…" (E43). Both read the progress row through
    # progress_read_status: a fresh run is being written, a stalled one is the error the progress poll would mark,
    # and an ended one is a missing summary. Neither writes the row.
    from app.database import SessionLocal
    from app.models import SummaryGenerationProgress
    from app.services.summary_generation_service import STALE_PROGRESS_SECONDS, STALLED_ERROR

    assert STALLED_AGE > STALE_PROGRESS_SECONDS
    ticker = f"S{uuid.uuid4().hex[:5].upper()}"
    cid = _company(ticker)
    _watch(user_id, cid, T0)
    fid = _filing(cid, "10-Q", datetime(2026, 3, 1, tzinfo=timezone.utc))
    sid = _summary(fid, body) if body is not None else None
    if stage is not None:
        _progress(fid, stage, age_seconds=age, error=error)

    def stored_row():
        with SessionLocal() as db:
            row = db.get(SummaryGenerationProgress, fid)
            return None if row is None else (row.stage, row.error, row.started_at, row.updated_at)

    before = stored_row()
    [insight] = client.get("/api/watchlist/insights").json()
    feed = client.get("/api/dashboard/feed")
    assert feed.status_code == 200, feed.text
    [item] = feed.json()["items"]

    snap = insight["latest_filing"]
    assert (snap["summary_id"], snap["summary_status"]) == (sid, status)
    assert snap["needs_regeneration"] is not status.startswith(("generating:", "ready"))
    expected = None if progress is None else (progress[0], STALLED_ERROR if progress[1] == "stalled" else progress[1])
    assert (None if snap["progress"] is None else (snap["progress"]["stage"], snap["progress"]["error"])) == expected
    assert (item["filing_id"], item["summary_id"], item["summary_status"]) == (fid, sid, status)
    assert stored_row() == before


def test_the_insights_and_the_feed_read_progress_without_a_write_or_a_query_per_row(client, user_id, monkeypatch):
    # The read-only surfaces never mark a stalled run (only the progress poll does) and read every company's progress
    # in one batched query: their statements are SELECTs alone, as many for four stalled companies as for one.
    from sqlalchemy import event

    from app.database import engine
    from app.services import summary_generation_service

    def _no_mark(*_args, **_kwargs):
        raise AssertionError("a GET marked a stalled run")

    monkeypatch.setattr(summary_generation_service, "mark_stale_progress_as_error", _no_mark)

    def watch_stalled(count: int) -> None:
        for _ in range(count):
            cid = _company(f"Q{uuid.uuid4().hex[:5].upper()}")
            _watch(user_id, cid, T0)
            _progress(_filing(cid, "10-Q", datetime(2026, 3, 1, tzinfo=timezone.utc)), "summarizing",
                      age_seconds=STALLED_AGE)

    def statements(path: str) -> list[str]:
        seen: list[str] = []

        def spy(_conn, _cursor, statement, _parameters, _context, _executemany):
            seen.append(statement.lstrip().split(None, 1)[0].upper())

        event.listen(engine, "before_cursor_execute", spy)
        try:
            response = client.get(path)
        finally:
            event.remove(engine, "before_cursor_execute", spy)
        assert response.status_code == 200, response.text
        return seen

    paths = ("/api/watchlist/insights", "/api/dashboard/feed")
    watch_stalled(1)
    one = {path: statements(path) for path in paths}
    watch_stalled(3)
    four = {path: statements(path) for path in paths}
    for path in paths:
        assert set(one[path]) == {"SELECT"} and set(four[path]) == {"SELECT"}, (path, one[path], four[path])
        assert len(four[path]) == len(one[path]), (path, one[path], four[path])
