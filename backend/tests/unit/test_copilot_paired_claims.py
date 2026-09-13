"""Retained ASML answer through normalization, isolated persistence and real tool resolution."""
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


async def complete(monkeypatch, tmp_path, *, changes=None, answer=ANSWER, row_changes=None):
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
        yield answer  # model made no tool calls in all three retained ASML draws

    monkeypatch.setattr(service.openai_service, "stream_chat_with_tools", stream)
    original_resolve = service._resolve_citations
    registrations = []

    def resolve(answer, text_citations, used_facts, filing_url):
        registrations.extend(used_facts)
        return original_resolve(answer, text_citations, used_facts, filing_url)

    monkeypatch.setattr(service, "_resolve_citations", resolve)
    view = filing(accession_number=ACC, period_of_report="2025-12-31", xbrl_data=points)
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
