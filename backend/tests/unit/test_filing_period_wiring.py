"""Persisted reporting dates reach the real fact writer; historical rows remain idempotent."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Company, Filing, FinancialFact
from app.services import facts_service as svc
from app.utils.sec_urls import build_sec_archive_url


@pytest.fixture
def db(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'facts.db'))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def persisted_filing(db, report_date):
    company = Company(cik='320193', ticker='TEST', name='Test source')
    accession = '0000320193-25-000079'
    url = build_sec_archive_url(company.cik, accession)
    filing = Filing(company=company, accession_number=accession, filing_type='10-K',
                    filing_date=datetime(2025, 2, 1, tzinfo=timezone.utc),
                    period_end_date=report_date, document_url=url, sec_url=url,
                    xbrl_data={'source': 'test'})
    db.add(filing)
    db.commit()
    db.expire_all()
    return db.query(Filing).one()


def source_metrics():
    return {'revenue': {'series': [{'period': '2024-12-31', 'value': 120.0},
                                   {'period': '2023-12-31', 'value': 100.0}]}}


def rows(db):
    db.expire_all()
    return [(r.period_end, float(r.value), r.unit, r.reconciled, r.is_latest)
            for r in db.query(FinancialFact).order_by(FinancialFact.period_end).all()]


@pytest.mark.parametrize('report_date,current_flag', [
    (datetime(2024, 12, 31, 23, 30, tzinfo=timezone.utc), True),
    (datetime(2024, 9, 30, tzinfo=timezone.utc), False),
    (None, True),
])
def test_persisted_report_date_controls_current_but_not_comparative(db, report_date, current_flag):
    filing = persisted_filing(db, report_date)
    result = svc.process_filing_facts(db, filing, standardized=source_metrics())
    assert result == {'inserted': 2, 'skipped': 0, 'rejected': 0}
    assert rows(db) == [(date(2023, 12, 31), 100.0, 'USD', True, True),
                        (date(2024, 12, 31), 120.0, 'USD', current_flag, True)]
    assert db.query(Filing).one().processed_facts_at is not None


def test_backfill_uses_persisted_date(db):
    persisted_filing(db, datetime(2024, 9, 30, tzinfo=timezone.utc))
    result = svc.backfill_facts(db, extract=lambda _: source_metrics(), cross_check=False)
    assert result == {'filings_processed': 1, 'facts_inserted': 2, 'facts_skipped': 0,
                      'facts_rejected': 0, 'extract_errors': 0}
    assert [r[3] for r in rows(db)] == [True, False]


def test_existing_identity_does_not_repair_stored_flags(db):
    filing = persisted_filing(db, None)
    svc.process_filing_facts(db, filing, standardized=source_metrics())
    before = rows(db)
    identities = [(r.id, r.accession) for r in db.query(FinancialFact).order_by(FinancialFact.id)]
    filing.period_end_date = datetime(2024, 9, 30, tzinfo=timezone.utc)
    db.commit()
    result = svc.process_filing_facts(db, filing, standardized=source_metrics())
    assert result == {'inserted': 0, 'skipped': 2, 'rejected': 0}
    assert rows(db) == before
    assert [(r.id, r.accession) for r in db.query(FinancialFact).order_by(FinancialFact.id)] == identities


def test_authoritative_confirmation_keeps_existing_override_policy(db):
    filing = persisted_filing(db, datetime(2024, 9, 30, tzinfo=timezone.utc))
    result = svc.process_filing_facts(db, filing, standardized=source_metrics(),
        authoritative={('revenue', date(2024, 12, 31)): 120.0})
    assert result == {'inserted': 2, 'skipped': 0, 'rejected': 0}
    assert [r[3] for r in rows(db)] == [True, True]
