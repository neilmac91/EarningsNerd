"""scripts/figure_check_impact.py: a count-only, read-only measure of what the strict figure check changes (E184).

The script reads stored summaries through a session it guards against writes, runs the retired substring check
and the strict one over each highlights row, and prints aggregate counts. These tests hold it to its header:
the counts by transition, swapped field and withheld takeaway; unavailable and unreadable samples apart, a summary
counted whole or not at all; an explicit bounded cohort; no statement but a SELECT; and no model call.
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


# A schema-2 summary's row, read from raw_summary's results_that_matter as the page reads it: its current figure
# matches, its prior ($383.3B against the filed $391.0B) is replaced.
SCHEMA_TWO_ROWS = [{"metric": "Total net sales", "current_period": "$416.2B", "prior_period": "$383.3B"}]


@pytest.fixture()
def cohort(monkeypatch):
    """Six stored summaries: one to count, one with no table, one whose filing has no XBRL, one whose XBRL does not
    read, one whose fourth row does not read after three that do, and a schema-2 one read from its sections (its
    compatibility column holds another table). Yields their ids by role; deletes every row it made, whatever fails."""
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary
    from app.services.edgar.compat import xbrl_service

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    company_id = None
    try:
        company = Company(cik=f"fci{suffix}", ticker=f"F{suffix[:4].upper()}", name=f"Impact {suffix}")
        db.add(company)
        db.commit()
        company_id = company.id

        def filing(label, xbrl):
            row = Filing(company_id=company_id, accession_number=f"{suffix}-{label}", filing_type="10-K",
                         filing_date=datetime(2025, 10, 31, tzinfo=timezone.utc), xbrl_data=xbrl,
                         document_url=f"https://sec.example/{suffix}-{label}/doc.htm",
                         sec_url=f"https://sec.example/{suffix}-{label}/")
            db.add(row)
            db.commit()
            return row

        counted, no_table, no_xbrl, unreadable, partial, schema_two = (
            filing("counted", {"revenue": [1]}), filing("no-table", {"revenue": [1]}),
            filing("no-xbrl", None), filing("unreadable", {"broken": True}), filing("partial", {"partial": True}),
            filing("schema-two", {"revenue": [1]}),
        )
        # The partial summary's operating income is filed as no finite number: its first rows read, its fourth cannot.
        partial_rows = [ROWS[0], ROWS[1], ROWS[3], ROWS[2]]
        summaries = {
            "counted": Summary(filing_id=counted.id, business_overview="Overview.", financial_highlights={"table": ROWS}),
            "no_table": Summary(filing_id=no_table.id, business_overview="Overview.", financial_highlights=None),
            "no_xbrl": Summary(filing_id=no_xbrl.id, business_overview="Overview.", financial_highlights={"table": ROWS}),
            "unreadable": Summary(filing_id=unreadable.id, business_overview="Overview.",
                                  financial_highlights={"table": ROWS}),
            "partial": Summary(filing_id=partial.id, business_overview="Overview.",
                               financial_highlights={"table": partial_rows}),
            "schema_two": Summary(filing_id=schema_two.id, business_overview="Overview.",
                                  financial_highlights={"table": [ROWS[3]]},
                                  raw_summary={"schema_version": 2, "sections": {
                                      "results_that_matter": {"table": SCHEMA_TWO_ROWS}}}),
        }
        db.add_all(summaries.values())
        db.commit()
        ids = {role: summary.id for role, summary in summaries.items()}

        def standardize(xbrl):
            if xbrl.get("broken"):
                raise ValueError("unreadable XBRL")
            if xbrl.get("partial"):
                operating = STANDARDIZED["operating_income"]
                return {**STANDARDIZED, "operating_income": {**operating, "current": {**operating["current"],
                                                                                       "value": float("inf")}}}
            return STANDARDIZED

        monkeypatch.setattr(xbrl_service, "extract_standardized_metrics", standardize)
        db.close()
        yield ids
    finally:
        db.close()
        if company_id is not None:
            with SessionLocal() as cleanup:
                filing_ids = [row.id for row in cleanup.query(Filing.id).filter(Filing.company_id == company_id)]
                cleanup.query(Summary).filter(Summary.filing_id.in_(filing_ids)).delete(synchronize_session=False)
                cleanup.query(Filing).filter(Filing.id.in_(filing_ids)).delete(synchronize_session=False)
                cleanup.query(Company).filter(Company.id == company_id).delete(synchronize_session=False)
                cleanup.commit()


@pytest.fixture()
def no_model(monkeypatch):
    """A model call that fails the test: constructing a client, or a request through any client, one built before
    this stub among them (every request of the openai SDK goes through its base clients' ``request``)."""
    import openai
    from openai import _base_client

    stub = MagicMock(side_effect=AssertionError("figure_check_impact called a model"))
    monkeypatch.setattr(openai, "OpenAI", stub)
    monkeypatch.setattr(openai, "AsyncOpenAI", stub)
    monkeypatch.setattr(_base_client.SyncAPIClient, "request", stub)
    monkeypatch.setattr(_base_client.AsyncAPIClient, "request", stub)
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
    # The partial summary adds its unreadable count alone, none of the three rows it read before the fourth; the
    # schema-2 summary is read from its sections (its replaced prior), never from its compatibility column.
    assert report == {
        "cohort": {"requested": 7, "found": 6, "missing": 1, "range": False},
        "summaries_counted": 2,
        "rows_counted": 5,
        "transitions": {"matched->matched": 1, "matched->replaced": 2, "unchecked->unchecked": 1,
                        "unmatched->replaced": 1},
        "swapped_fields": {"current_period": 2, "prior_period": 1},
        "withheld_takeaways": 1,
        "unavailable": {"no_filing_xbrl": 1, "no_highlights_table": 1},
        "unreadable": 2,
    }
    no_model.assert_not_called()
    # Aggregate counts only: no metric text, figure, takeaway or identifier reaches the output.
    printed = json.dumps(report)
    assert "Total net sales" not in printed and "416" not in printed and "Services" not in printed


def test_the_guarded_session_refuses_a_write_and_leaves_others_alone(cohort):
    from sqlalchemy import text, update

    from app.database import SessionLocal
    from app.models import Company, Summary

    session = SessionLocal()
    other_cik = f"o{uuid.uuid4().hex[:8]}"
    try:
        impact.guard_read_only(session)
        with pytest.raises(RuntimeError, match="read-only"):
            session.execute(update(Summary).where(Summary.id == cohort["counted"]).values(business_overview="x"))
        session.rollback()
        impact.guard_read_only(session)
        # A write a CTE carries is refused too: the guard takes SELECT alone.
        with pytest.raises(RuntimeError, match="read-only; refused a WITH"):
            session.execute(text("WITH t AS (SELECT :id AS id) UPDATE summaries SET business_overview = 'x' "
                                 "WHERE id IN (SELECT id FROM t)"), {"id": cohort["counted"]})
        session.rollback()
        impact.guard_read_only(session)
        session.add(Company(cik=f"w{uuid.uuid4().hex[:8]}", ticker="WRITE", name="Write"))
        with pytest.raises(RuntimeError, match="refused a flush"):
            session.flush()
        session.rollback()
        impact.guard_read_only(session)
        # The guard is the guarded session's alone: another session writes beside it.
        with SessionLocal() as other:
            other.add(Company(cik=other_cik, ticker="OTHER", name="Other"))
            other.commit()
        assert session.query(Summary).filter(Summary.id == cohort["counted"]).one().business_overview == "Overview."
    finally:
        session.rollback()
        session.close()
    with SessionLocal() as other:
        assert other.get(Summary, cohort["counted"]).business_overview == "Overview."
        assert other.query(Company).filter(Company.cik == other_cik).delete() == 1
        other.commit()


def test_a_no_total_banks_revenue_row_is_dropped_by_both_checks():
    # The page drops a no-total bank's revenue row, as the retired check's enrichment did (751ce417^): no change.
    bank = {"reporting_currency": "USD", "revenue": {"current": {"value": None}},
            "net_interest_income": {"current": _annual(60_000e6, "2025-12-31", "2025-01-01")}}
    block = {"table": [{"metric": "Total revenue", "current_period": "$90.0B", "prior_period": "$85.0B"},
                       {"metric": "Diluted EPS", "current_period": "$4.10", "prior_period": "$3.90"}]}
    filing = type("Filing", (), {"document_url": "https://sec.example/doc.htm", "sec_url": None,
                                 "accession_number": "0000000001-25-000001"})()
    transitions, swapped, withheld = impact._count_summary(block, filing, bank)
    assert transitions == {("dropped", "dropped"): 1, ("unchecked", "unchecked"): 1}
    assert (dict(swapped), withheld) == ({}, 0)


def test_main_exits_non_zero_on_a_partial_count_and_zero_on_a_whole_one(cohort, no_model, capsys):
    assert impact.main(["--summary-ids", f"{cohort['counted']},{cohort['unreadable']}"]) == 1
    assert json.loads(capsys.readouterr().out)["unreadable"] == 1
    # An id the list names that is not there is a partial count too.
    assert impact.main(["--summary-ids", str(cohort["counted"]), str(10**9)]) == 1
    assert json.loads(capsys.readouterr().out)["cohort"]["missing"] == 1
    assert impact.main(["--summary-ids", str(cohort["counted"]), str(cohort["no_table"])]) == 0
    assert json.loads(capsys.readouterr().out)["summaries_counted"] == 1


def test_a_ranges_absent_ids_are_reported_and_fail_nothing(cohort, no_model, capsys):
    # A range's absent ids are its gaps (summaries deleted or never made), reported, not failed; an unreadable
    # summary in a range still fails it.
    top = max(cohort.values())
    assert impact.main(["--from-id", str(top + 1), "--to-id", str(top + 3)]) == 0
    assert json.loads(capsys.readouterr().out)["cohort"] == {"requested": 3, "found": 0, "missing": 3, "range": True}
    assert impact.main(["--from-id", str(cohort["unreadable"]), "--to-id", str(cohort["unreadable"])]) == 1
    assert json.loads(capsys.readouterr().out)["unreadable"] == 1


def test_a_cohort_of_exactly_the_bound_is_accepted():
    import argparse

    args = argparse.Namespace(summary_ids=None, from_id=1, to_id=impact.MAX_COHORT)
    assert len(impact.parse_cohort(args)) == impact.MAX_COHORT


@pytest.mark.parametrize("argv", [
    [],
    ["--from-id", "5"],
    ["--from-id", "9", "--to-id", "3"],
    ["--from-id", "1", "--to-id", str(impact.MAX_COHORT + 1)],
    ["--summary-ids", "1", "--from-id", "1", "--to-id", "2"],
    ["--summary-ids", ","],
])
def test_the_cohort_is_explicit_and_bounded(argv):
    with pytest.raises(SystemExit) as exit_:
        impact.main(argv)
    assert exit_.value.code == 2
