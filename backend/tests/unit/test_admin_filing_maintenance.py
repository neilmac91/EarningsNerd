"""Tests for the admin per-filing maintenance endpoints and the stale-XBRL audit / bulk reset.

Covers DELETE /api/admin/filing/{id}/summary, /xbrl and /reset, GET /api/admin/filings/audit-xbrl
and POST /api/admin/filings/bulk-reset-stale: the admin gate, the 404 for an unknown filing, what
each route deletes or keeps, and the exact response shapes. The audit and bulk reset scan every
filing with XBRL data, so each test runs on its own in-memory SQLite database (``get_db`` is
overridden) and never touches rows that other modules seed in the shared test DB.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db
from app.models import Company, Filing, FilingContentCache, Summary, SummaryGenerationProgress
from app.routers.auth import get_current_user

ADMIN = SimpleNamespace(id=1, email="admin@example.com", is_admin=True)
NON_ADMIN = SimpleNamespace(id=2, email="user@example.com", is_admin=False)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


def _client(session_factory, user):
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def admin_client(session_factory):
    with _client(session_factory, ADMIN) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def non_admin_client(session_factory):
    with _client(session_factory, NON_ADMIN) as c:
        yield c
    app.dependency_overrides.clear()


def _xbrl(*periods):
    return {"revenue": [{"period": p, "value": 1} for p in periods]}


def _seed(session_factory, *, period_end_year=2025, xbrl=None, summary=True, progress=True, cache=True):
    """One filing (with the requested satellites) and return its id."""
    with session_factory() as db:
        company = db.query(Company).first()
        if company is None:
            company = Company(cik="320193", ticker="MAINT", name="Maintenance Co")
            db.add(company)
            db.flush()
        n = db.query(Filing).count()
        fields = {}
        if xbrl is not None:
            fields["xbrl_data"] = xbrl
        filing = Filing(
            company_id=company.id,
            accession_number=f"maint-{n}",
            filing_type="10-K",
            filing_date=datetime(period_end_year + 1, 2, 1, tzinfo=timezone.utc),
            period_end_date=datetime(period_end_year, 12, 31, tzinfo=timezone.utc),
            document_url=f"https://sec.example/maint-{n}.htm",
            sec_url=f"https://sec.example/maint-{n}/",
            **fields,
        )
        db.add(filing)
        db.flush()
        if summary:
            db.add(Summary(filing_id=filing.id, business_overview="old summary"))
        if progress:
            db.add(SummaryGenerationProgress(filing_id=filing.id, stage="complete"))
        if cache:
            db.add(FilingContentCache(filing_id=filing.id, critical_excerpt="excerpt"))
        db.commit()
        return filing.id


def _state(session_factory, filing_id):
    with session_factory() as db:
        filing = db.query(Filing).filter(Filing.id == filing_id).first()
        return {
            "xbrl_data": filing.xbrl_data,
            "summary": db.query(Summary).filter(Summary.filing_id == filing_id).count(),
            "progress": db.query(SummaryGenerationProgress).filter(
                SummaryGenerationProgress.filing_id == filing_id
            ).count(),
            "cache": db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).count(),
        }


ROUTES = [
    ("delete", "/api/admin/filing/1/summary"),
    ("delete", "/api/admin/filing/1/xbrl"),
    ("delete", "/api/admin/filing/1/reset"),
    ("get", "/api/admin/filings/audit-xbrl"),
    ("post", "/api/admin/filings/bulk-reset-stale"),
]


@pytest.mark.parametrize("method,path", ROUTES)
def test_non_admin_is_forbidden(non_admin_client, method, path):
    resp = getattr(non_admin_client, method)(path)
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Admin access required"}


@pytest.mark.parametrize("suffix", ["summary", "xbrl", "reset"])
def test_unknown_filing_is_404(admin_client, suffix):
    resp = admin_client.delete(f"/api/admin/filing/99999999/{suffix}")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Filing not found"}


def test_delete_summary_drops_summary_and_progress_only(admin_client, session_factory):
    fid = _seed(session_factory, xbrl=_xbrl("2025-12-31"))
    resp = admin_client.delete(f"/api/admin/filing/{fid}/summary")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "message": f"Summary deleted for filing {fid}",
        "filing_id": fid,
        "summary_deleted": True,
    }
    assert _state(session_factory, fid) == {
        "xbrl_data": _xbrl("2025-12-31"), "summary": 0, "progress": 0, "cache": 1,
    }

    again = admin_client.delete(f"/api/admin/filing/{fid}/summary")
    assert again.status_code == 200, again.text
    assert again.json()["summary_deleted"] is False


def test_clear_xbrl_reports_whether_there_was_any(admin_client, session_factory):
    fid = _seed(session_factory, xbrl=_xbrl("2025-12-31"))
    resp = admin_client.delete(f"/api/admin/filing/{fid}/xbrl")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "message": f"XBRL data cleared for filing {fid}",
        "filing_id": fid,
        "had_xbrl_data": True,
    }
    assert _state(session_factory, fid) == {"xbrl_data": None, "summary": 1, "progress": 1, "cache": 1}

    again = admin_client.delete(f"/api/admin/filing/{fid}/xbrl")
    assert again.status_code == 200, again.text
    assert again.json()["had_xbrl_data"] is False


def test_reset_deletes_everything_and_reports_each_part(admin_client, session_factory):
    fid = _seed(session_factory, xbrl=_xbrl("2025-12-31"))
    resp = admin_client.delete(f"/api/admin/filing/{fid}/reset")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "message": f"Filing {fid} has been reset",
        "filing_id": fid,
        "deleted": {"summary": True, "xbrl_data": True, "content_cache": True, "progress": True},
    }
    assert list(body["deleted"]) == ["summary", "xbrl_data", "content_cache", "progress"]
    assert _state(session_factory, fid) == {"xbrl_data": None, "summary": 0, "progress": 0, "cache": 0}

    again = admin_client.delete(f"/api/admin/filing/{fid}/reset")
    assert again.status_code == 200, again.text
    assert again.json()["deleted"] == {
        "summary": False, "xbrl_data": False, "content_cache": False, "progress": False,
    }


def _seed_audit_corpus(session_factory):
    stale = _seed(session_factory, period_end_year=2025, xbrl=_xbrl("2020-12-31", "2019-12-31"))
    fresh = _seed(session_factory, period_end_year=2025, xbrl=_xbrl("2025-12-31", "2024-12-31"))
    no_xbrl = _seed(session_factory, period_end_year=2025)
    return stale, fresh, no_xbrl


def test_audit_flags_only_the_stale_filing(admin_client, session_factory):
    stale, _fresh, _no_xbrl = _seed_audit_corpus(session_factory)
    resp = admin_client.get("/api/admin/filings/audit-xbrl")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert list(body) == ["total_filings_with_xbrl", "stale_filings_count", "year_threshold", "stale_filings"]
    assert body["total_filings_with_xbrl"] == 2
    assert body["stale_filings_count"] == 1
    assert body["year_threshold"] == 2
    item = body["stale_filings"][0]
    assert list(item) == [
        "filing_id", "company_id", "filing_type", "filing_date", "period_end_date",
        "expected_year", "xbrl_years", "max_xbrl_year", "year_difference",
    ]
    assert item["filing_id"] == stale
    assert item["filing_type"] == "10-K"
    assert item["expected_year"] == 2025
    assert item["xbrl_years"] == [2020, 2019]
    assert item["max_xbrl_year"] == 2020
    assert item["year_difference"] == 5
    assert item["filing_date"].startswith("2026-02-01")
    assert item["period_end_date"].startswith("2025-12-31")

    wide = admin_client.get("/api/admin/filings/audit-xbrl?year_threshold=5")
    assert wide.json()["stale_filings_count"] == 0 and wide.json()["year_threshold"] == 5


def test_bulk_reset_dry_run_changes_nothing(admin_client, session_factory):
    stale, fresh, _no_xbrl = _seed_audit_corpus(session_factory)
    before = {fid: _state(session_factory, fid) for fid in (stale, fresh)}
    resp = admin_client.post("/api/admin/filings/bulk-reset-stale")  # dry_run defaults True
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "dry_run": True,
        "year_threshold": 2,
        "affected_count": 1,
        "affected_filings": [
            {"filing_id": stale, "expected_year": 2025, "max_xbrl_year": 2020, "year_difference": 5}
        ],
        "message": "Would reset 1 filings with stale XBRL data",
    }
    assert {fid: _state(session_factory, fid) for fid in (stale, fresh)} == before


def test_bulk_reset_real_run_resets_only_stale_filings(admin_client, session_factory):
    stale, fresh, _no_xbrl = _seed_audit_corpus(session_factory)
    resp = admin_client.post("/api/admin/filings/bulk-reset-stale?dry_run=false")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "dry_run": False,
        "year_threshold": 2,
        "affected_count": 1,
        "affected_filings": [
            {"filing_id": stale, "expected_year": 2025, "max_xbrl_year": 2020, "year_difference": 5}
        ],
        "message": "Reset 1 filings with stale XBRL data",
    }
    # The stale filing loses its XBRL data, summary and progress; its content cache is kept.
    assert _state(session_factory, stale) == {"xbrl_data": None, "summary": 0, "progress": 0, "cache": 1}
    assert _state(session_factory, fresh) == {
        "xbrl_data": _xbrl("2025-12-31", "2024-12-31"), "summary": 1, "progress": 1, "cache": 1,
    }
    assert admin_client.get("/api/admin/filings/audit-xbrl").json()["stale_filings_count"] == 0
