"""Presentation-only narrative format, exact evidence and cache/PDF compatibility."""
from copy import deepcopy
from datetime import date
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.trend_analysis.cache import NARRATIVE_FORMAT_VERSION
from app.services.trend_analysis.data_notes import data_notes
from app.services.trend_analysis.dataset import dataset_fingerprint, marker_index
from app.services.trend_analysis.fidelity import scan_numeric_fidelity
from app.services.trend_analysis.narrative_display import compact_narrative_text, currency_precision_plan
from app.services.trend_analysis.observations import (
    ANALYSIS_SECTIONS, build_observation_catalogue, compact_observation_catalogue,
    render_observation_selection,
)
from app.services.trend_analysis.presentation import (
    presentation_is_current, render_narrative_presentation,
)


def _dataset():
    periods = ["2026Q1", "2026Q2"]
    series = []
    specifications = [
        ("revenue", "Revenue 🧾", "USD", False, (1_500_000_000, 1_600_000_000)),
        ("net_income", "Net income", "USD", False, (1_002_000_000, 1_004_000_000)),
        ("free_cash_flow", "Free cash flow", "USD", False, (1_003_000_000, 1_001_000_000)),
        ("current_ratio", "Current ratio", "pure", False, (1.01, 1.00004)),
        ("operating_margin", "Operating margin", "pure", True, (28.73456254321, 26.06536076709265)),
        ("earnings_per_share", "EPS (basic)", "EUR/shares", False, (1.15, 1.23)),
    ]
    for concept, label, unit, percent, values in specifications:
        points = [{"period": period, "value": value, "marker": f"F{len(series) * 2 + i + 1}",
                   "unit": unit, "period_end": "2026-03-31" if i == 0 else "2026-06-30",
                   "derived": False, "raw_tag": f"us-gaap:{concept}", "reconciled": True,
                   "provenance": {"method": "reported", "validation": "passed", "reasons": [], "inputs": []}}
                  for i, (period, value) in enumerate(zip(periods, values))]
        series.append({"concept": concept, "label": label, "unit": unit, "percent": percent,
                       "points": points, "cagr": None})
    series[4]["points"][1]["provenance"] = {
        "method": "calculated", "validation": "needs_review", "reasons": ["legacy_calculation"],
        "formula": "100 * operating_income / revenue", "inputs": [],
    }
    dataset = {
        "ticker": "TST", "company_name": "Presentation Co", "dataset_version": "quarterly-v2",
        "mode": "quarterly", "period_key": "2026Q1..2026Q2",
        "periods": [{"key": period} for period in periods], "series": series,
        "inflections": [{"kind": "fcf_ni_divergence", "detail": "Cash trails earnings.",
                         "markers": ["F6", "F4", "F10"]}],
    }
    dataset["data_notes"] = data_notes(dataset)
    dataset["snapshot_id"] = dataset_fingerprint(dataset)
    return dataset


def _render(dataset):
    catalogue = build_observation_catalogue(dataset)
    selection = {section: [] for section, _ in ANALYSIS_SECTIONS}
    return render_narrative_presentation(dataset, catalogue, selection, marker_index(dataset))


