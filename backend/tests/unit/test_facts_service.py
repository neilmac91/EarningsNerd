"""Unit tests for the P3 financial-facts normalizer + writer."""

import uuid
from datetime import date

import pytest

from app.services import facts_service as svc


class TestNormalize:
    def test_units_periods_and_fiscal_year(self):
        standardized = {
            "revenue": {"current": {"period": "2024-09-28", "value": 391035000000.0}},
            "earnings_per_share": {"current": {"period": "2024-09-28", "value": 6.13}},
            "net_margin": {"current": {"period": "2024-09-28", "value": 24.3}},
        }
        facts = svc.normalize_standardized_to_facts(1, 10, "0000320193-24-000123", "10-K", standardized)
        by = {f["concept"]: f for f in facts}
        assert by["revenue"]["unit"] == "USD"
        assert by["earnings_per_share"]["unit"] == "USD/shares"
        assert by["net_margin"]["unit"] == "pure"
        assert by["revenue"]["period_end"] == date(2024, 9, 28)
        assert by["revenue"]["fiscal_year"] == 2024
        assert by["revenue"]["fiscal_period"] == "FY"
        assert by["revenue"]["accession"] == "0000320193-24-000123"
        assert by["revenue"]["value"] == 391035000000.0
        assert by["revenue"]["source"] == "edgar_xbrl"

    def test_10q_has_no_fiscal_period(self):
        facts = svc.normalize_standardized_to_facts(
            1, 10, "acc", "10-Q", {"revenue": {"current": {"period": "2024-03-31", "value": 90.0}}}
        )
        assert facts[0]["fiscal_period"] is None

    def test_skips_malformed_entries(self):
        standardized = {
            "no_current": {"prior": {"period": "2023-09-30", "value": 1.0}},
            "no_value": {"current": {"period": "2024-09-28"}},
            "non_numeric": {"current": {"period": "2024-09-28", "value": "lots"}},
            "boolean": {"current": {"period": "2024-09-28", "value": True}},  # bool excluded
            "bad_date": {"current": {"period": "not-a-date", "value": 5.0}},
            "good": {"current": {"period": "2024-09-28", "value": 5.0}},
        }
        facts = svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", standardized)
        assert [f["concept"] for f in facts] == ["good"]

    def test_unmapped_concept_defaults_to_usd(self):
        facts = svc.normalize_standardized_to_facts(
            1, 10, "acc", "10-K", {"some_future_metric": {"current": {"period": "2024-09-28", "value": 1.0}}}
        )
        assert facts[0]["unit"] == "USD"

    def test_empty_or_malformed_inputs(self):
        good = {"revenue": {"current": {"period": "2024-09-28", "value": 1.0}}}
        assert svc.normalize_standardized_to_facts(1, 10, None, "10-K", good) == []  # no accession
        assert svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", None) == []
        assert svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", "nope") == []


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _new_company(db):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=suffix, ticker=("T" + suffix[:4]).upper(), name=f"Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company.id


