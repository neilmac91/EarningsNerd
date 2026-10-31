"""The lineage backfill for filing-owned legacy calculations (Multi-Period Analysis WP0).

A filing-owned margin, free cash flow, working capital or current ratio stored before #1191 has no
versioned provenance, so readers show it as ``legacy_calculation``, and no writer ever gives it
lineage. ``app/services/filing_lineage_repair.py`` recomputes each one from the operands its own
accession stores, through the per-filing writer's calculator, and writes ``provenance`` and
``reconciled`` only: a pass, or a concern with positive evidence (a recomputed value that differs,
an operand's review state). It holds, unchanged and counted, a row the old gate flagged, one whose
record would withhold a shown figure, one whose operands it cannot find and one with a legacy
calculation among its operands. Values are read back through the ORM, so they arrive as Decimal,
as production's ``Numeric`` column gives them. ``scripts/repair_filing_lineage.py`` runs it, a dry
run by default, one transaction per company.
"""
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Query, Session, sessionmaker

from app import database
from app.models import Base, Company, Filing, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import facts_service, filing_lineage_repair as repair, quarterly_fact_repair
from app.services.fact_provenance import METRIC_FORMULAS, reported_provenance
from app.services.trend_analysis.data_notes import data_notes
from app.services.trend_analysis.dataset_quality import dataset_point
from app.utils.sec_urls import build_sec_archive_url
from scripts import repair_filing_lineage as cli

pytestmark = pytest.mark.unit

START, END = date(2025, 1, 1), date(2025, 12, 31)
_TAG = object()  # a reported operand's us-gaap tag; a formula row's NULL tag


@pytest.fixture
def factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'lineage.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)  # the CLI opens its sessions from here
    yield sessions
    engine.dispose()


@pytest.fixture
def db(factory):
    with factory() as session:
        yield session


def _company(db, ticker="REGN", cik="0000872589"):
    company = Company(cik=cik, ticker=ticker, name=ticker)
    db.add(company)
    db.flush()
    accession = f"{cik}-26-000008"
    url = build_sec_archive_url(cik, accession)
    filing = Filing(
        company_id=company.id, accession_number=accession, filing_type="10-K",
        filing_date=datetime(2026, 2, 10, tzinfo=timezone.utc), sec_url=url, document_url=f"{url}a.htm",
    )
    db.add(filing)
    db.flush()
    return company, filing


def _row(db, company, concept, value, *, filing=None, accession=None, raw_tag=_TAG, unit=None, start=_TAG,
         reconciled=True, provenance=None, source="edgar_xbrl", **extra):
    """A stored row as the legacy writers left it: NULL provenance unless given. A formula row has no
    tag of its own, a margin or ratio is ``pure`` and a margin has no start date, as the per-filing
    writer stores them; an operand is a reported ``us-gaap`` duration over the fiscal year."""
    formula = concept in METRIC_FORMULAS
    row = FinancialFact(
        company_id=company.id, filing_id=filing.id if filing else None, concept=concept,
        raw_tag=(None if formula else f"us-gaap:{concept}") if raw_tag is _TAG else raw_tag,
        unit=unit or ("pure" if concept.endswith(("_margin", "_ratio")) else "USD"),
        period_start=(None if formula else START) if start is _TAG else start,
        period_end=extra.pop("end", END), fiscal_year=extra.pop("fiscal_year", 2025),
        fiscal_period=extra.pop("fiscal_period", "FY"), value=Decimal(str(value)), form="10-K",
        accession=accession or filing.accession_number, source=source, reconciled=reconciled,
        is_latest=extra.pop("is_latest", True), provenance=provenance, **extra,
    )
    db.add(row)
    db.flush()
    return row


def _margin(db, company, filing, *, margin=25.0, revenue=1000, income=250, **margin_fields):
    """A filing-owned legacy operating margin and its two legacy operands under the filing's accession."""
    _row(db, company, "revenue", revenue, filing=filing)
    _row(db, company, "operating_income", income, filing=filing)
    return _row(db, company, "operating_margin", margin, filing=filing, **margin_fields)


def _states(db):
    db.expire_all()
    return {row.id: quarterly_fact_repair.snapshot(row) for row in db.query(FinancialFact).all()}


def _apply(db, company, run_id="run-1"):
    result = repair.backfill_company(db, company.id, apply=True, run_id=run_id)
    db.commit()
    return result


