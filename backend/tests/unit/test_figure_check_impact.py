"""scripts/figure_check_impact.py: a count-only, read-only measure of what the strict figure check changes (E184).

The script reads stored summaries through a session it guards against writes, runs the retired substring check
and the strict one over each highlights row, and prints aggregate counts. These tests hold it to its header:
the counts by transition, swapped field and withheld takeaway; unavailable and unreadable samples apart; an
explicit bounded cohort; no statement but a SELECT; and no model call.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from scripts import figure_check_impact as impact

REVENUE_TAG = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"


def _annual(value, end, start, **extra):
    return {"value": value, "period": end, "period_start": start, "form": "10-K", "currency": "USD", **extra}


# Apple's FY2025 figures, standardized as provenance_service reads them.
STANDARDIZED = {
    "reporting_currency": "USD",
    "revenue": {"current": _annual(416_161e6, "2025-09-27", "2024-09-29", raw_tag=REVENUE_TAG),
                "prior": _annual(391_035e6, "2024-09-28", "2023-10-01", raw_tag=REVENUE_TAG)},
    "operating_income": {"current": _annual(133_050e6, "2025-09-27", "2024-09-29"),
                         "prior": _annual(123_216e6, "2024-09-28", "2023-10-01")},
}
ROWS = [
    # Matched before and after.
    {"metric": "Total net sales", "current_period": "$416.2B", "prior_period": "$391.0B"},
    # The old check found "416" in "$416.9B"; the strict one shows the filed figure, and withholds the takeaway
    # written from the replaced one.
    {"metric": "Total net sales", "current_period": "$416.9B", "prior_period": "$391.0B",
     "commentary": "Sales reached $416.9B on Services."},
    # Checked and not found before; the strict check replaces it.
    {"metric": "Operating income", "current_period": "$140.0B", "prior_period": "$123.2B"},
    # Never checked.
    {"metric": "Diluted EPS", "current_period": "$7.46", "prior_period": "$6.08"},
]


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def cohort(monkeypatch):
    """Four stored summaries: one to count, one with no table, one whose filing has no XBRL and one whose XBRL
    does not read. Yields their ids by role; deletes every row it made."""
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary
    from app.services.edgar.compat import xbrl_service

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    company = Company(cik=f"fci{suffix}", ticker=f"F{suffix[:4].upper()}", name=f"Impact {suffix}")
    db.add(company)
    db.commit()
    company_id = company.id

    def filing(label, xbrl):
        row = Filing(company_id=company_id, accession_number=f"{suffix}-{label}", filing_type="10-K",
                     filing_date=datetime(2025, 10, 31, tzinfo=timezone.utc), xbrl_data=xbrl,
                     document_url=f"https://sec.example/{suffix}-{label}/doc.htm", sec_url=f"https://sec.example/{suffix}-{label}/")
        db.add(row)
        db.commit()
        return row

    counted, no_table, no_xbrl, unreadable = (
        filing("counted", {"revenue": [1]}), filing("no-table", {"revenue": [1]}),
        filing("no-xbrl", None), filing("unreadable", {"broken": True}),
    )
    summaries = {
        "counted": Summary(filing_id=counted.id, business_overview="Overview.", financial_highlights={"table": ROWS}),
        "no_table": Summary(filing_id=no_table.id, business_overview="Overview.", financial_highlights=None),
        "no_xbrl": Summary(filing_id=no_xbrl.id, business_overview="Overview.", financial_highlights={"table": ROWS}),
        "unreadable": Summary(filing_id=unreadable.id, business_overview="Overview.", financial_highlights={"table": ROWS}),
    }
    db.add_all(summaries.values())
    db.commit()
    ids = {role: summary.id for role, summary in summaries.items()}
    filing_ids = [counted.id, no_table.id, no_xbrl.id, unreadable.id]

    def standardize(xbrl):
        if xbrl.get("broken"):
            raise ValueError("unreadable XBRL")
        return STANDARDIZED

    monkeypatch.setattr(xbrl_service, "extract_standardized_metrics", standardize)
    db.close()
    try:
        yield ids
    finally:
        db = SessionLocal()
        db.query(Summary).filter(Summary.filing_id.in_(filing_ids)).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.id.in_(filing_ids)).delete(synchronize_session=False)
        db.query(Company).filter(Company.id == company_id).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.fixture()
def no_model(monkeypatch):
    """A model client that fails the test if anything constructs it."""
    import openai

    stub = MagicMock(side_effect=AssertionError("figure_check_impact called a model"))
    monkeypatch.setattr(openai, "OpenAI", stub)
    monkeypatch.setattr(openai, "AsyncOpenAI", stub)
    return stub


def test_counts_each_transition_swap_withheld_takeaway_and_sample_it_could_not_read(cohort, no_model):
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        impact.guard_read_only(session)
        report = impact.count_impact(session, [*cohort.values(), 10**9])
    finally:
        session.rollback()
        session.close()
    assert report == {
        "cohort": {"requested": 5, "found": 4, "missing": 1},
        "summaries_counted": 1,
        "rows_counted": 4,
        "transitions": {"matched->matched": 1, "matched->replaced": 1, "unchecked->unchecked": 1,
                        "unmatched->replaced": 1},
        "swapped_fields": {"current_period": 2},
        "withheld_takeaways": 1,
        "unavailable": {"no_filing_xbrl": 1, "no_highlights_table": 1},
        "unreadable": 1,
    }
    no_model.assert_not_called()
    # Aggregate counts only: no metric text, figure, takeaway or identifier reaches the output.
    printed = json.dumps(report)
    assert "Total net sales" not in printed and "416" not in printed and "Services" not in printed


def test_the_guarded_session_refuses_a_write_and_leaves_others_alone(cohort):
    from sqlalchemy import update

    from app.database import SessionLocal
    from app.models import Company, Summary

    session = SessionLocal()
    try:
        impact.guard_read_only(session)
        with pytest.raises(RuntimeError, match="read-only"):
            session.execute(update(Summary).where(Summary.id == cohort["counted"]).values(business_overview="x"))
        session.rollback()
        impact.guard_read_only(session)
        session.add(Company(cik=f"w{uuid.uuid4().hex[:8]}", ticker="WRITE", name="Write"))
        with pytest.raises(RuntimeError, match="read-only"):
            session.flush()
    finally:
        session.rollback()
        session.close()
    with SessionLocal() as other:
        assert other.get(Summary, cohort["counted"]).business_overview == "Overview."


def test_main_exits_non_zero_on_a_partial_count_and_zero_on_a_whole_one(cohort, no_model, capsys):
    assert impact.main(["--summary-ids", f"{cohort['counted']},{cohort['unreadable']}"]) == 1
    assert json.loads(capsys.readouterr().out)["unreadable"] == 1
    assert impact.main(["--summary-ids", str(cohort["counted"]), str(cohort["no_table"])]) == 0
    assert json.loads(capsys.readouterr().out)["summaries_counted"] == 1


@pytest.mark.parametrize("argv", [
    [],
    ["--from-id", "5"],
    ["--from-id", "9", "--to-id", "3"],
    ["--from-id", "1", "--to-id", str(impact.MAX_COHORT + 1)],
])
def test_the_cohort_is_explicit_and_bounded(argv):
    with pytest.raises(SystemExit) as exit_:
        impact.main(argv)
    assert exit_.value.code == 2
