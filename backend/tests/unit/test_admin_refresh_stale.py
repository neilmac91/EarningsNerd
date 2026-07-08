"""Tests for POST /api/admin/summaries/refresh-stale (in-place, bookmark-preserving refresh).

Unlike reset-all (delete+regenerate, destroys bookmarks), refresh-stale drains the ONE orchestrator
with force_regenerate=True so each stale row is UPDATEd in place. The in-place UPDATE + keep-better
mechanics are pinned in test_background_generation_characterization.py; here we pin the endpoint:
admin gate, the staleness filter/count (dry-run = the staleness count), and that a real run calls
force_regenerate per candidate without disturbing the saved_summaries bookmark. Generation itself is
mocked (the drain is exercised by the characterization tests). Each test scopes by a UNIQUE
filing_type to isolate its rows in the shared module DB.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers.auth import get_current_user
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION


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


def _seed(filing_type, stamps, saved_indices=()):
    """Create one filing + Summary per (schema_version, prompt_version) tuple in `stamps`.

    Returns filing_ids, summary_ids, and the saved (bookmarked) summary ids.
    """
    from app.database import SessionLocal
    from app.models import Company, Filing, SavedSummary, Summary, User

    db = SessionLocal()
    try:
        if db.query(User).filter(User.id == 9101).first() is None:
            db.add(User(id=9101, email="stale-saver@example.com", hashed_password="x"))
            db.commit()
        tag = uuid.uuid4().hex[:10]
        company = Company(cik=f"cik-{tag}", ticker=f"S{tag[:6]}", name=f"Co {tag}")
        db.add(company)
        db.commit()
        db.refresh(company)

        filing_ids, summary_ids, saved_ids = [], [], []
        for i, (sv, pv) in enumerate(stamps):
            acc = f"{tag}-{i}"
            filing = Filing(
                company_id=company.id,
                accession_number=acc,
                filing_type=filing_type,
                filing_date=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                document_url=f"https://sec.gov/{acc}.htm",
                sec_url=f"https://sec.gov/{acc}/",
            )
            db.add(filing)
            db.commit()
            db.refresh(filing)
            summary = Summary(
                filing_id=filing.id,
                business_overview=f"stale summary {i}",
                schema_version=sv,
                prompt_version=pv,
            )
            db.add(summary)
            db.commit()
            db.refresh(summary)
            filing_ids.append(filing.id)
            summary_ids.append(summary.id)
            if i in saved_indices:
                db.add(SavedSummary(user_id=9101, summary_id=summary.id))
                db.commit()
                saved_ids.append(summary.id)
        return {"filing_ids": filing_ids, "summary_ids": summary_ids, "saved_ids": saved_ids}
    finally:
        db.close()


def test_non_admin_is_forbidden(client, as_non_admin):
    assert client.post("/api/admin/summaries/refresh-stale").status_code == 403


@pytest.mark.requires_db
def test_dry_run_counts_stale_and_regenerates_nothing(client, as_admin, monkeypatch):
    ft = f"STALE-{uuid.uuid4().hex[:6]}"
    # 2 stale (unstamped) + 1 current-stamped -> default filter counts only the 2 stale.
    _seed(ft, stamps=[(None, None), (None, None), (SUMMARY_SCHEMA_VERSION, SUMMARY_PROMPT_VERSION)])
    spy = AsyncMock()
    monkeypatch.setattr(
        "app.services.summary_generation_service.generate_summary_background", spy
    )
    resp = client.post(f"/api/admin/summaries/refresh-stale?filing_type={ft}")  # dry_run default
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert body["stale_total"] == 2
    assert body["regenerated_count"] == 0
    spy.assert_not_called()


@pytest.mark.requires_db
def test_current_version_rows_are_not_stale(client, as_admin):
    ft = f"CUR-{uuid.uuid4().hex[:6]}"
    _seed(ft, stamps=[(SUMMARY_SCHEMA_VERSION, SUMMARY_PROMPT_VERSION)] * 2)
    resp = client.post(f"/api/admin/summaries/refresh-stale?filing_type={ft}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stale_total"] == 0


@pytest.mark.requires_db
def test_schema_version_lt_bounds_the_filter(client, as_admin):
    ft = f"LT-{uuid.uuid4().hex[:6]}"
    # schema_version=1 rows are current under the default filter, but stale under schema_version_lt=2.
    _seed(ft, stamps=[(SUMMARY_SCHEMA_VERSION, SUMMARY_PROMPT_VERSION)] * 2)
    resp = client.post(
        f"/api/admin/summaries/refresh-stale?filing_type={ft}&schema_version_lt={SUMMARY_SCHEMA_VERSION + 1}"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stale_total"] == 2


@pytest.mark.requires_db
def test_limit_is_clamped_to_the_batch_ceiling(client, as_admin):
    from app.routers.admin import _REFRESH_STALE_MAX_BATCH

    ft = f"CLAMP-{uuid.uuid4().hex[:6]}"
    _seed(ft, stamps=[(None, None)] * 2)
    resp = client.post(f"/api/admin/summaries/refresh-stale?filing_type={ft}&limit=9999")
    assert resp.status_code == 200, resp.text
    assert resp.json()["batch_limit"] == _REFRESH_STALE_MAX_BATCH


@pytest.mark.requires_db
def test_real_run_forces_regenerate_preserves_bookmark_and_audits(client, as_admin, monkeypatch):
    ft = f"REAL-{uuid.uuid4().hex[:6]}"
    seed = _seed(ft, stamps=[(None, None)], saved_indices=(0,))
    stale_fid = seed["filing_ids"][0]
    saved_id = seed["saved_ids"][0]

    spy = AsyncMock()
    monkeypatch.setattr(
        "app.services.summary_generation_service.generate_summary_background", spy
    )
    resp = client.post(f"/api/admin/summaries/refresh-stale?filing_type={ft}&dry_run=false")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["regenerated_count"] == 1
    # Each candidate is drained with force_regenerate=True (in-place UPDATE, bookmark-safe).
    spy.assert_awaited_once_with(stale_fid, None, force_regenerate=True)

    from app.database import SessionLocal
    from app.models import SavedSummary
    from app.models.audit_log import AuditLog

    db = SessionLocal()
    try:
        # The bookmark is untouched (no delete+insert), unlike reset-all.
        assert db.query(SavedSummary).filter(SavedSummary.summary_id == saved_id).count() == 1
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "summaries_refresh_stale")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None and audit.entity_type == "summaries"
    finally:
        db.close()
