"""Tests for POST /api/admin/summaries/reset-all (FK-safe bulk summary reset).

Mirrors the admin-feedback harness: TestClient against the app's test DB, overriding only
get_current_user. Each test scopes its reset by a UNIQUE filing_type so it only touches its own
seeded rows (the test DB is shared across the module).
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers.auth import get_current_user


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def as_admin():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, email="admin@example.com", is_admin=True
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def as_non_admin():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=2, email="user@example.com", is_admin=False
    )
    yield
    app.dependency_overrides.clear()


def _seed(filing_type, n=2, saved_indices=(), with_xbrl=False):
    """Create n filings of `filing_type`, each with a Summary + progress row.

    Save the summaries at `saved_indices` (via a saved_summaries bookmark). Returns id lists.
    """
    from app.database import SessionLocal
    from app.models import (
        Company, Filing, SavedSummary, Summary, SummaryGenerationProgress, User,
    )

    db = SessionLocal()
    try:
        if db.query(User).filter(User.id == 9001).first() is None:
            db.add(User(id=9001, email="saver@example.com", hashed_password="x"))
            db.commit()

        tag = uuid.uuid4().hex[:10]
        company = Company(cik=f"cik-{tag}", ticker=f"T{tag[:6]}", name=f"Co {tag}")
        db.add(company)
        db.commit()
        db.refresh(company)

        filing_ids, summary_ids, saved_summary_ids = [], [], []
        for i in range(n):
            acc = f"{tag}-{i}"
            filing = Filing(
                company_id=company.id,
                accession_number=acc,
                filing_type=filing_type,
                filing_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                document_url=f"https://sec.gov/{acc}.htm",
                sec_url=f"https://sec.gov/{acc}/",
                xbrl_data={"revenue": 1} if with_xbrl else None,
            )
            db.add(filing)
            db.commit()
            db.refresh(filing)
            summary = Summary(filing_id=filing.id, business_overview=f"old summary {i}")
            db.add(summary)
            db.add(SummaryGenerationProgress(filing_id=filing.id, stage="complete"))
            db.commit()
            db.refresh(summary)
            filing_ids.append(filing.id)
            summary_ids.append(summary.id)
            if i in saved_indices:
                db.add(SavedSummary(user_id=9001, summary_id=summary.id))
                db.commit()
                saved_summary_ids.append(summary.id)
        return {"filing_ids": filing_ids, "summary_ids": summary_ids,
                "saved_summary_ids": saved_summary_ids}
    finally:
        db.close()


def _summary_exists(summary_id):
    from app.database import SessionLocal
    from app.models import Summary

    db = SessionLocal()
    try:
        return db.query(Summary).filter(Summary.id == summary_id).first() is not None
    finally:
        db.close()


def test_non_admin_is_forbidden(client, as_non_admin):
    assert client.post("/api/admin/summaries/reset-all").status_code == 403


@pytest.mark.requires_db
def test_dry_run_reports_but_deletes_nothing(client, as_admin):
    ft = f"DRY-{uuid.uuid4().hex[:6]}"
    seed = _seed(ft, n=2)
    resp = client.post(f"/api/admin/summaries/reset-all?filing_type={ft}")  # dry_run defaults True
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert body["total_matched"] == 2
    assert body["deleted_count"] == 2
    assert all(_summary_exists(sid) for sid in seed["summary_ids"])  # nothing deleted


@pytest.mark.requires_db
def test_real_run_deletes_unsaved_keeps_saved_and_xbrl(client, as_admin):
    ft = f"REAL-{uuid.uuid4().hex[:6]}"
    seed = _seed(ft, n=3, saved_indices=(0,), with_xbrl=True)
    resp = client.post(f"/api/admin/summaries/reset-all?filing_type={ft}&dry_run=false")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted_count"] == 2          # the 2 unsaved
    assert body["skipped_saved_count"] == 1    # the 1 saved is FK-safe skipped

    saved_id = seed["saved_summary_ids"][0]
    assert _summary_exists(saved_id) is True
    unsaved = [sid for sid in seed["summary_ids"] if sid != saved_id]
    assert all(_summary_exists(sid) is False for sid in unsaved)

    # Source data (XBRL) is retained on every filing — only summaries/progress are cleared.
    from app.database import SessionLocal
    from app.models import Filing

    db = SessionLocal()
    try:
        for fid in seed["filing_ids"]:
            assert db.query(Filing).filter(Filing.id == fid).first().xbrl_data == {"revenue": 1}
    finally:
        db.close()


@pytest.mark.requires_db
def test_include_saved_deletes_bookmark_and_summary(client, as_admin):
    ft = f"INCL-{uuid.uuid4().hex[:6]}"
    seed = _seed(ft, n=2, saved_indices=(0,))
    resp = client.post(
        f"/api/admin/summaries/reset-all?filing_type={ft}&dry_run=false&include_saved=true"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted_count"] == 2
    assert body["skipped_saved_count"] == 0
    assert all(_summary_exists(sid) is False for sid in seed["summary_ids"])

    from app.database import SessionLocal
    from app.models import SavedSummary

    db = SessionLocal()
    try:
        remaining = db.query(SavedSummary).filter(
            SavedSummary.summary_id.in_(seed["summary_ids"])
        ).count()
        assert remaining == 0
    finally:
        db.close()


@pytest.mark.requires_db
def test_writes_audit_log(client, as_admin):
    ft = f"AUD-{uuid.uuid4().hex[:6]}"
    _seed(ft, n=1)
    resp = client.post(f"/api/admin/summaries/reset-all?filing_type={ft}&dry_run=false")
    assert resp.status_code == 200, resp.text

    from app.database import SessionLocal
    from app.models.audit_log import AuditLog

    db = SessionLocal()
    try:
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "summaries_bulk_reset")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.entity_type == "summaries"
    finally:
        db.close()
