"""The E184 count (``scripts/count_figure_check_changes.py``) reads the stored rows as the page does and
labels each the way main's check did before #1530 and the way the strict check does now.

The old check is a copy of main's at ae2a7844, so its own defects are pinned here as its behaviour: a
wrong scale or a wrong tenth matched, the prior period was never read. The new outcome is the strict
check's, with a swap's fields and its withheld takeaway. The whole count runs once over an in-memory
database, so the join, the paging and every counter are exercised, and writes nothing; what SQLite
cannot show (a read-only session refusing a write, Postgres JSON decoding, the lock a page holds) the
Ops step's read-back and its gates hold."""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from app.utils.datetimes import utcnow

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("count_figure_check_changes", ROOT / "scripts" / "count_figure_check_changes.py")
script = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("count_figure_check_changes", script)
_SPEC.loader.exec_module(script)

SEC_URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/"
DOC_URL = SEC_URL + "aapl-20250927.htm"


def _fact(value, period="2025-09-27", start="2024-09-29", tag="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"):
    return {"period": period, "value": value, "form": "10-K", "currency": "USD", "raw_tag": tag, "period_start": start}


XBRL_DATA = {
    "revenue": [_fact(416_161_000_000), _fact(391_035_000_000, "2024-09-28", "2023-10-01")],
    "net_income": [_fact(112_010_000_000, tag="us-gaap:NetIncomeLoss"), _fact(93_736_000_000, "2024-09-28", "2023-10-01", "us-gaap:NetIncomeLoss")],
    "operating_income": [_fact(133_050_000_000, tag="us-gaap:OperatingIncomeLoss"), _fact(123_216_000_000, "2024-09-28", "2023-10-01", "us-gaap:OperatingIncomeLoss")],
    "gross_profit": [_fact(512_345_678, tag="us-gaap:GrossProfit"), _fact(480_000_000, "2024-09-28", "2023-10-01", "us-gaap:GrossProfit")],
    "reporting_currency": "USD",
}
ROWS = [
    # Right on both years: matched on main (the digits appear), matched now.
    {"metric": "Total net sales", "current_period": "$416.2B", "prior_period": "$391.0B", "commentary": "Up 6.4%."},
    # The wrong scale: main's substring check matched "416.2"; the strict check swaps the current figure in,
    # and withholds the takeaway, which states a figure.
    {"metric": "Revenue", "current_period": "$416.2M", "prior_period": "$391.0B", "commentary": "Grew 6.4% on the year."},
    # A wrong prior: main never read it; the strict check swaps it, and keeps a takeaway that names no figure.
    {"metric": "Operating income", "current_period": "$133.1B", "prior_period": "$120.0B", "commentary": "Services grew fastest in FY2025."},
    # A wrong prior under net income, which the strict check matches but never replaces (the parent's share or the
    # consolidated total): main matched the current figure; the row is now left unchecked.
    {"metric": "Net income", "current_period": "$112.0B", "prior_period": "$92.0B", "commentary": "Up 19.5%."},
    # Never checked by either: no mapped concept.
    {"metric": "Diluted earnings per share", "current_period": "$7.46", "prior_period": "$6.08", "commentary": "Up 22.7%."},
    # Main matched a segment line's figure by substring ("net sales" maps revenue) when it happened to equal the
    # total; the strict check maps whole labels and leaves a segment unchecked.
    {"metric": "Services net sales", "current_period": "$416.2B", "prior_period": "$391.0B"},
    # A wrong figure main's digits never found: linked then, swapped now, its figured takeaway withheld.
    {"metric": "Operating income", "current_period": "$140.0B", "prior_period": "$123.2B", "commentary": "Up 5% on the year."},
    # A figure main's candidates could not read ("$0.51B" holds no "512"): linked then, matched now.
    {"metric": "Gross profit", "current_period": "$0.51B", "prior_period": "$0.48B", "commentary": "Margin held."},
]
# Each row's transition, old label to new outcome, in ROWS order: the fixture's meaning in one place.
TRANSITIONS = [
    "matched -> matched", "matched -> swapped", "matched -> swapped", "matched -> linked",
    "linked -> linked", "matched -> linked", "linked -> swapped", "linked -> matched",
]


class _Filing:
    document_url = DOC_URL
    sec_url = SEC_URL
    filing_type = "10-K"
    xbrl_data = XBRL_DATA
    id = 3