def _writes(statements):
    return [s for s in statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def _v1(validation="passed", reasons=(), **fields):
    """A version-1 record of a reported operand, as today's writers and the quarterly repair store one."""
    return {**reported_provenance({"reconciled": True}), "validation": validation, "reasons": list(reasons), **fields}


@pytest.fixture
def locks(monkeypatch):
    """The fact writers' company lock and every row lock a query asks for, by the entity it locks."""
    taken = SimpleNamespace(companies=[], rows=[])
    lock, for_update = facts_service._lock_fact_companies, Query.with_for_update
    monkeypatch.setattr(facts_service, "_lock_fact_companies",
                        lambda session, facts: taken.companies.append([f["company_id"] for f in facts])
                        or lock(session, facts))
    monkeypatch.setattr(Query, "with_for_update",
                        lambda query, *a, **k: taken.rows.append(query.column_descriptions[0]["entity"].__name__)
                        or for_update(query, *a, **k))
    return taken


def test_dry_run_plans_and_writes_nothing(db, locks):
    """A dry run reads and plans, and writes, flushes and locks nothing: the Ops dry run's transactions are
    read-only, where Postgres refuses a write and a FOR UPDATE alike."""
    company, filing = _company(db)
    _margin(db, company, filing)
    db.commit()
    before = _states(db)
    statements = []
    record = lambda c, cu, stmt, *a: statements.append(stmt)  # noqa: E731
    event.listen(db.bind, "before_cursor_execute", record)

    result = repair.backfill_company(db, company.id, apply=False, run_id="dry")

    assert not (db.new or db.dirty or db.deleted), "planning must not touch an ORM object"
    db.rollback()
    event.remove(db.bind, "before_cursor_execute", record)
    assert (result["dry_run"], result["writes"], result["outcomes"]["passed"], result["revisions"]) == (True, 1, 1, 0)
    assert not _writes(statements) and _states(db) == before
    assert db.query(FinancialFactRevision).count() == 0
    assert (locks.companies, locks.rows) == ([], [])


def test_apply_gives_a_filing_owned_legacy_calculation_lineage_and_nothing_else_moves(db, factory):
    """The one row the reader shows as a filing-owned legacy calculation gains the record today's writer
    stores, and ``reconciled`` from it; its value, labels and ``is_latest`` stay. Nothing else moves: not
    a companyfacts-owned legacy margin whose operands would pass, not a tagged margin, not a margin
    that already has a version-1 record, not a reported row. One journal entry holds the row's before."""
    company, filing = _company(db)
    target = _margin(db, company, filing)
    # Not targets: each would be written if it were one, since its operands are stored beside it.
    older = "0000872589-25-000007"
    _row(db, company, "revenue", 800, accession=older, source="companyfacts", end=date(2024, 12, 31), fiscal_year=2024)
    _row(db, company, "net_income", 80, accession=older, source="companyfacts", end=date(2024, 12, 31), fiscal_year=2024)
    _row(db, company, "net_margin", 10.0, accession=older, source="derived", end=date(2024, 12, 31), fiscal_year=2024)
    _row(db, company, "gross_profit", 400, filing=filing)
    _row(db, company, "gross_margin", 40.0, filing=filing, raw_tag="custom:GrossMargin")
    _row(db, company, "net_income", 100, filing=filing)
    _row(db, company, "net_margin", 10.0, filing=filing, provenance={
        **_v1(), "method": "calculated", "formula": METRIC_FORMULAS["net_margin"],
        "checks": {"local_reconciliation": {"reasons": []}},
    })
    _row(db, company, "total_assets", 5000, filing=filing, start=None)
    db.commit()
    before = _states(db)

    result = _apply(db, company)

    assert (result["scanned"], result["writes"], result["revisions"]) == (1, 1, 1)
    assert result["outcomes"] == {"passed": 1, "needs_review": 0}
    assert result["latest_fy"] == {"cleared": 1, "marked": 0, "held": 0}
    with factory() as fresh:
        stored = fresh.get(FinancialFact, target.id)
        assert isinstance(stored.value, Decimal), "read back as production's Numeric column gives it"
        after = {row.id: quarterly_fact_repair.snapshot(row) for row in fresh.query(FinancialFact)}
        journal = fresh.query(FinancialFactRevision).all()
    record = after[target.id]["provenance"]
    assert {key: value for key, value in after[target.id].items() if key not in {"provenance", "reconciled"}} == {
        key: value for key, value in before[target.id].items() if key not in {"provenance", "reconciled"}
    }
    assert after[target.id]["reconciled"] is True and before[target.id]["provenance"] is None
    assert (record["version"], record["method"], record["validation"], record["reasons"]) == (1, "calculated", "passed", [])
    assert record["formula"] == METRIC_FORMULAS["operating_margin"]
    assert record["calculation_version"] == "quarterly-v2" and "checks" not in record
    assert [(item["concept"], item["value"], item["accession"]) for item in record["inputs"]] == [
        ("operating_income", 250.0, filing.accession_number), ("revenue", 1000.0, filing.accession_number),
    ]
    assert {row_id: state for row_id, state in after.items() if row_id != target.id} == {
        row_id: state for row_id, state in before.items() if row_id != target.id
    }
    assert len(journal) == 1
    entry = journal[0]
    assert (entry.fact_id, entry.action, entry.calculation_version, entry.run_id) == (
        target.id, "apply", "lineage-backfill-v1", "run-1")
    assert entry.before_state == before[target.id] and entry.after_state == after[target.id]
    assert len(entry.payload_sha256) == 64


def test_a_recomputed_mismatch_is_written_as_calculation_mismatch_and_unreconciled(db):
    """The figure disagrees with its own accession's operands (a legacy margin computed from the parsed
    revenue before the cross-check replaced it): written as a concern, as today's writer writes it, and
    ``reconciled`` turns false. The value stays."""
    company, filing = _company(db)
    target = _margin(db, company, filing, margin=26.0)
    db.commit()

    result = _apply(db, company)

    db.refresh(target)
    assert (target.provenance["validation"], target.provenance["reasons"]) == ("needs_review", ["calculation_mismatch"])
    assert target.reconciled is False and target.value == Decimal("26")
    assert result["outcomes"] == {"passed": 0, "needs_review": 1} and result["reasons"] == {"calculation_mismatch": 1}
    assert result["latest_fy"] == {"cleared": 0, "marked": 1, "held": 0}
    assert result["revisions"] == 1


def test_latest_fy_counts_the_companys_newest_fiscal_year_alone(db):
    """Every year keeps a current annual row, so ``latest_fy`` counts only the company's newest
    year, the year whose review notes the Multi-Period Analysis baseline counts (77 of 82), and in
    it only the current annual targets: a superseded annual row and a quarter are not counted."""
    company, filing = _company(db)
    _margin(db, company, filing)
    accession = "0000872589-25-000007"
    url = build_sec_archive_url(company.cik, accession)
    prior = Filing(
        company_id=company.id, accession_number=accession, filing_type="10-K",
        filing_date=datetime(2025, 2, 10, tzinfo=timezone.utc), sec_url=url, document_url=f"{url}a.htm",
    )
    db.add(prior)
    db.flush()
    year = {"filing": prior, "end": date(2024, 12, 31), "fiscal_year": 2024}
    _row(db, company, "revenue", 800, start=date(2024, 1, 1), **year)
    _row(db, company, "operating_income", 100, start=date(2024, 1, 1), **year)
    _row(db, company, "operating_margin", 12.5, **year)
    # Each alone in its accession, so each is held for want of operands: counted, it would read as held.
    _row(db, company, "operating_margin", 24.0, filing=filing, accession="0000872589-26-000002", is_latest=False)
    _row(db, company, "operating_margin", 30.0, filing=filing, accession="0000872589-26-000005", fiscal_period="Q4")
    db.commit()

    result = repair.backfill_company(db, company.id, apply=False, run_id="dry")

    assert result["outcomes"] == {"passed": 2, "needs_review": 0} and result["held"]["inputs_not_found"] == 2
    assert result["latest_fy"] == {"cleared": 1, "marked": 0, "held": 0}


@pytest.mark.parametrize("revenue, reason", [
    pytest.param({"reconciled": False}, "source_check_needed", id="legacy-operand-flagged"),
    pytest.param({"provenance": _v1("needs_review", ["magnitude_vs_prior"])}, "magnitude_vs_prior", id="v1-operand-review"),
])
def test_inherited_operand_review_is_written_with_the_operands_reason(db, revenue, reason):
    """An operand under review passes its reason to the calculation: written as a concern with that reason."""
    company, filing = _company(db)
    _row(db, company, "revenue", 1000, filing=filing, **revenue)
    _row(db, company, "operating_income", 250, filing=filing)
    target = _row(db, company, "operating_margin", 25.0, filing=filing)
    db.commit()

    result = _apply(db, company)

    db.refresh(target)
    assert (target.provenance["validation"], target.provenance["reasons"], target.reconciled) == (
        "needs_review", [reason], False)
    assert result["reasons"] == {reason: 1} and result["revisions"] == 1


# Each hold: what the stored rows look like, the hold it counts under, and for an operand the calculator
# cannot find, the cause the report names. Every such cause is the calculator's own verdict.
HOLDS = {
    "duration_unknown": ("inputs_not_found", "duration_unknown"),  # flow operands stored before #831
    "no_operand_row": ("inputs_not_found", "no_operand_row"),
    "ambiguous_operand": ("inputs_not_found", "ambiguous_operand"),  # revenue in two currencies
    "unit_mismatch": ("inputs_not_found", "unit_mismatch"),
    "duration_mismatch": ("inputs_not_found", "duration_mismatch"),
    "target_flagged": ("legacy_flagged", None),
    "operand_unavailable": ("operand_withheld", None),
    "operand_derived": ("operand_legacy_calculation", None),
}


def _seed_hold(db, company, filing, case):
    revenue = {"start": None} if case == "duration_unknown" else {
        "unit": "CNY"} if case == "unit_mismatch" else {"provenance": _v1(
            "unavailable", ["legacy_period_label_mismatch"])} if case == "operand_unavailable" else {
        "source": "derived"} if case == "operand_derived" else {}
    income = {"start": None} if case == "duration_unknown" else {
        "start": date(2025, 7, 1)} if case == "duration_mismatch" else {}
    _row(db, company, "revenue", 1000, filing=filing, **revenue)
    if case == "ambiguous_operand":
        _row(db, company, "revenue", 7000, filing=filing, unit="CNY")
    if case != "no_operand_row":
        _row(db, company, "operating_income", 250, filing=filing, **income)
    return _row(db, company, "operating_margin", 25.0, filing=filing, reconciled=case != "target_flagged")


@pytest.mark.parametrize("case", sorted(HOLDS))
def test_holds_write_nothing(db, case):
    """A held row is counted under its reason and left exactly as it was, ``reconciled`` included: no
    unrecoverable flag is turned true, no shown figure is withheld, absent operands are no evidence
    against the figure, and no version-1 record carries a legacy reason. Where the calculator found no
    operands, the report names why, and the calculator itself said so."""
    company, filing = _company(db)
    target = _seed_hold(db, company, filing, case)
    db.commit()
    before = _states(db)

    result = _apply(db, company)

    hold, label = HOLDS[case]
    assert result["held"] == dict.fromkeys(repair.HOLD_REASONS, 0) | {hold: 1}
    assert (result["writes"], result["revisions"], result["outcomes"]) == (0, 0, {"passed": 0, "needs_review": 0})
    assert result["latest_fy"] == {"cleared": 0, "marked": 0, "held": 1}
    assert _states(db) == before and db.query(FinancialFactRevision).count() == 0
    [entry] = result["rows"]
    assert (entry["fact_id"], entry["outcome"]) == (target.id, hold)
    if label is None:
        assert "diagnostic" not in entry and result["diagnostics"] == dict.fromkeys(repair.DIAGNOSTICS, 0)
    else:
        assert "missing_calculation_inputs" in entry["reasons"] and entry["inputs"] == []
        assert entry["diagnostic"]["label"] == label
        assert result["diagnostics"] == dict.fromkeys(repair.DIAGNOSTICS, 0) | {label: 1}
    if case == "target_flagged":
        assert entry["validation"] == "passed", "the report shows what the row would have had"
    if case == "duration_unknown":
        assert entry["diagnostic"]["inputs"] == [
            {"concept": "operating_income", "rows": 1, "units": ["USD"], "null_start": 1},
            {"concept": "revenue", "rows": 1, "units": ["USD"], "null_start": 1},
        ]


def test_operands_are_any_row_of_the_accession_scope(db):
    """The writer that stored an identity first owns it, so an operand under the filing's accession can be a
    companyfacts row; it counts. A row of the same concept and period under another accession does not."""
    company, filing = _company(db)
    _row(db, company, "revenue", 1000, accession=filing.accession_number, source="companyfacts")
    _row(db, company, "operating_income", 250, filing=filing)
    _row(db, company, "operating_income", 999, accession="0000872589-26-000011", source="companyfacts")
    target = _row(db, company, "operating_margin", 25.0, filing=filing)
    db.commit()

    result = _apply(db, company)

    db.refresh(target)
    assert target.provenance["validation"] == "passed" and result["revisions"] == 1
    assert {(item["concept"], item["value"], item["accession"]) for item in target.provenance["inputs"]} == {
        ("revenue", 1000.0, filing.accession_number), ("operating_income", 250.0, filing.accession_number),
    }


def test_working_capital_and_current_ratio_pass_from_instants(db):
    """Two balance-sheet instants need no start date."""
    company, filing = _company(db)
    _row(db, company, "current_assets", 300, filing=filing, start=None)
    _row(db, company, "current_liabilities", 100, filing=filing, start=None)
    capital = _row(db, company, "working_capital", 200, filing=filing)
    ratio = _row(db, company, "current_ratio", 3.0, filing=filing)
    db.commit()

    result = _apply(db, company)

    db.refresh(capital)
    db.refresh(ratio)
    assert result["outcomes"] == {"passed": 2, "needs_review": 0}
    assert [(row.provenance["validation"], row.reconciled) for row in (capital, ratio)] == [("passed", True)] * 2


def test_raw_tag_equal_to_concept_and_empty_string_are_targets(db):
    """The reader's own legacy condition: no tag, an empty one, or the concept itself; never a tag of its own."""
    company, filing = _company(db)
    _row(db, company, "revenue", 1000, filing=filing)
    _row(db, company, "operating_income", 250, filing=filing)
    _row(db, company, "net_income", 100, filing=filing)
    named = _row(db, company, "operating_margin", 25.0, filing=filing, raw_tag="operating_margin")
    empty = _row(db, company, "net_margin", 10.0, filing=filing, raw_tag="")
    db.commit()

    result = _apply(db, company)

    db.refresh(named)
    db.refresh(empty)
    assert result["revisions"] == 2 and named.provenance["validation"] == empty.provenance["validation"] == "passed"

    def row(**fields):
        return SimpleNamespace(**{"filing_id": 7, "concept": "net_margin", "raw_tag": None, "provenance": None, **fields})

    assert [repair.is_target(row(raw_tag=tag)) for tag in (None, "", "net_margin")] == [True] * 3
    assert [repair.is_target(row(raw_tag=tag)) for tag in ("custom:NetMargin", "NetMargin")] == [False] * 2
    assert repair.is_target(row(provenance={"version": 0})) and not repair.is_target(row(provenance={"version": 1}))
    assert not repair.is_target(row(filing_id=None)) and not repair.is_target(row(concept="revenue"))


def test_a_targets_old_record_is_replaced_not_read(db):
    """A target can carry a record from before version 1. The calculator recomputes the figure from its
    operands and never reads that record, so a reason it lists is not carried into the new one."""
    company, filing = _company(db)
    target = _margin(db, company, filing, provenance={
        "version": 0, "checks": {"local_reconciliation": {"reasons": ["calculation_mismatch"]}},
    })
    db.commit()

    result = _apply(db, company)

    db.refresh(target)
    assert (target.provenance["version"], target.provenance["validation"]) == (1, "passed")
    assert (target.provenance["reasons"], target.reconciled) == ([], True)
    assert result["outcomes"] == {"passed": 1, "needs_review": 0}


def test_rerun_is_idempotent(db):
    """A written row carries a version-1 record and is no longer a target; a held row is counted again."""
    company, filing = _company(db)
    _margin(db, company, filing)
    _row(db, company, "net_income", 100, filing=filing)
    _row(db, company, "net_margin", 10.0, filing=filing, reconciled=False)
    db.commit()

    first = _apply(db, company, run_id="first")
    after = _states(db)
    second = _apply(db, company, run_id="second")

    assert (first["scanned"], first["writes"], first["revisions"]) == (2, 1, 1)
    assert (second["scanned"], second["writes"], second["revisions"]) == (1, 0, 0)
    assert second["held"]["legacy_flagged"] == first["held"]["legacy_flagged"] == 1
    assert _states(db) == after and db.query(FinancialFactRevision).count() == 1


def test_quarterly_rollback_restores_the_backfill_and_refuses_after_a_later_change(db):
    """The audited rollback the other repairs use undoes a company's run whole; once a later write moves a
    backfilled row, it refuses that company rather than overwrite the newer state."""
    company, filing = _company(db)
    target = _margin(db, company, filing)
    db.commit()
    before = _states(db)

    _apply(db, company, run_id="run-1")
    quarterly_fact_repair.rollback_company(db, company.id, "run-1", dry_run=False)
    db.commit()

    assert _states(db) == before
    assert repair.is_target(db.get(FinancialFact, target.id)), "a restored row is a target again"
    _apply(db, company, run_id="run-2")
    db.get(FinancialFact, target.id).is_latest = False  # a newer filing demotes it
    db.commit()
    with pytest.raises(ValueError, match=f"Rollback conflict on fact {target.id}"):
        quarterly_fact_repair.rollback_company(db, company.id, "run-2", dry_run=False)


def test_run_id_reuse_and_a_dirty_session_are_refused(db):
    company, filing = _company(db)
    target = _margin(db, company, filing)
    company_id, target_id = company.id, target.id
    db.add(FinancialFactRevision(run_id="used", company_id=company_id, fact_id=target_id, action="apply",
                                 calculation_version="lineage-backfill-v1", payload_sha256="0" * 64,
                                 after_state={}))
    db.commit()
    before = _states(db)

    with pytest.raises(ValueError, match="Run ID already used"):
        repair.backfill_company(db, company_id, apply=True, run_id="used")
    db.rollback()
    assert _states(db) == before

    # The id is read first: reading an expired attribute loads it, and that load flushes a pending change.
    db.get(FinancialFact, target_id).fiscal_year = 2024
    with pytest.raises(ValueError, match="clean caller-owned transaction"):
        repair.backfill_company(db, company_id, apply=False, run_id="dirty")
    db.rollback()
    assert _states(db) == before


def test_a_company_above_the_rollbacks_bound_is_refused(db, monkeypatch):
    """The backfill's audited undo is the quarterly repair's rollback, which refuses a company holding more
    facts than its bound; so the backfill refuses that company too, dry run and apply alike."""
    company, filing = _company(db)
    _margin(db, company, filing)
    db.commit()
    before = _states(db)
    monkeypatch.setattr(quarterly_fact_repair, "MAX_COMPANY_FACTS", len(before) - 1)

    for apply in (False, True):
        with pytest.raises(ValueError, match=f"exceeds the {len(before) - 1}-fact repair bound"):
            repair.backfill_company(db, company.id, apply=apply, run_id="bounded")
        db.rollback()
    with pytest.raises(ValueError, match=f"exceeds the {len(before) - 1}-fact repair bound"):
        quarterly_fact_repair._rows(db, company.id)
    monkeypatch.setattr(quarterly_fact_repair, "MAX_COMPANY_FACTS", len(before))
    assert repair.backfill_company(db, company.id, apply=False, run_id="bounded")["writes"] == 1
    db.rollback()
    assert _states(db) == before


def test_backfill_matches_todays_writer(db):
    """The record is the one the per-filing writer stores today for the same rows, less its local-gate
    audit (``checks``), which the backfill cannot recover and does not invent."""
    company, filing = _company(db)
    db.commit()

    def point(value, *, start=True, tag=None):
        return {"series": [{"period": END.isoformat(), "value": value, "form": "10-K",
                            **({"period_start": START.isoformat()} if start else {}),
                            **({"raw_tag": tag} if tag else {})}]}

    facts_service.process_filing_facts(db, filing, standardized={
        "revenue": point(6557.6e6, tag="us-gaap:Revenues"),
        "operating_income": point(1234.5e6, tag="us-gaap:OperatingIncomeLoss"),
        "operating_margin": point(1234.5e6 / 6557.6e6 * 100, start=False),
        "current_assets": point(300.0, start=False, tag="us-gaap:AssetsCurrent"),
        "current_liabilities": point(120.0, start=False, tag="us-gaap:LiabilitiesCurrent"),
        "current_ratio": point(2.5, start=False),
    })
    calculated = db.query(FinancialFact).filter(FinancialFact.concept.in_(sorted(METRIC_FORMULAS))).all()
    written = {row.id: dict(row.provenance) for row in calculated}
    assert {record["validation"] for record in written.values()} == {"passed"} and "checks" in written[calculated[0].id]
    for row in calculated:
        row.provenance = None  # as stored before #1191
    db.commit()

    result = _apply(db, company)

    assert result["revisions"] == 2
    db.expire_all()
    assert {row.id: row.provenance for row in calculated} == {
        row_id: {key: value for key, value in record.items() if key != "checks"} for row_id, record in written.items()
    }


def test_after_apply_the_dataset_point_passes(db):
    """Multi-Period Analysis reads the record: the point passes and the data notes raise nothing for it,
    where before it read as a legacy calculation."""
    company, filing = _company(db)
    target = _margin(db, company, filing)
    db.commit()

    def notes():
        db.expire_all()
        point = dataset_point(db.get(FinancialFact, target.id), "FY2025", None)
        dataset = {"mode": "annual", "periods": [{"key": "FY2025"}], "period_key": "FY2025",
                   "series": [{"concept": "operating_margin", "label": "Operating margin", "points": [point]}]}
        return point, data_notes(dataset)["notes"]

    point, before = notes()
    assert point["provenance"]["reasons"] == ["legacy_calculation"]
    assert [note["reasons"] for note in before] == [["legacy_calculation"]]

    _apply(db, company)

    point, after = notes()
    assert (point["provenance"]["validation"], point["reconciled"], point["value"]) == ("passed", True, 25.0)
    assert after == []


# ---------------------------------------------------------------------------------------------- the CLI


def _cohort(db):
    regn, regn_filing = _company(db)
    _margin(db, regn, regn_filing)
    _row(db, regn, "net_margin", 10.0, filing=regn_filing)  # held: its accession stores no net income
    aapl, aapl_filing = _company(db, "AAPL", "0000320193")
    _margin(db, aapl, aapl_filing, margin=26.0)
    bare, _filing = _company(db, "BARE", "0000000999")  # no filing-owned formula row
    _row(db, bare, "revenue", 1, filing=_filing)
    db.commit()
    return regn, aapl, bare


def test_cli_dry_run_is_the_default_takes_no_lock_and_scopes_by_ticker_and_limit(db, factory, capsys, locks, monkeypatch):
    regn, aapl, _bare = _cohort(db)
    before = _states(db)
    statements = []
    record = lambda c, cu, stmt, *a: statements.append(stmt)  # noqa: E731
    event.listen(db.bind, "before_cursor_execute", record)
    opened = SimpleNamespace(now=0, most=0)

    class Counted(Session):  # every session the CLI opens, to show it never holds two at once
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.counted = True
            opened.now += 1
            opened.most = max(opened.most, opened.now)

        def close(self):
            if getattr(self, "counted", False):
                self.counted = False
                opened.now -= 1
            super().close()

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=db.bind, expire_on_commit=False, class_=Counted))

    def run(argv):
        code = cli.main(argv)
        return code, [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    code, (start, *companies, summary) = run([])
    assert code == 0 and not _writes(statements) and _states(db) == before
    assert (locks.companies, locks.rows) == ([], [])
    assert (opened.now, opened.most) == (0, 1), "the cohort's session closes before each company's opens"
    assert start == {"started": True, "run_id": summary["run_id"], "dry_run": True, "tickers": None}
    assert [(line["ticker"], line["writes"], line["run_id"]) for line in companies] == [
        ("REGN", 1, start["run_id"]), ("AAPL", 1, start["run_id"])]
    no_holds = dict.fromkeys(repair.HOLD_REASONS, 0)
    no_diagnostics = dict.fromkeys(repair.DIAGNOSTICS, 0)
    assert {key: summary[key] for key in ("companies", "companies_with_writes", "scanned", "writes", "revisions",
                                          "outcomes", "reasons", "held", "diagnostics", "latest_fy",
                                          "failed")} == {
        "companies": 2, "companies_with_writes": 2, "scanned": 3, "writes": 2, "revisions": 0,
        "outcomes": {"passed": 1, "needs_review": 1}, "reasons": {"calculation_mismatch": 1},
        "held": {**no_holds, "inputs_not_found": 1}, "diagnostics": {**no_diagnostics, "no_operand_row": 1},
        "latest_fy": {"cleared": 1, "marked": 1, "held": 1}, "failed": 0,
    }
    code, lines = run(["--limit", "1"])
    assert code == 0 and [line.get("ticker") for line in lines] == [None, "REGN", None]
    code, lines = run(["--tickers", "bare,aapl"])  # a named company is reported even with nothing to scan
    assert code == 0 and lines[0]["tickers"] == ["AAPL", "BARE"]
    assert [(line["ticker"], line["scanned"]) for line in lines[1:-1]] == [("AAPL", 1), ("BARE", 0)]
    code, lines = run(["--tickers", "REGN,NOPE"])
    assert code == 1 and lines == [{"failed": 1, "error": "Unknown tickers ['NOPE']; no company processed"}]
    code, lines = run(["--limit", "0"])
    assert code == 1 and lines == [{"failed": 1, "error": "--limit must be at least 1"}]
    assert not _writes(statements) and _states(db) == before
    event.remove(db.bind, "before_cursor_execute", record)

    code, lines = run(["--apply", "--tickers", "REGN"])

    assert code == 0 and not lines[-1]["dry_run"] and lines[-1]["revisions"] == 1
    assert locks.companies == [[regn.id]]
    assert locks.rows == ["Company", "FinancialFact", "FinancialFact"], "the company, the targets, the rows read"
    with factory() as fresh:  # committed: a new session sees the record and the journal
        assert fresh.query(FinancialFactRevision).filter_by(run_id=lines[0]["run_id"], company_id=regn.id).count() == 1
        assert fresh.query(FinancialFactRevision).filter_by(company_id=aapl.id).count() == 0


class _Stdout:
    """A stdout that tells what was flushed from what is still buffered."""

    def __init__(self):
        self.flushed, self.pending = "", ""

    def write(self, text):
        self.pending += text
        return len(text)

    def flush(self):
        self.flushed, self.pending = self.flushed + self.pending, ""


def test_cli_prints_its_run_id_before_any_company(db, monkeypatch):
    """Each company commits as it goes, so the run's first line, flushed before any company, names the
    run_id an apply cut short has journaled its committed companies under."""
    _cohort(db)
    seen, out = [], _Stdout()

    def interrupted(session, company_id, **kwargs):
        seen.append((out.flushed, out.pending))
        raise KeyboardInterrupt  # what a cancel or the step's timeout raises in the script

    monkeypatch.setattr(repair, "backfill_company", interrupted)
    monkeypatch.setattr(sys, "stdout", out)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["--apply"])
    assert len(seen) == 1
    before_any_company, buffered = seen[0]
    assert buffered == "" and before_any_company.count("\n") == 1, "one start line, flushed before any company"
    start = json.loads(before_any_company)
    assert start == {"started": True, "run_id": start["run_id"], "dry_run": False, "tickers": None}