@pytest.mark.requires_db
class TestUpsert:
    def test_insert_then_idempotent(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        facts = svc.normalize_standardized_to_facts(
            cid,
            None,
            "ACC1",
            "10-K",
            {
                "revenue": {"current": {"period": "2024-09-28", "value": 100.0}},
                "net_income": {"current": {"period": "2024-09-28", "value": 20.0}},
            },
        )
        assert svc.upsert_facts(db, facts) == {"inserted": 2, "skipped": 0}

        rows = db.query(FinancialFact).filter_by(company_id=cid).all()
        assert len(rows) == 2
        assert all(r.is_latest for r in rows)

        # Re-upserting the identical facts is a no-op (idempotent on the identity key).
        assert svc.upsert_facts(db, facts) == {"inserted": 0, "skipped": 2}
        assert db.query(FinancialFact).filter_by(company_id=cid).count() == 2
        db.close()

    def test_restatement_flips_is_latest(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        base = {
            "company_id": cid,
            "filing_id": None,
            "concept": "revenue",
            "unit": "USD",
            "period_end": date(2024, 9, 28),
            "fiscal_year": 2024,
            "fiscal_period": "FY",
            "form": "10-K",
            "source": "edgar_xbrl",
        }
        svc.upsert_facts(db, [{**base, "value": 100.0, "accession": "ACC1"}])
        # A restatement: same period under a new accession with a corrected value.
        svc.upsert_facts(db, [{**base, "value": 110.0, "accession": "ACC2", "form": "10-K/A"}])

        rows = {
            r.accession: r
            for r in db.query(FinancialFact).filter_by(company_id=cid, concept="revenue").all()
        }
        assert len(rows) == 2  # original + restatement coexist (audit trail preserved)
        assert not rows["ACC1"].is_latest  # original demoted
        assert rows["ACC2"].is_latest  # restatement is current
        assert float(rows["ACC2"].value) == 110.0
        db.close()


_BACKFILL_STD = {
    "revenue": {"current": {"period": "2024-09-28", "value": 100.0}},
    "net_income": {"current": {"period": "2024-09-28", "value": 20.0}},
}


def _fake_extract(xbrl):
    # Only our marked filing yields metrics, so the test is isolated from any other filings that
    # may carry xbrl_data in the shared test DB.
    if isinstance(xbrl, dict) and xbrl.get("mark") == "X":
        return _BACKFILL_STD
    return {}


@pytest.mark.requires_db
class TestBackfill:
    def test_backfill_populates_facts_and_is_idempotent(self):
        from datetime import datetime

        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        filing = Filing(
            company_id=cid,
            accession_number=f"ACC-bf-{uuid.uuid4().hex[:8]}",
            filing_type="10-K",
            filing_date=datetime(2024, 11, 1),
            document_url="https://sec.example/x.htm",
            sec_url="https://sec.example/",
            xbrl_data={"mark": "X"},
        )
        db.add(filing)
        db.commit()

        stats = svc.backfill_facts(db, extract=_fake_extract)
        assert stats["facts_inserted"] == 2  # revenue + net_income from our filing
        assert db.query(FinancialFact).filter_by(company_id=cid).count() == 2

        # Re-running is a no-op (idempotent on the identity key).
        stats2 = svc.backfill_facts(db, extract=_fake_extract)
        assert stats2["facts_inserted"] == 0
        assert stats2["facts_skipped"] >= 2
        db.close()


@pytest.mark.requires_db
class TestGetFundamentals:
    def test_returns_per_concept_series_oldest_first(self):
        from app.database import SessionLocal
        from app.models import Company

        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        company = Company(cik=suffix, ticker=("F" + suffix[:4]).upper(), name=f"Fund {suffix}")
        db.add(company)
        db.commit()
        db.refresh(company)

        common = {"concept": "revenue", "unit": "USD", "fiscal_period": "FY", "form": "10-K",
                  "company_id": company.id, "filing_id": None, "source": "edgar_xbrl"}
        svc.upsert_facts(db, [
            {**common, "period_end": date(2023, 9, 30), "fiscal_year": 2023, "value": 80.0, "accession": "A23"},
        ])
        svc.upsert_facts(db, [
            {**common, "period_end": date(2024, 9, 28), "fiscal_year": 2024, "value": 100.0, "accession": "A24"},
        ])

        out = svc.get_fundamentals(db, company.ticker.lower())  # case-insensitive
        assert out["ticker"] == company.ticker
        revenue = next(c for c in out["concepts"] if c["concept"] == "revenue")
        assert revenue["unit"] == "USD"
        assert [p["value"] for p in revenue["points"]] == [80.0, 100.0]  # oldest → newest
        assert [p["fiscal_year"] for p in revenue["points"]] == [2023, 2024]
        db.close()

    def test_unknown_ticker_returns_none(self):
        from app.database import SessionLocal

        db = SessionLocal()
        assert svc.get_fundamentals(db, "NOPE-NOT-A-TICKER") is None
        db.close()