class _Summary:
    def __init__(self, raw_summary=None, financial_highlights=None, schema_version=2, risk_factors=None):
        self.raw_summary = raw_summary
        self.financial_highlights = financial_highlights
        self.schema_version = schema_version
        self.risk_factors = risk_factors
        self.filing_id = 3


def _xbrl():
    from app.services.provenance_service import standardized_xbrl

    return standardized_xbrl(_Filing())


class TestOldLabel:
    # The last is a bare number: main read its leading digits ("416") as a match.
    @pytest.mark.parametrize("shown", ["$416.2B", "$416.2M", "$416.9B", "$4,416.2B", "$416,161M", "416161", 416.2e9])
    def test_mains_substring_check_matched_these(self, shown):
        assert script.old_label({"metric": "Revenue", "current_period": shown}, _xbrl()) == "matched"

    @pytest.mark.parametrize("shown", ["$391.0B", "$41.6B", "—", None, ""])
    def test_and_left_these_linked(self, shown):
        assert script.old_label({"metric": "Revenue", "current_period": shown}, _xbrl()) == "linked"

    def test_a_substring_of_the_label_mapped_the_concept(self):
        assert script.old_label({"metric": "Services net sales", "current_period": "$416.2B"}, _xbrl()) == "matched"

    def test_the_prior_period_was_never_read(self):
        assert script.old_label({"metric": "Revenue", "current_period": "$416.2B", "prior_period": "$1.0B"}, _xbrl()) == "matched"

    def test_an_unmapped_label_a_small_value_or_no_data_is_linked(self):
        assert script.old_label({"metric": "Diluted EPS", "current_period": "$7.46"}, _xbrl()) == "linked"
        assert script.old_label({"metric": "Revenue", "current_period": "$416.2B"}, None) == "linked"
        small = {"revenue": {"current": {"value": 500_000.0, "period": "2025-09-27"}}}
        assert script.old_label({"metric": "Revenue", "current_period": "$500,000"}, small) == "linked"

    # Main's check as it stood, at its edges: a loss by its magnitude, a value under a billion by its millions, a
    # wrong scale by its digits only, and the current period's snake_case key alone.
    @pytest.mark.parametrize("value, shown, label", [
        (-5_000_000_000, "$(5.0)B", "matched"),
        (512_345_678, "$512.3M", "matched"),
        (5_200_000_000, "$15.0M", "linked"),
        (1_000_000, "$1.0M", "matched"),
    ])
    def test_mains_check_at_its_edges(self, value, shown, label):
        xbrl = {"revenue": {"current": {"value": value, "period": "2025-09-27"}}}
        assert script.old_label({"metric": "Revenue", "current_period": shown}, xbrl) == label

    def test_main_read_the_current_periods_snake_case_key_alone(self):
        assert script.old_label({"metric": "Revenue", "currentPeriod": "$416.2B"}, _xbrl()) == "linked"


class TestNewOutcome:
    def test_reads_each_row_as_the_pages_enrichment_does(self):
        """The strict check's own behaviours are gated in test_provenance_service.py; what the count claims is
        that it reads a row as the page does, so each row's outcome is compared with the enriched row."""
        from app.services.provenance_service import enrich_financial_highlights

        enriched = enrich_financial_highlights({"table": copy.deepcopy(ROWS), "source_section_ref": "Item 8"}, _Filing(), _xbrl())
        for row, shown in zip(ROWS, enriched["table"]):
            label, fields, withheld = script.new_outcome(row, _Filing(), _xbrl(), "Item 8")
            replaced = shown.get("source_replaced") or {}
            assert fields == tuple(replaced), row["metric"]
            assert withheld == (shown.get("commentary_withheld") == "figure_replaced"), row["metric"]
            assert label == ("swapped" if replaced else "matched" if shown["source_verified"] else "linked"), row["metric"]

    def test_the_fixture_holds_every_outcome_the_count_can_give(self):
        outcomes = [script.new_outcome(row, _Filing(), _xbrl(), "Item 8") for row in ROWS]
        assert outcomes[1] == ("swapped", ("current_period",), True) and outcomes[2] == ("swapped", ("prior_period",), False)
        assert outcomes[6] == ("swapped", ("current_period",), True) and outcomes[7] == ("matched", (), False)
        assert {outcome[0] for outcome in outcomes} == {"matched", "swapped", "linked"}