def test_a_failing_company_rolls_back_alone_and_fails_the_exit_code(db, factory, capsys, monkeypatch):
    regn, aapl, _bare = _cohort(db)
    before = _states(db)
    plan = repair.backfill_company

    def failing_for_regn(session, company_id, **kwargs):
        result = plan(session, company_id, **kwargs)  # its records are flushed before it fails
        if company_id == regn.id:
            raise RuntimeError("simulated failure")
        return result

    monkeypatch.setattr(repair, "backfill_company", failing_for_regn)

    assert cli.main(["--apply"]) == 1

    _start, *lines, summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0] == {"company_id": regn.id, "ticker": "REGN", "error": "simulated failure"}
    assert lines[1]["ticker"] == "AAPL" and lines[1]["revisions"] == 1
    assert (summary["failed"], summary["companies"], summary["revisions"]) == (1, 2, 1)
    with factory() as fresh:
        states = {row.id: quarterly_fact_repair.snapshot(row) for row in fresh.query(FinancialFact)}
        assert {k: v for k, v in states.items() if v["company_id"] == regn.id} == {
            k: v for k, v in before.items() if v["company_id"] == regn.id
        }
        assert {r.company_id for r in fresh.query(FinancialFactRevision)} == {aapl.id}


def test_one_apply_journals_every_company_under_its_run_id(db, factory, capsys):
    """The CLI journals a whole apply under one run_id, so the reuse check refuses a run_id only where
    this company already holds it: the founder's "then the rest in one apply" writes every company."""
    regn, aapl, _bare = _cohort(db)

    assert cli.main(["--apply"]) == 0

    start, *lines, summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(line["ticker"], line["revisions"]) for line in lines] == [("REGN", 1), ("AAPL", 1)]
    assert (summary["failed"], summary["revisions"]) == (0, 2)
    with factory() as fresh:
        journal = fresh.query(FinancialFactRevision).filter_by(run_id=start["run_id"])
        assert sorted(entry.company_id for entry in journal) == sorted([regn.id, aapl.id])