def test_selected_narrative_is_compact_but_evidence_and_selector_inputs_remain_exact():
    dataset = _dataset()
    original = deepcopy(dataset)
    catalogue = build_observation_catalogue(dataset)
    selector_text = compact_observation_catalogue(catalogue)
    text, citations, grounded, unverified, presentation = _render(dataset)

    assert "$1.6B in Q2 2026" in text
    assert "USD 1,001,000,000" in text and "USD 1,004,000,000" in text
    assert "1.00004× in Q2 2026" in text and "above 1.00×" in text
    assert unverified == 0 and grounded == len(citations)
    assert scan_numeric_fidelity(text, citations, marker_index(dataset)) == []
    assert dataset == original
    assert compact_observation_catalogue(catalogue) == selector_text
    assert "USD 1,600,000,000 in 2026Q2" in selector_text
    assert "USD 1,600,000,000 in 2026Q2" in render_observation_selection(
        catalogue, {section: [] for section, _ in ANALYSIS_SECTIONS},
    )
    assert presentation["format_version"] == NARRATIVE_FORMAT_VERSION
    assert presentation["snapshot_id"] == dataset["snapshot_id"]
    assert presentation["notes"] == dataset["data_notes"]
    evidence, = presentation["evidence"]
    tail = evidence["tail"]
    encoded = text.encode("utf-16-le")
    assert encoded[tail["start"] * 2:tail["end"] * 2].decode("utf-16-le") == tail["text"]
    assert tail["start"] > text.index(tail["text"])  # supplementary Unicode before the tail
    assert tail["text"].startswith(" Source operands: ") and tail["text"].endswith(".")
    assert evidence["observation_id"] == "red_flags.signal.fcf-ni-divergence.1"
    assert [operand["value"] for operand in evidence["operands"]] == [1_001_000_000, 1_004_000_000, 26.06536076709265]
    assert [operand["display_value"] for operand in evidence["operands"]] == [
        "USD 1,001,000,000", "USD 1,004,000,000", "26.1%",
    ]
    for operand in evidence["operands"]:
        citation = next(c for c in citations if c["n"] == operand["citation_id"])
        assert all(operand[key] == citation[key] for key in ("marker", "concept", "value", "unit", "percent", "period", "derived", "provenance"))
    assert evidence["operands"][-1]["provenance"]["reasons"] == ["legacy_calculation"]
    assert evidence["operands"][-1]["provenance"]["inputs"] == []


def test_citation_units_distinguish_growth_fractions_percentage_levels_and_currency():
    dataset = _dataset()
    dataset["series"][0].update(cagr=0.134, cagr_marker="F20", cagr_window="FY2020..FY2024")
    _, citations, _, _, _ = _render(dataset)
    assert next(c for c in citations if c["marker"] == "F20")["unit"] == "growth fraction"
    assert next(c for c in citations if c["marker"] == "F10")["unit"] == "percent"
    assert next(c for c in citations if c["marker"] == "F2")["unit"] == "USD"
    assert next(c for c in citations if c["marker"] == "F20")["value"] == 0.134


def test_display_precision_plan_survives_markdown_splits_and_per_share_collisions():
    original = "USD 1,001,000,000 [1] was below **USD 1,004,000,000** [2]. EUR 1.001 per share and EUR 1.004 per share."
    plan = currency_precision_plan(original)
    assert compact_narrative_text("USD 1,001,000,000", plan) == "USD 1,001,000,000"
    assert compact_narrative_text("USD 1,004,000,000", plan) == "USD 1,004,000,000"
    assert compact_narrative_text(original, plan) == original
    assert compact_narrative_text("USD -71,900,000,000 in 2026Q2; EUR 6.25 per share") == "-$71.9B in Q2 2026; EUR\u00a06.25 per share"
    assert compact_narrative_text("0.99996x below 1.00x") == "0.99996× below 1.00×"


@pytest.mark.parametrize(("currency", "value", "compact"), [
    ("EUR", 1_600_000_000, "1.6B"), ("GBP", 23_400_000, "23.4M"),
])
def test_non_usd_display_is_safe_in_older_tabs_and_retains_numeric_fidelity(currency, value, compact):
    # Phase 1 tabs still run this ASCII-space regex without inspecting the new envelope.
    # With an ASCII prefix it backtracks into the integer part of a scaled decimal token.
    legacy_currency = re.compile(r"\b([A-Z]{3}) (-?\d[\d,]*(?:\.\d+)?)( per share)?\b")
    assert legacy_currency.search(f"{currency} {compact}") is not None
    rendered = compact_narrative_text(f"Revenue was {currency} {value:,} in 2026Q2 [1].")
    assert rendered == f"Revenue was {currency}\u00a0{compact} in Q2 2026 [1]."
    assert legacy_currency.search(rendered) is None
    assert compact_narrative_text(rendered) == rendered
    point = {"concept": "revenue", "period": "2026Q2", "value": value,
             "unit": currency, "percent": False}
    citations = [{"n": 1, **point}]
    assert scan_numeric_fidelity(rendered, citations, {"F1": point}) == []
    assert scan_numeric_fidelity(rendered.replace(compact, "9.9T"), citations, {"F1": point}) == [1]


