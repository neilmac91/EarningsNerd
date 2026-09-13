"""Retained ASML answer through normalization, isolated persistence and real tool resolution."""
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.models.financial_fact import FinancialFact
from app.services import copilot_service as service
from app.services.edgar.xbrl_service import EdgarXBRLService
from app.services.facts_service import normalize_standardized_to_facts
from tests.unit.test_copilot_citation_repair import filing

ACC = "0001628280-26-011378"
ANSWER = ("Total net sales for the year ended December 31, 2025 were €32,667.3 million, "
          "and net income was €9,609.4 million.")


async def complete(monkeypatch, tmp_path, *, changes=None, answer=ANSWER, row_changes=None, source=None, call_revenue=False):
    # Exact current points from retained PR833 third Copilot input; net income has no raw tag.
    points = {
        "revenue": [{"period": "2025-12-31", "value": 32667300000.0, "form": "20-F",
                     "accn": ACC, "currency": "EUR", "period_start": "2025-01-01",
                     "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"}],
        "net_income": [{"period": "2025-12-31", "value": 9609400000.0, "form": "20-F",
                        "accn": ACC, "currency": "EUR", "period_start": "2025-01-01"}],
    }
    if changes:
        points["net_income"][0].update(changes)
    standardized = EdgarXBRLService.__new__(EdgarXBRLService).extract_standardized_metrics(points)
    rows = normalize_standardized_to_facts(9, 7, ACC, "20-F", standardized)
    if row_changes:
        for row in rows:
            if row["concept"] == "net_income":
                row.update(row_changes)
    engine = create_engine(f"sqlite:///{tmp_path / 'facts.db'}")
    FinancialFact.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([FinancialFact(**row) for row in rows])
        db.commit()
    monkeypatch.setattr(service.copilot_tools, "SessionLocal", sessions)

    async def stream(*args, **kwargs):
        if call_revenue:
            args[2]("get_financial_fact", {"concept": "revenue"})
        yield answer  # model made no tool calls in all three retained ASML draws

    monkeypatch.setattr(service.openai_service, "stream_chat_with_tools", stream)
    original_resolve = service._resolve_citations
    registrations = []

    def resolve(answer, text_citations, used_facts, filing_url):
        registrations.extend(used_facts)
        return original_resolve(answer, text_citations, used_facts, filing_url)

    monkeypatch.setattr(service, "_resolve_citations", resolve)
    view = filing(accession_number=ACC, period_of_report="2025-12-31",
                  period_end_date=datetime(2025, 12, 31), xbrl_data=points)
    if source is not None:
        view.content_cache.critical_excerpt = source
    view = service.snapshot_filing(view)
    try:
        events = [event async for event in service.answer_filing_question(filing=view, question="Annual sales and income?")]
        result = next(event for event in events if event["type"] == "complete")
        result["registered_markers"] = registrations
        return result
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_retained_pair_has_two_distinct_grounded_chips(monkeypatch, tmp_path):
    result = await complete(monkeypatch, tmp_path)
    assert result["grounded"] == 2
    assert result["answer"] == ANSWER.replace("million,", "million [1],").replace("million.", "million [2].")
    assert result["uncited_figures"] == 0 and result["misplaced_fact_markers"] == 0
    assert [c["concept"] for c in result["citations"]] == ["revenue", "net_income"]
    assert [c["value"] for c in result["citations"]] == [32667300000.0, 9609400000.0]
    for citation in result["citations"]:
        assert (citation["accession"], citation["unit"], citation["period_start"], citation["period_end"]) == (
            ACC, "EUR", "2025-01-01", "2025-12-31")
    assert result["citations"][1]["raw_tag"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"period_start": None}, {"period_start": "2025-10-01"},
    {"period_start": "2024-12-30"}, {"period": "2024-12-31"},
    {"currency": "USD"}, {"value": -9609400000.0}, {"value": 9608400000.0},
])
async def test_pair_abstains_without_registering_either_operand(monkeypatch, tmp_path, changes):
    result = await complete(monkeypatch, tmp_path, changes=changes)
    assert result["answer"] == ANSWER
    assert result["citations"] == [] and result["registered_markers"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("row_changes", [
    {"accession": "0000950170-25-090161"}, {"concept": "operating_income"},
    {"fiscal_period": "Q4"},
])
async def test_wrong_fact_identity_never_certifies_pair(monkeypatch, tmp_path, row_changes):
    result = await complete(monkeypatch, tmp_path, row_changes=row_changes)
    assert result["answer"] == ANSWER and result["registered_markers"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [
    ANSWER + " Growth accelerated.", ANSWER.replace("net income", "adjusted net income"),
    ANSWER.replace("Total net sales", "Cloud net sales"),
    ANSWER.replace("million,", "million [1],"),
    ANSWER.replace("was €9", "was $9"),
    ANSWER.replace("and net income was", "and net income for 2024 was"),
])
async def test_unsupported_pair_never_adds_a_fact_marker(monkeypatch, tmp_path, answer):
    result = await complete(monkeypatch, tmp_path, answer=answer)
    assert result["registered_markers"] == [] and result["citations"] == []


UNRESOLVED_PAIR = ANSWER.replace("million,", "million [F81],").replace("million.", "million [F82].")


@pytest.mark.asyncio
async def test_final_visible_pair_repairs_after_unresolved_markers(monkeypatch, tmp_path):
    result = await complete(monkeypatch, tmp_path, answer=UNRESOLVED_PAIR)
    assert result["answer"] == ANSWER.replace("million,", "million [1],").replace("million.", "million [2].")
    assert result["grounded"] == 2 and result["uncited_figures"] == 0
    assert result["misplaced_fact_markers"] == 0
    assert [c["concept"] for c in result["citations"]] == ["revenue", "net_income"]


@pytest.mark.asyncio
async def test_final_visible_pair_missing_operand_still_abstains(monkeypatch, tmp_path):
    result = await complete(monkeypatch, tmp_path, answer=UNRESOLVED_PAIR, changes={"period_start": None})
    assert result["answer"] == ANSWER
    assert result["citations"] == [] and result["registered_markers"] == []


@pytest.mark.asyncio
async def test_existing_verified_text_citation_survives_without_repair(monkeypatch, tmp_path):
    source = "Total net sales for the year ended December 31, 2025 were €32,667.3 million."
    answer = ANSWER.replace("million,", "million [1],")
    payload = answer + '\n===CITATIONS===\n' + '[{"n": 1, "excerpt": "' + source + '", "section": "Financial statements"}]'
    result = await complete(monkeypatch, tmp_path, answer=payload, source=source)
    assert result["answer"] == answer and len(result["citations"]) == 1
    assert result["citations"][0]["verified"] is True
    assert result["registered_markers"] == []


@pytest.mark.asyncio
async def test_surviving_fact_citation_is_not_reinterpreted(monkeypatch, tmp_path):
    answer = ANSWER.replace("million,", "million [F1],").replace("million.", "million [F88].")
    result = await complete(monkeypatch, tmp_path, answer=answer, call_revenue=True)
    assert result["answer"] == ANSWER.replace("million,", "million [1],")
    assert len(result["citations"]) == 1 and result["citations"][0]["concept"] == "revenue"


@pytest.mark.asyncio
async def test_repair_preserves_original_misplacement_telemetry(monkeypatch, tmp_path):
    answer = ANSWER.replace("million.", "million [F1].")
    result = await complete(monkeypatch, tmp_path, answer=answer, call_revenue=True)
    assert result["answer"] == ANSWER.replace("million,", "million [1],").replace("million.", "million [2].")
    assert result["misplaced_fact_markers"] == 1
    assert result["grounded"] == 2 and result["uncited_figures"] == 0
