"""Tests for the in-app filing viewer content endpoint (P7).

`GET /api/filings/{id}/content` serves the cached full-text markdown so the frontend can render the
filing on-page and highlight cited passages. DB-touching → marked ``requires_db``.
"""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _seed_filing(markdown):
    """Insert a Company + Filing, with a content cache only when ``markdown`` is not None."""
    from app.database import SessionLocal
    from app.models import Company, Filing, FilingContentCache

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4]}", name="Test Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    filing = Filing(
        company_id=company.id,
        accession_number=f"acc-{suffix}",
        filing_type="10-K",
        filing_date=datetime.datetime(2026, 1, 1),
        document_url="https://www.sec.gov/Archives/edgar/data/1/x/doc.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/1/x/",
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)
    if markdown is not None:
        db.add(FilingContentCache(filing_id=filing.id, markdown_content=markdown))
        db.commit()
    fid, cid = filing.id, company.id
    db.close()
    return fid, cid


def _cleanup(fid, cid):
    from app.database import SessionLocal
    from app.models import Company, Filing, FilingContentCache

    db = SessionLocal()
    db.query(FilingContentCache).filter(FilingContentCache.filing_id == fid).delete()
    db.query(Filing).filter(Filing.id == fid).delete()
    db.query(Company).filter(Company.id == cid).delete()
    db.commit()
    db.close()


@pytest.mark.requires_db
def test_filing_content_returns_markdown(client):
    fid, cid = _seed_filing("# Item 7 — MD&A\n\nRevenue increased to $391.0B this year.")
    try:
        resp = client.get(f"/api/filings/{fid}/content")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filing_id"] == fid
        assert data["has_content"] is True
        assert "Revenue increased to $391.0B" in data["markdown_content"]
    finally:
        _cleanup(fid, cid)


@pytest.mark.requires_db
def test_filing_content_no_cache_returns_empty(client):
    fid, cid = _seed_filing(None)  # filing exists, but no cached markdown
    try:
        resp = client.get(f"/api/filings/{fid}/content")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_content"] is False
        assert data["markdown_content"] is None
    finally:
        _cleanup(fid, cid)


@pytest.mark.requires_db
def test_filing_content_404_for_missing_filing(client):
    resp = client.get("/api/filings/99999999/content")
    assert resp.status_code == 404
