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


def _fact(db, company_id, *, concept, value, period_end, fy, latest=True, accession=None, unit="USD"):
    from app.models import FinancialFact

    db.add(
        FinancialFact(
            company_id=company_id,
            concept=concept,
            unit=unit,
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

    def test_ranks_on_annual_not_later_quarterly(self):
        """A filer's later 10-Q value must not be ranked against peers' 10-K annuals."""
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        a = _company(db, sic=sic)
        # Annual FY2023 — the value peers should rank on ...
        _fact(db, a.id, concept="revenue", value=100.0, period_end=date(2023, 12, 31), fy=2023)
        # ... plus a *later* 10-Q with a smaller, quarterly figure (fiscal_period NULL). Both
        # rows are is_latest=True (different period_ends), so without the annual-only filter the
        # period_end-desc pick would surface the 25.0 quarterly value.
        db.add(
            FinancialFact(
                company_id=a.id, concept="revenue", unit="USD",
                period_end=date(2024, 3, 31), fiscal_year=2024, fiscal_period=None,
                value=25.0, form="10-Q", accession=uuid.uuid4().hex,
                source="edgar_xbrl", is_latest=True,
            )
        )
        db.commit()

        result = svc.get_peers(db, a.ticker, "revenue")
        assert result["subject"]["value"] == 100.0  # annual, not the 25.0 quarterly
        assert result["subject"]["fiscal_year"] == 2023
        db.close()

    def test_tied_values_share_rank_and_percentile(self):
        """Equal values get the same rank + percentile (competition ranking), not adjacent
        ranks split by arbitrary order."""
        from app.database import SessionLocal

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        top = _company(db, sic=sic)
        tie_a = _company(db, sic=sic)
        tie_b = _company(db, sic=sic)
        _fact(db, top.id, concept="revenue", value=300.0, period_end=date(2023, 12, 31), fy=2023)
        _fact(db, tie_a.id, concept="revenue", value=200.0, period_end=date(2023, 12, 31), fy=2023)
        _fact(db, tie_b.id, concept="revenue", value=200.0, period_end=date(2023, 12, 31), fy=2023)

        result = svc.get_peers(db, top.ticker, "revenue")
        by_ticker = {p["ticker"]: p for p in result["peers"]}
        assert by_ticker[top.ticker]["rank"] == 1
        assert by_ticker[tie_a.ticker]["rank"] == 2
        assert by_ticker[tie_b.ticker]["rank"] == 2  # shares rank 2, not pushed to 3
        assert by_ticker[tie_a.ticker]["percentile"] == by_ticker[tie_b.ticker]["percentile"]
        db.close()

    def test_excludes_foreign_currency_peer_from_usd_ranking(self):
        """A foreign private issuer that reports in CNY must NOT be ranked against USD filers
        in the same SIC (a CNY revenue is ~7x a USD one — apples-to-oranges)."""
        from app.database import SessionLocal

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        usd_subject = _company(db, sic=sic)
        usd_peer = _company(db, sic=sic)
        cny_fpi = _company(db, sic=sic)
        _fact(db, usd_subject.id, concept="revenue", value=100.0, period_end=date(2023, 12, 31), fy=2023, unit="USD")
        _fact(db, usd_peer.id, concept="revenue", value=200.0, period_end=date(2023, 12, 31), fy=2023, unit="USD")
        # Huge CNY figure in the same SIC — if currency were ignored it would rank #1.
        _fact(db, cny_fpi.id, concept="revenue", value=900000.0, period_end=date(2023, 12, 31), fy=2023, unit="CNY")

        result = svc.get_peers(db, usd_subject.ticker, "revenue")
        tickers = [p["ticker"] for p in result["peers"]]
        assert cny_fpi.ticker not in tickers  # excluded by the currency guard
        assert usd_peer.ticker in tickers
        assert result["peer_count"] == 2
        assert result["unit"] == "USD"
        db.close()

    def test_foreign_subject_ranks_in_its_own_currency(self):
        """A CNY subject ranks only against other CNY filers; the response unit is the
        subject's currency, and USD filers in the same SIC are excluded."""
        from app.database import SessionLocal

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:6]}"
        cny_subject = _company(db, sic=sic)
        cny_peer = _company(db, sic=sic)
        usd_peer = _company(db, sic=sic)
        _fact(db, cny_subject.id, concept="revenue", value=500000.0, period_end=date(2023, 12, 31), fy=2023, unit="CNY")
        _fact(db, cny_peer.id, concept="revenue", value=800000.0, period_end=date(2023, 12, 31), fy=2023, unit="CNY")
        _fact(db, usd_peer.id, concept="revenue", value=100.0, period_end=date(2023, 12, 31), fy=2023, unit="USD")

        result = svc.get_peers(db, cny_subject.ticker, "revenue")
        tickers = [p["ticker"] for p in result["peers"]]
        assert result["unit"] == "CNY"
        assert set(tickers) == {cny_subject.ticker, cny_peer.ticker}
        assert usd_peer.ticker not in tickers
        # Subject ranks #2 of the two CNY filers (800k > 500k).
        assert result["subject"]["rank"] == 2
        db.close()

    def test_unknown_ticker_returns_none(self):
        from app.database import SessionLocal

        db = SessionLocal()
        assert svc.get_peers(db, "NOPE" + uuid.uuid4().hex[:6], "revenue") is None
        db.close()
