"""Sitemap correctness (SEO quick-wins).

The sitemap is a crawler-facing contract:
- static pages carry NO lastmod (a fabricated "today" teaches Google to ignore the field);
- company pages appear only when the company has filings, with lastmod = newest filing date;
- filing pages appear only when a real summary exists (the frontend noindexes summary-less
  filing pages, and a sitemap must never advertise noindex'd URLs);
- the document is cached in-process so crawlers can't turn it into a per-request table scan.

Runs against a real in-memory SQLite DB so the actual queries execute.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from app.database import Base, get_db
import app.models  # noqa: F401 — register models on Base.metadata
from app.models import Company, Filing, Summary
from app.routers import sitemap as sitemap_mod


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_engine):
    TestingSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    sitemap_mod.reset_sitemap_cache()
    main.app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(main.app), TestingSession
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        sitemap_mod.reset_sitemap_cache()


def _seed_company(session, ticker, cik):
    company = Company(cik=cik, ticker=ticker, name=f"{ticker} Inc.")
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def _seed_filing(session, company, accession, year=2025):
    sec_url = f"https://www.sec.gov/Archives/edgar/data/1/{accession}/"
    filing = Filing(
        company_id=company.id,
        accession_number=accession,
        filing_type="10-K",
        filing_date=datetime(year, 2, 19, tzinfo=timezone.utc),
        document_url=sec_url + "primary.htm",
        sec_url=sec_url,
    )
    session.add(filing)
    session.commit()
    session.refresh(filing)
    return filing


def _seed_summary(session, filing, business_overview="A real generated summary."):
    summary = Summary(filing_id=filing.id, business_overview=business_overview)
    session.add(summary)
    session.commit()
    return summary


def test_static_pages_present_without_lastmod(client):
    test_client, _ = client
    xml = test_client.get("/sitemap.xml").text
    for path in ("/pricing", "/contact", "/privacy", "/terms", "/security"):
        assert f"<loc>https://www.earningsnerd.io{path}</loc>" in xml
    # Static entries emit no fabricated lastmod: with an empty DB, the document has none at all.
    assert "<lastmod>" not in xml


def test_company_without_filings_is_excluded(client):
    test_client, TestingSession = client
    with TestingSession() as session:
        _seed_company(session, "EMPTY", "0000000001")
    xml = test_client.get("/sitemap.xml").text
    assert "/company/EMPTY" not in xml


def test_company_with_filing_uses_newest_filing_date_as_lastmod(client):
    test_client, TestingSession = client
    with TestingSession() as session:
        company = _seed_company(session, "ACME", "0000000002")
        _seed_filing(session, company, "acc-1", year=2024)
        _seed_filing(session, company, "acc-2", year=2026)
    xml = test_client.get("/sitemap.xml").text
    assert "<loc>https://www.earningsnerd.io/company/ACME</loc>" in xml
    assert "<lastmod>2026-02-19</lastmod>" in xml
    assert "<lastmod>2024-02-19</lastmod>" not in xml  # filing without summary is excluded below


def test_only_summarized_filings_are_listed(client):
    test_client, TestingSession = client
    with TestingSession() as session:
        company = _seed_company(session, "ACME", "0000000002")
        bare = _seed_filing(session, company, "acc-bare", year=2024)
        empty = _seed_filing(session, company, "acc-empty", year=2025)
        _seed_summary(session, empty, business_overview="")
        summarized = _seed_filing(session, company, "acc-summ", year=2026)
        _seed_summary(session, summarized)
        bare_id, empty_id, summarized_id = bare.id, empty.id, summarized.id
    xml = test_client.get("/sitemap.xml").text
    assert f"<loc>https://www.earningsnerd.io/filing/{summarized_id}</loc>" in xml
    assert f"/filing/{bare_id}</loc>" not in xml
    assert f"/filing/{empty_id}</loc>" not in xml


def test_sitemap_is_served_from_cache_within_ttl(client):
    test_client, TestingSession = client
    first = test_client.get("/sitemap.xml").text
    # New content arriving does NOT appear until the TTL lapses: the second request must be
    # served from the in-process cache, not a fresh table scan.
    with TestingSession() as session:
        company = _seed_company(session, "LATE", "0000000003")
        filing = _seed_filing(session, company, "acc-late", year=2026)
        _seed_summary(session, filing)
    second = test_client.get("/sitemap.xml").text
    assert second == first
    assert "/company/LATE" not in second

    sitemap_mod.reset_sitemap_cache()
    third = test_client.get("/sitemap.xml").text
    assert "/company/LATE" in third
