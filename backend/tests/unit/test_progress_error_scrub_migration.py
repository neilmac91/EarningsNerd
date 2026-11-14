"""The one-time scrub of exception text from stored progress rows.

Until 2026-11-14 the generic failure handler stored ``str(exception)`` in ``summary_generation_progress.error``,
which ``GET /api/summaries/filing/{id}/progress`` serves without authentication. The handler stores a fixed code now
(``test_progress_error_text_allowlist.py`` keeps it so); ``migrations/20261114_scrub_progress_error_text.sql``
replaces what the rows already held.
"""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Company, Filing, SummaryGenerationProgress
from app.utils.sec_urls import build_sec_archive_url

MIGRATION = Path(__file__).resolve().parents[2] / "migrations/20261114_scrub_progress_error_text.sql"
CODE = "summary_generation_failed"
RAW = '(psycopg2.errors.UndefinedColumn) column filings.x does not exist\n[SQL: SELECT filings.id FROM filings]'
# The fixed values the application writes to the column; the scrub keeps each.
FIXED = (
    CODE,
    "filing_source_unavailable",
    "sec_rate_limited",
    "Pipeline timeout",
    "Generation stalled and was abandoned. Please retry.",
    "We could not generate this summary. Try again shortly.",
)
EARLIER = datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)
LAST_SECOND = datetime(2026, 11, 14, 15, 59, 59, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 11, 14, 16, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)


def test_the_scrub_replaces_exception_text_written_before_the_cutoff_and_nothing_else():
    """A row last written before the cutoff that holds anything but a fixed value gets the fixed code: raw exception
    text, and the empty text of an exception with no message. A fixed value, a row with no error, and a row written
    at or after the cutoff keep what they hold; the replaced row keeps its stage, its clock and its coverage; and a
    second run changes nothing more."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    company = Company(cik="0000000001", ticker="ONE", name="One")
    db.add(company)
    db.commit()
    rows = {
        "raw": (RAW, EARLIER), "empty": ("", EARLIER), "raw at the last second": (RAW, LAST_SECOND),
        "raw at the cutoff": (RAW, CUTOFF), "raw later": (RAW, LATER), "no error": (None, EARLIER),
        **{f"fixed: {value}": (value, EARLIER) for value in FIXED},
    }
    filing_ids = {}
    for number, (label, (error, written)) in enumerate(rows.items(), start=1):
        accession = f"0000000001-26-{number:06d}"
        sec_url = build_sec_archive_url(company.cik, accession)
        filing = Filing(
            company_id=company.id, accession_number=accession, filing_type="10-K", filing_date=EARLIER,
            sec_url=sec_url, document_url=sec_url + "doc.htm",
        )
        db.add(filing)
        db.flush()
        filing_ids[label] = filing.id
        db.add(SummaryGenerationProgress(
            filing_id=filing.id, stage="error" if error is not None else "summarizing", started_at=written,
            updated_at=written, elapsed_seconds=12.5, error=error, section_coverage={"mdna": True},
        ))
    db.commit()

    script = MIGRATION.read_text(encoding="utf-8")
    # It bounds its PostgreSQL session as the recent migrations do; SQLite runs the UPDATE alone.
    assert "SET lock_timeout" in script and "SET statement_timeout" in script
    update = "\n".join(
        line for line in script.splitlines()
        if not line.startswith(("SET lock_timeout", "SET statement_timeout", "RESET "))
    )

    def migrate() -> dict[str, str | None]:
        raw = db.get_bind().raw_connection()
        try:
            raw.driver_connection.executescript(update)
        finally:
            raw.close()
        db.expire_all()
        return {label: db.get(SummaryGenerationProgress, filing_id).error for label, filing_id in filing_ids.items()}

    expected = {
        "raw": CODE, "empty": CODE, "raw at the last second": CODE,
        "raw at the cutoff": RAW, "raw later": RAW, "no error": None,
        **{f"fixed: {value}": value for value in FIXED},
    }
    assert migrate() == expected
    assert migrate() == expected
    replaced = db.get(SummaryGenerationProgress, filing_ids["raw"])
    assert (replaced.stage, replaced.elapsed_seconds, replaced.section_coverage) == ("error", 12.5, {"mdna": True})
    assert replaced.updated_at.replace(tzinfo=timezone.utc) == EARLIER
