"""Filing URL boundary (CLAUDE.md rule 10): the one archive-URL builder + the model's event listeners.

``app.utils.sec_urls`` owns the canonical archive-URL convention (lessons/sec-filing-url-format.md);
the ``Filing`` ``before_insert``/``before_update`` listeners validate ``sec_url``/``document_url``
against it. Hermetic: a private in-memory SQLite engine, no network.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Company, Filing
from app.utils.sec_urls import (
    build_sec_archive_url,
    companyfacts_url,
    is_acceptable_filing_url,
    is_sec_archive_url,
    normalize_accession,
    normalize_cik,
)

CANONICAL = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/"
DOC = CANONICAL + "aapl-20230930.htm"


# --------------------------------------------------------------------------- the builder


class TestSecUrlHelpers:
    def test_build_strips_cik_zeros_and_accession_dashes(self):
        assert build_sec_archive_url("0000320193", "0000320193-23-000077") == CANONICAL
        # Already-normalized inputs are a no-op.
        assert build_sec_archive_url("320193", "000032019323000077") == CANONICAL

    @pytest.mark.parametrize("cik", ["0", "0000000000", "", None, "abc", "12a"])
    def test_build_rejects_placeholder_or_malformed_cik(self, cik):
        with pytest.raises(ValueError, match="CIK"):
            build_sec_archive_url(cik, "0000320193-23-000077")

    @pytest.mark.parametrize("accession", ["", None, "x", "0000320193-23-00007", "test-123"])
    def test_build_rejects_malformed_accession(self, accession):
        with pytest.raises(ValueError, match="accession"):
            build_sec_archive_url("320193", accession)

    def test_normalizers(self):
        assert normalize_cik("0000320193") == "320193"
        assert normalize_accession("0000320193-23-000077") == "000032019323000077"

    @pytest.mark.parametrize(
        "url",
        [CANONICAL, DOC, CANONICAL + "xslF345X05/wk-form4_1.xml", CANONICAL + "R1.htm?x=1"],
    )
    def test_is_sec_archive_url_accepts_canonical_forms(self, url):
        assert is_sec_archive_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "https://www.sec.gov/Archives/edgar/data/0/000032019323000077/",  # the old placeholder
            "https://www.sec.gov/Archives/edgar/data/0000320193/000032019323000077/",  # padded CIK
            "https://www.sec.gov/Archives/edgar/data/320193/0000320193-23-000077/",  # dashed accession
            "https://www.sec.gov/cgi-bin/viewer?action=view&cik=320193",  # legacy viewer URL
            "http://www.sec.gov/Archives/edgar/data/320193/000032019323000077/",  # not https
            "https://sec.example/",
        ],
    )
    def test_is_sec_archive_url_rejects_non_canonical(self, url):
        assert not is_sec_archive_url(url)

    @pytest.mark.parametrize(
        "url", [CANONICAL, DOC, "https://sec.example/acc-1/", "http://test.com/filing.htm"]
    )
    def test_filing_url_rule_accepts_canonical_sec_and_hermetic_hosts(self, url):
        assert is_acceptable_filing_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "not-a-url",
            "/Archives/edgar/data/320193/000032019323000077/",  # relative
            "https://www.sec.gov/Archives/edgar/data/0/000032019323000077/",  # the old placeholder
            "https://sec.gov/x",  # sec.gov host, non-canonical path
            "https://www.sec.gov/cgi-bin/viewer?action=view&cik=320193",  # legacy viewer URL
        ],
    )
    def test_filing_url_rule_rejects_placeholder_and_malformed_sec_urls(self, url):
        assert not is_acceptable_filing_url(url)

    def test_companyfacts_url_pads_cik(self):
        assert companyfacts_url("320193") == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
        assert companyfacts_url("0000320193") == companyfacts_url("320193")


# --------------------------------------------------------------------------- the listeners


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def company(db: Session) -> Company:
    row = Company(cik="0000320193", ticker="AAPL", name="Apple Inc.")
    db.add(row)
    db.commit()
    return row


def _filing(**overrides) -> Filing:
    base = dict(
        accession_number="0000320193-23-000077",
        filing_type="10-K",
        filing_date=datetime(2023, 11, 3, tzinfo=timezone.utc),
        document_url=DOC,
        sec_url=CANONICAL,
    )
    base.update(overrides)
    return Filing(**base)


class TestBeforeInsert:
    def test_insert_with_company_loaded_derives_sec_url(self, db, company):
        filing = _filing(sec_url=None)
        filing.company = company  # relationship loaded on the pending row
        db.add(filing)
        db.commit()
        assert filing.sec_url == CANONICAL

    def test_insert_without_company_loaded_raises_instead_of_fabricating(self, db, company):
        filing = _filing(sec_url=None, company_id=company.id)  # FK only — relationship NOT loaded
        db.add(filing)
        with pytest.raises(ValueError, match="Company relationship is not loaded"):
            db.flush()
        db.rollback()
        assert db.query(Filing).count() == 0

    def test_insert_without_accession_or_company_raises(self, db, company):
        filing = _filing(sec_url=None, accession_number=None, company_id=company.id)
        db.add(filing)
        with pytest.raises(ValueError, match="accession_number is required"):
            db.flush()
        db.rollback()

    def test_insert_with_explicit_canonical_urls_passes(self, db, company):
        db.add(_filing(company_id=company.id))
        db.commit()
        assert db.query(Filing).one().sec_url == CANONICAL

    @pytest.mark.parametrize(
        "field, value",
        [
            ("sec_url", "https://www.sec.gov/Archives/edgar/data/0/000032019323000077/"),
            ("sec_url", "not-a-url"),
            ("document_url", None),
            ("document_url", "https://sec.gov/x"),
        ],
    )
    def test_insert_with_malformed_url_raises(self, db, company, field, value):
        db.add(_filing(company_id=company.id, **{field: value}))
        with pytest.raises(ValueError, match=field):
            db.flush()
        db.rollback()


class TestBeforeUpdate:
    def test_update_to_none_raises(self, db, company):
        db.add(_filing(company_id=company.id))
        db.commit()
        filing = db.query(Filing).one()
        filing.sec_url = None
        with pytest.raises(ValueError, match="Cannot set sec_url to None"):
            db.flush()
        db.rollback()

    def test_update_to_malformed_url_raises(self, db, company):
        db.add(_filing(company_id=company.id))
        db.commit()
        filing = db.query(Filing).one()
        filing.document_url = "https://www.sec.gov/Archives/edgar/data/0/000032019323000077/x.htm"
        with pytest.raises(ValueError, match="document_url"):
            db.flush()
        db.rollback()

    def test_update_to_canonical_url_passes(self, db, company):
        db.add(_filing(company_id=company.id))
        db.commit()
        filing = db.query(Filing).one()
        filing.document_url = CANONICAL + "R2.htm"
        db.commit()
        assert db.query(Filing).one().document_url == CANONICAL + "R2.htm"

    def test_unrelated_update_on_legacy_url_row_still_flushes(self, db, company):
        """Pre-canonical rows (legacy viewer URLs) must stay updatable; only a CHANGED URL is checked."""
        legacy = "https://www.sec.gov/cgi-bin/viewer?action=view&cik=320193&accession_number=0000320193-23-000077"
        # Core insert bypasses ORM events, exactly like a row written before the validator existed.
        db.execute(
            insert(Filing).values(
                company_id=company.id,
                accession_number="0000320193-23-000077",
                filing_type="10-K",
                filing_date=datetime(2023, 11, 3, tzinfo=timezone.utc),
                document_url=legacy,
                sec_url=legacy,
            )
        )
        db.commit()
        filing = db.query(Filing).one()
        filing.processed_facts_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
        db.commit()  # no raise
        assert db.query(Filing).one().processed_facts_at is not None