class TestHighlightRows:
    def test_a_v2_raw_summary_gives_its_results_table(self):
        raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": ROWS, "source_section_ref": "Item 8"}}}
        rows, ref, container = script.highlight_rows(_Summary(raw_summary=raw))
        assert (len(rows), ref, container) == (8, "Item 8", "results_that_matter")

    def test_a_v1_raw_summary_gives_its_highlights_table(self):
        raw = {"schema_version": 1, "sections": {"financial_highlights": {"table": ROWS[:2], "sourceSectionRef": "Item 7"}}}
        rows, ref, container = script.highlight_rows(_Summary(raw_summary=raw, schema_version=1))
        assert (len(rows), ref, container) == (2, "Item 7", "financial_highlights")

    def test_the_legacy_column_is_never_read_since_the_page_never_draws_it(self):
        # A summary whose raw summary holds no table renders no metrics block (``rendered_sections`` is built from
        # the raw summary alone), whatever the legacy ``financial_highlights`` column holds.
        rows, ref, container = script.highlight_rows(_Summary(raw_summary={"sections": {}}, financial_highlights={"table": ROWS[:1]}))
        assert (rows, ref, container) == ([], None, "none")

    def test_a_row_with_no_metric_label_is_skipped_as_the_renderer_skips_it(self):
        raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": [
            {"metric": "", "current_period": "$1.0B"}, {"metric": None, "current_period": "$1.0B"}, {"current_period": "$1.0B"}, ROWS[0],
        ]}}}
        rows, _ref, _container = script.highlight_rows(_Summary(raw_summary=raw))
        assert rows == [ROWS[0]]

    def test_a_summary_with_no_table_anywhere_gives_none(self):
        assert script.highlight_rows(_Summary(raw_summary=None, financial_highlights=None)) == ([], None, "none")


class TestCountSummary:
    def test_tallies_each_rows_transition_swap_and_withheld_takeaway(self):
        counts = script.new_counts()
        raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": copy.deepcopy(ROWS), "source_section_ref": "Item 8"}}}
        script.count_summary(_Summary(raw_summary=raw), _Filing(), counts)
        assert counts["summaries"] == counts["summaries_with_rows"] == 1
        assert counts["rows"] == 8 and counts["summaries_without_xbrl"] == 0 and counts["summaries_xbrl_failed"] == 0
        assert dict(counts["transitions"]) == {transition: TRANSITIONS.count(transition) for transition in set(TRANSITIONS)}
        assert dict(counts["transitions_by_form"]) == {f"10-K: {transition}": TRANSITIONS.count(transition) for transition in set(TRANSITIONS)}
        assert dict(counts["swapped_fields"]) == {"current_period": 2, "prior_period": 1}
        assert counts["takeaways_withheld"] == 2
        assert (counts["summaries_with_a_swap"], counts["summaries_losing_a_match"], counts["summaries_gaining_a_match"]) == (1, 1, 1)
        assert dict(counts["rows_by_container"]) == {"results_that_matter": 8}

    def test_a_summary_with_only_a_lost_match_or_only_a_gained_one_is_counted_once_each(self):
        counts = script.new_counts()
        for rows in (ROWS[3:4], ROWS[7:8]):
            raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": copy.deepcopy(rows)}}}
            script.count_summary(_Summary(raw_summary=raw), _Filing(), counts)
        assert (counts["summaries_with_a_swap"], counts["summaries_losing_a_match"], counts["summaries_gaining_a_match"]) == (0, 1, 1)

    def test_a_no_total_banks_conflated_revenue_row_is_dropped_as_enrichment_drops_it(self):
        class Bank(_Filing):
            xbrl_data = {
                "net_interest_income": [_fact(95_443_000_000, "2025-12-31", "2025-01-01", "us-gaap:InterestIncomeExpenseNet")],
                "reporting_currency": "USD",
            }

        counts = script.new_counts()
        raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": [
            {"metric": "Revenue", "current_period": "$182.4B", "prior_period": "$177.6B"},
            {"metric": "Net interest income", "current_period": "$95.4B", "prior_period": "$92.6B"},
        ]}}}
        script.count_summary(_Summary(raw_summary=raw), Bank(), counts)
        assert (counts["rows_dropped_no_total_bank"], counts["rows"]) == (1, 1)

    def test_a_summary_without_a_table_without_xbrl_or_whose_xbrl_fails_is_counted_as_such(self, caplog):
        counts = script.new_counts()
        script.count_summary(_Summary(), _Filing(), counts)

        class Bare(_Filing):
            xbrl_data = None

        class Broken(_Filing):
            xbrl_data = {"revenue": "not a series"}
            id = 4242

        raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": copy.deepcopy(ROWS[:1])}}}
        with caplog.at_level("DEBUG"):
            script.count_summary(_Summary(raw_summary=raw), Bare(), counts)
            script.count_summary(_Summary(raw_summary=copy.deepcopy(raw)), Broken(), counts)
        assert (counts["summaries"], counts["summaries_without_a_table"], counts["summaries_with_rows"]) == (3, 1, 2)
        assert (counts["summaries_without_xbrl"], counts["summaries_xbrl_failed"]) == (1, 1)
        assert dict(counts["transitions"]) == {"linked -> linked": 2}
        # The page's own read logs "[summary:4242] XBRL standardization ... failed" on this path; the count logs nothing.
        assert [record.getMessage() for record in caplog.records] == []