def test_compact_fidelity_still_rejects_wrong_values_scales_and_citations():
    dataset = _dataset()
    text, citations, _, _, _ = _render(dataset)
    assert scan_numeric_fidelity(text.replace("$1.6B", "$9.6B"), citations, marker_index(dataset))
    assert scan_numeric_fidelity(text.replace("$1.6B", "$1.6M"), citations, marker_index(dataset))
    revenue_id = next(c["n"] for c in citations if c["marker"] == "F2")
    wrong_id = next(c["n"] for c in citations if c["marker"] == "F4")
    assert scan_numeric_fidelity(f"Revenue was $1.6B [{wrong_id}].", citations, marker_index(dataset)) == [wrong_id]
    assert scan_numeric_fidelity(f"Revenue was $1.6B [{revenue_id}].", citations, marker_index(dataset)) == []


@pytest.fixture
def narrative_company(tmp_path, monkeypatch):
    from app import database
    from app.models import Base, Company, FinancialFact

    engine = create_engine(f"sqlite:///{tmp_path / 'presentation.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    with factory() as db:
        company = Company(cik="0000909876", ticker="PRES", name="Presentation Co")
        db.add(company)
        db.flush()
        for year, revenue, income in [(2021, 1_000_000_000, 100_000_000), (2022, 1_200_000_000, 130_000_000), (2023, 1_500_000_000, 180_000_000)]:
            for concept, value in (("revenue", revenue), ("net_income", income)):
                db.add(FinancialFact(company_id=company.id, concept=concept, raw_tag=f"us-gaap:{concept}",
                                     unit="USD", period_start=date(year, 1, 1), period_end=date(year, 12, 31),
                                     fiscal_year=year, fiscal_period="FY", value=value, form="10-K",
                                     accession=f"0000909876-{year % 100}-000001", source="companyfacts",
                                     reconciled=True, is_latest=True))
        db.commit()
        identifier = company.id
    yield identifier, factory
    engine.dispose()


async def _drain(identifier, monkeypatch, *, force=False):
    from app.services.openai_service import openai_service
    from app.services.trend_analysis.narrative import stream_trend_narrative

    calls = []

    async def fake(messages, **kwargs):
        calls.append(deepcopy(messages))
        kwargs["usage_sink"].update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        yield json.dumps({section: [] for section, _ in ANALYSIS_SECTIONS})

    monkeypatch.setattr(openai_service, "stream_chat", fake)
    events = [event async for event in stream_trend_narrative(
        company_id=identifier, mode="annual", start_period="FY2021", end_period="FY2023", force=force,
    )]
    return events, calls


@pytest.mark.asyncio
async def test_fresh_cached_and_saved_presentation_are_identical(narrative_company, monkeypatch):
    from app.models import TrendAnalysis

    identifier, factory = narrative_company
    fresh_events, fresh_calls = await _drain(identifier, monkeypatch)
    cached_events, cached_calls = await _drain(identifier, monkeypatch)
    fresh, cached = fresh_events[-1], cached_events[-1]
    assert fresh["type"] == cached["type"] == "complete"
    assert fresh["cached"] is False and cached["cached"] is True
    assert len(fresh_calls) == 1 and cached_calls == []
    assert fresh["narrative_presentation"] == cached["narrative_presentation"]
    assert fresh["narrative"] == cached["narrative"] and fresh["citations"] == cached["citations"]
    assert "".join(e["text"] for e in fresh_events if e["type"] == "token") == fresh["narrative"]
    with factory() as db:
        saved = db.query(TrendAnalysis).one()
        assert saved.dataset_json["narrative_presentation"] == fresh["narrative_presentation"]
        assert presentation_is_current(saved.dataset_json)
        assert saved.dataset_fingerprint == dataset_fingerprint(saved.dataset_json)


@pytest.mark.asyncio
@pytest.mark.parametrize("obsolete", ["absent", "format", "notes", "snapshot"])
async def test_old_presentation_lazily_regenerates_as_system_invalidated(narrative_company, monkeypatch, obsolete):
    from app.models import TrendAnalysis

    identifier, factory = narrative_company
    fresh = (await _drain(identifier, monkeypatch))[0][-1]
    with factory() as db:
        row = db.query(TrendAnalysis).one()
        saved = deepcopy(row.dataset_json)
        if obsolete == "absent":
            saved.pop("narrative_presentation")
        elif obsolete == "format":
            saved["narrative_presentation"]["format_version"] = "retired"
        elif obsolete == "notes":
            saved["narrative_presentation"]["data_notes_version"] = 0
        else:
            saved["narrative_presentation"]["snapshot_id"] = "0" * 64
        row.dataset_json = saved
        db.commit()
    events, calls = await _drain(identifier, monkeypatch)
    regenerated = events[-1]
    assert len(calls) == 1 and regenerated["cached"] is False and regenerated["invalidated"] is True
    assert regenerated["analysis_id"] == fresh["analysis_id"]
    assert regenerated["narrative_presentation"] == fresh["narrative_presentation"]
    assert regenerated["snapshot_id"] == fresh["snapshot_id"]


@pytest.mark.asyncio
async def test_persistence_failure_does_not_drop_the_display_or_evidence(narrative_company, monkeypatch):
    from app.services.trend_analysis import narrative

    monkeypatch.setattr(narrative, "_persist_analysis", lambda **kwargs: None)
    events, calls = await _drain(narrative_company[0], monkeypatch)
    complete = events[-1]
    assert len(calls) == 1 and complete["type"] == "complete" and complete["analysis_id"] is None
    assert complete["narrative_presentation"]["format_version"] == NARRATIVE_FORMAT_VERSION
    assert complete["narrative_presentation"]["snapshot_id"] == complete["snapshot_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("obsolete", [None, "absent", "format", "notes", "snapshot", "boolean_notes", "malformed_evidence"])
async def test_pdf_uses_the_same_presentation_admission_as_cache(monkeypatch, obsolete):
    from fastapi import HTTPException
    from app.models import TrendAnalysis
    from app.routers import analysis as router
    from app.services import entitlements
    from app.services.export_service import export_service
    from app.services.trend_analysis.cache import PROMPT_VERSION

    dataset = _dataset()
    text, citations, grounded, _, presentation = _render(dataset)
    dataset["narrative_presentation"] = presentation
    if obsolete == "absent":
        dataset.pop("narrative_presentation")
    elif obsolete == "format":
        presentation["format_version"] = "retired"
    elif obsolete == "notes":
        presentation["notes"]["version"] = 0
    elif obsolete == "snapshot":
        presentation["snapshot_id"] = "0" * 64
    elif obsolete == "boolean_notes":
        presentation["data_notes_version"] = True
    elif obsolete == "malformed_evidence":
        presentation["evidence"] = None
    record = SimpleNamespace(dataset_json=dataset, narrative_md=text, citations_json=citations,
                             grounded=grounded, unverified=0, company_id=1, mode="quarterly",
                             period_key=dataset["period_key"], dataset_fingerprint=dataset["snapshot_id"],
                             prompt_version=PROMPT_VERSION)
    db = SimpleNamespace(get=lambda model, identifier: record if model is TrendAnalysis else SimpleNamespace(ticker="TST"))
    monkeypatch.setattr(entitlements, "get_entitlements", lambda _: SimpleNamespace(can_export=True))
    monkeypatch.setattr(router.trend_analysis_service, "build_dataset", lambda *args: _dataset())
    render = AsyncMock(return_value=b"%PDF-presentation")
    monkeypatch.setattr(export_service, "export_analysis_pdf", render)
    assert presentation_is_current(dataset) is (obsolete is None)
    if obsolete:
        with pytest.raises(HTTPException) as error:
            await router.export_analysis_pdf(1, snapshot_id=dataset["snapshot_id"], current_user=SimpleNamespace(), db=db)
        assert error.value.status_code == 409 and "presentation format" in error.value.detail
        render.assert_not_awaited()
    else:
        result = await router.export_analysis_pdf(1, snapshot_id=dataset["snapshot_id"], current_user=SimpleNamespace(), db=db)
        assert result.body == b"%PDF-presentation"
        render.assert_awaited_once()
