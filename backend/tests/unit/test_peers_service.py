"""Unit tests for the P3 cross-company peer comparison service."""

import uuid
from datetime import date

import pytest

from app.services import peers_service as svc


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _company(db, *, sic):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=suffix, ticker=("T" + suffix[:5]).upper(), name=f"Co {suffix}", sic=sic)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _fact(db, company_id, *, concept, value, period_end, fy, latest=True, accession=None):
    from app.models import FinancialFact

    db.add(
        FinancialFact(
            company_id=company_id,
            concept=concept,
            unit="USD",
            period_end=period_end,
            fiscal_year=fy,
            fiscal_period="FY",
            value=value,
            form="10-K",
            accession=accession or uuid.uuid4().hex,
            source="edgar_xbrl",
            is_latest=latest,
        )
    )
    db.commit()


@pytest.mark.requires_db
class TestGetPeers:
    def test_ranks_same_sic_peers_with_percentile(self):
        from app.database import SessionLocal

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        a = _company(db, sic=sic)  # subject
        b = _company(db, sic=sic)
        c = _company(db, sic=sic)
        _fact(db, a.id, concept="revenue", value=100.0, period_end=date(2023, 12, 31), fy=2023)
        _fact(db, b.id, concept="revenue", value=300.0, period_end=date(2023, 12, 31), fy=2023)
        _fact(db, c.id, concept="revenue", value=200.0, period_end=date(2023, 12, 31), fy=2023)

        result = svc.get_peers(db, a.ticker.lower(), "revenue")

        assert result is not None
        assert result["peer_count"] == 3
        assert result["unit"] == "USD"
        # Ranked by value descending: b(300) > c(200) > a(100)
        assert [p["ticker"] for p in result["peers"]] == [b.ticker, c.ticker, a.ticker]
        subject = result["subject"]
        assert subject["is_subject"] is True
        assert subject["ticker"] == a.ticker
        assert subject["rank"] == 3
        assert subject["value"] == 100.0
        assert subject["percentile"] == 0.0  # lowest of three
        # Highest is 100th percentile
        assert result["peers"][0]["percentile"] == 100.0
        db.close()

    def test_uses_most_recent_value_per_company(self):
        from app.database import SessionLocal

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        a = _company(db, sic=sic)
        _fact(db, a.id, concept="revenue", value=50.0, period_end=date(2021, 12, 31), fy=2021)
        _fact(db, a.id, concept="revenue", value=80.0, period_end=date(2023, 12, 31), fy=2023)

        result = svc.get_peers(db, a.ticker, "revenue")
        assert result["subject"]["value"] == 80.0  # 2023, not 2021
        assert result["subject"]["fiscal_year"] == 2023
        db.close()

    def test_excludes_other_sic_companies(self):
        from app.database import SessionLocal

        db = SessionLocal()
        sic_a = f"SIC{uuid.uuid4().hex[:6]}"
        sic_b = f"SIC{uuid.uuid4().hex[:6]}"
        a = _company(db, sic=sic_a)
        other = _company(db, sic=sic_b)
        _fact(db, a.id, concept="revenue", value=100.0, period_end=date(2023, 12, 31), fy=2023)
        _fact(db, other.id, concept="revenue", value=999.0, period_end=date(2023, 12, 31), fy=2023)

        result = svc.get_peers(db, a.ticker, "revenue")
        tickers = [p["ticker"] for p in result["peers"]]
        assert a.ticker in tickers
        assert other.ticker not in tickers
        assert result["peer_count"] == 1
        db.close()

    def test_subject_without_fact_is_surfaced(self):
        from app.database import SessionLocal

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        a = _company(db, sic=sic)  # no facts for the requested concept
        result = svc.get_peers(db, a.ticker, "net_margin")
        assert result["subject"]["is_subject"] is True
        assert result["subject"]["value"] is None
        assert result["subject"]["rank"] is None
        assert result["peers"] == []
        db.close()

    def test_unknown_ticker_returns_none(self):
        from app.database import SessionLocal

        db = SessionLocal()
        assert svc.get_peers(db, "NOPE" + uuid.uuid4().hex[:6], "revenue") is None
        db.close()