class TestCountStoredSummaries:
    def test_reads_every_stored_summary_with_its_own_filing_and_writes_nothing(self):
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker

        from app.models import Base, Company, Filing, Summary

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        statements: list[str] = []
        event.listen(engine, "before_cursor_execute", lambda conn, cursor, statement, *rest: statements.append(statement))
        session_factory = sessionmaker(bind=engine)

        def filing(session, company, accession, form, xbrl=XBRL_DATA):
            row = Filing(company_id=company.id, accession_number=accession, filing_type=form, filing_date=utcnow(),
                         document_url=DOC_URL, sec_url=SEC_URL, xbrl_data=xbrl)
            session.add(row)
            session.flush()
            return row

        with session_factory() as session:
            company = Company(cik="0000320193", ticker="AAPL", name="Apple Inc.")
            session.add(company)
            session.flush()
            # A filing with no summary first, so no summary's id equals its own filing's: a join on the wrong
            # column pairs a summary with another filing's XBRL and form.
            filing(session, company, "0000320193-23-000001", "10-K")
            annual = filing(session, company, "0000320193-25-000079", "10-K")
            raw = {"schema_version": 2, "sections": {"results_that_matter": {"table": copy.deepcopy(ROWS), "source_section_ref": "Item 8"}}}
            # One summary per filing (uq_summaries_filing_id). The first holds a raw table and a legacy column: the
            # raw table is read. The second, a 10-Q, holds a v1 raw table. The third holds the legacy column alone.
            session.add(Summary(filing_id=annual.id, raw_summary=raw, schema_version=2, financial_highlights={"table": copy.deepcopy(ROWS[:1])}))
            quarter = filing(session, company, "0000320193-25-000050", "10-Q")
            session.add(Summary(filing_id=quarter.id, schema_version=1, raw_summary={
                "schema_version": 1, "sections": {"financial_highlights": {"table": copy.deepcopy(ROWS[:1])}}}))
            legacy = filing(session, company, "0000320193-24-000123", "10-K")
            session.add(Summary(filing_id=legacy.id, raw_summary=None, financial_highlights={"table": copy.deepcopy(ROWS[:1])}))
            session.commit()
            statements.clear()
            counts = script.count_stored_summaries(session)
            paged = script.count_stored_summaries(session, page_size=1)
            limited = script.count_stored_summaries(session, limit=1, page_size=1)
        assert (counts["summaries"], counts["summaries_with_rows"], counts["summaries_without_a_table"]) == (3, 2, 1)
        assert dict(counts["rows_by_container"]) == {"results_that_matter": 8, "financial_highlights": 1}
        assert dict(counts["transitions"]) == {**{t: TRANSITIONS.count(t) for t in set(TRANSITIONS)}, "matched -> matched": 2}
        assert dict(counts["transitions_by_form"])["10-Q: matched -> matched"] == 1, "each summary is joined to its own filing"
        assert (limited["summaries"], limited["rows"], dict(limited["rows_by_container"])) == (1, 8, {"results_that_matter": 8})
        assert paged == counts, "a page per transaction reads every summary once"
        assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements), statements
        printed = script.as_json(counts) + "\n" + "\n".join(script.as_lines(counts))
        assert "matched -> swapped" in printed and "transitions:" in printed
        # Counts only: no label, figure, ticker, CIK or accession from the fixture reaches the output.
        for secret in ("Total net sales", "Services", "$416", "416,161", "AAPL", "Apple", "320193", "000079", "Up 6.4%"):
            assert secret not in printed, secret
