"""Unit tests for the Multi-Period Analysis narrative pipeline (M3).

The model is faked (monkeypatched ``openai_service.stream_chat``, the ``test_copilot`` pattern):
these tests pin the event contract, marker→citation resolution, the D4 cache semantics
(cached re-serve / force / fingerprint invalidation), and the route's meter-on-fresh-complete rule.
"""

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import trend_analysis_service as svc
from app.services.openai_service import STREAM_ERROR_SENTINEL


class TestResolveNarrativeCitations:
    INDEX = {
        "F1": {"concept": "revenue", "label": "Revenue", "unit": "USD", "percent": False,
               "value": 1000.0, "period": "FY2022", "raw_tag": "us-gaap:Revenues"},
        "F2": {"concept": "net_income", "label": "Net income", "unit": "USD", "percent": False,
               "value": 200.0, "period": "FY2022", "raw_tag": None},
    }

    def test_renumbers_in_first_appearance_order(self):
        text = "Net income was 200 [F2] on revenue of 1,000 [F1]. Revenue again [F1]."
        final, citations, grounded = svc.resolve_narrative_citations(text, self.INDEX)
        assert "[1]" in final and "[2]" in final and "[F" not in final
        assert final.count("[1]") == 1  # F2 → 1 (first appearance)
        assert final.count("[2]") == 2  # F1 reused
        assert [c["n"] for c in citations] == [1, 2]
        assert citations[0]["concept"] == "net_income"
        assert citations[1]["section_ref"] == "XBRL · us-gaap:Revenues"
        assert grounded == 2

    def test_unknown_marker_stripped_swallowing_space(self):
        final, citations, grounded = svc.resolve_narrative_citations(
            "Margins expanded [F99], notably.", self.INDEX
        )
        assert final == "Margins expanded, notably."
        assert citations == []
        assert grounded == 0

    def test_marker_whitespace_and_case_tolerated(self):
        final, citations, _ = svc.resolve_narrative_citations("Revenue [f 1] grew.", self.INDEX)
        assert final == "Revenue [1] grew."
        assert citations[0]["concept"] == "revenue"


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _seed_company_with_history():
    from app.database import SessionLocal
    from app.models import Company, FinancialFact

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=suffix, ticker=("S" + suffix[:4]).upper(), name=f"Stream Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    for fy, revenue, net_income in [(2021, 1000.0, 100.0), (2022, 1200.0, 130.0), (2023, 1500.0, 180.0)]:
        for concept, value in (("revenue", revenue), ("net_income", net_income)):
            db.add(FinancialFact(
                company_id=company.id, filing_id=None, concept=concept,
                raw_tag=f"us-gaap:{concept}", unit="USD", period_start=date(fy, 1, 1),
                period_end=date(fy, 12, 31), fiscal_year=fy, fiscal_period="FY", value=value,
                form="10-K", accession=f"K{fy}-{suffix}", source="companyfacts",
                reconciled=True, is_latest=True,
            ))
    db.commit()
    company_id = company.id
    db.close()
    return company_id


def _fake_stream(chunks, calls=None):
    async def fake(messages, **kwargs):
        if calls is not None:
            calls.append(messages)
        usage_sink = kwargs.get("usage_sink")
        if usage_sink is not None:
            usage_sink.update({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        for chunk in chunks:
            yield chunk

    return fake


async def _drain(company_id, monkeypatch, chunks, *, force=False, calls=None):
    from app.services import openai_service as oa

    monkeypatch.setattr(oa.openai_service, "stream_chat", _fake_stream(chunks, calls))
    return [
        event
        async for event in svc.stream_trend_narrative(
            company_id=company_id, mode="annual", start_period="FY2021",
            end_period="FY2023", force=force, user_id=None,
        )
    ]


@pytest.mark.requires_db
class TestStreamTrendNarrative:
    @pytest.mark.asyncio
    async def test_fresh_generation_event_contract_and_persistence(self, monkeypatch):
        from app.database import SessionLocal
        from app.models import TrendAnalysis

        company_id = _seed_company_with_history()
        chunks = ["## The trajectory\nRevenue reached ", "1,500 [F3] this year.", " Bogus [F99]."]
        events = await _drain(company_id, monkeypatch, chunks)

        types = [e["type"] for e in events]
        assert types[0] == "progress" and "token" in types and types[-1] == "complete"

        complete = events[-1]
        assert complete["kind"] == "analysis"
        assert complete["cached"] is False
        assert complete["n_periods"] == 3
        assert "[1]" in complete["narrative"] and "F99" not in complete["narrative"]
        assert complete["grounded"] == 1
        assert complete["citations"][0]["verified"] is True
        assert complete["usage"]["prompt_tokens"] == 100

        db = SessionLocal()
        row = db.query(TrendAnalysis).filter_by(company_id=company_id).one()
        assert row.id == complete["analysis_id"]
        assert row.period_key == "FY2021..FY2023"
        assert row.prompt_version == svc.PROMPT_VERSION
        assert row.narrative_md == complete["narrative"]
        db.close()

    @pytest.mark.asyncio
    async def test_cached_reserve_skips_model(self, monkeypatch):
        company_id = _seed_company_with_history()
        await _drain(company_id, monkeypatch, ["Solid year [F1]."])

        calls = []
        events = await _drain(company_id, monkeypatch, ["MUST NOT RUN"], calls=calls)
        complete = events[-1]
        assert complete["cached"] is True
        assert calls == []  # no model call
        assert all(e["type"] != "token" for e in events)

    @pytest.mark.asyncio
    async def test_force_regenerates(self, monkeypatch):
        company_id = _seed_company_with_history()
        await _drain(company_id, monkeypatch, ["First [F1]."])
        calls = []
        events = await _drain(company_id, monkeypatch, ["Second [F1]."], force=True, calls=calls)
        assert len(calls) == 1
        assert events[-1]["cached"] is False
        assert "Second" in events[-1]["narrative"]

    @pytest.mark.asyncio
    async def test_new_facts_invalidate_cache(self, monkeypatch):
        from app.database import SessionLocal
        from app.models import FinancialFact

        company_id = _seed_company_with_history()
        await _drain(company_id, monkeypatch, ["First [F1]."])

        # A restatement changes the dataset fingerprint → the cached narrative must not re-serve.
        db = SessionLocal()
        (db.query(FinancialFact)
           .filter_by(company_id=company_id, concept="revenue", fiscal_period="FY")
           .filter(FinancialFact.period_end == date(2023, 12, 31))
           .update({"is_latest": False}, synchronize_session=False))
        db.add(FinancialFact(
            company_id=company_id, filing_id=None, concept="revenue", raw_tag="us-gaap:Revenues",
            unit="USD", period_start=date(2023, 1, 1), period_end=date(2023, 12, 31),
            fiscal_year=2023, fiscal_period="FY", value=1510.0, form="10-K/A",
            accession=f"RESTATED-{uuid.uuid4().hex[:6]}", source="companyfacts",
            reconciled=True, is_latest=True,
        ))
        db.commit()
        db.close()

        calls = []
        events = await _drain(company_id, monkeypatch, ["Restated [F1]."], calls=calls)
        assert len(calls) == 1
        assert events[-1]["cached"] is False

    @pytest.mark.asyncio
    async def test_stream_error_yields_error_and_no_persist(self, monkeypatch):
        from app.database import SessionLocal
        from app.models import TrendAnalysis

        company_id = _seed_company_with_history()
        events = await _drain(company_id, monkeypatch, [f"{STREAM_ERROR_SENTINEL}boom"])
        assert events[-1]["type"] == "error"
        db = SessionLocal()
        assert db.query(TrendAnalysis).filter_by(company_id=company_id).count() == 0
        db.close()

    @pytest.mark.asyncio
    async def test_not_enough_data_completes_without_persist(self, monkeypatch):
        from app.database import SessionLocal
        from app.models import TrendAnalysis

        company_id = _seed_company_with_history()
        events = await _drain(company_id, monkeypatch, [svc.NOT_ENOUGH_DATA_SENTINEL])
        complete = events[-1]
        assert complete["type"] == "complete"
        assert complete["kind"] == "not_enough_data"
        assert complete["analysis_id"] is None
        db = SessionLocal()
        assert db.query(TrendAnalysis).filter_by(company_id=company_id).count() == 0
        db.close()

    @pytest.mark.asyncio
    async def test_bad_range_yields_error_event(self, monkeypatch):
        company_id = _seed_company_with_history()
        from app.services import openai_service as oa

        monkeypatch.setattr(oa.openai_service, "stream_chat", _fake_stream(["nope"]))
        events = [
            event
            async for event in svc.stream_trend_narrative(
                company_id=company_id, mode="annual", start_period="FY1990",
                end_period="FY1991", force=False, user_id=None,
            )
        ]
        assert events[-1]["type"] == "error"


class TestStreamRouteMetering:
    def _client(self, monkeypatch, events, *, allowed=True):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app import dependencies
        from app.routers import analysis as analysis_router

        app = FastAPI()
        app.include_router(analysis_router.router, prefix="/api/analysis")
        pro = SimpleNamespace(id=42, is_pro=True, subscription=None)
        app.dependency_overrides[dependencies._resolve_current_user] = lambda: pro
        app.dependency_overrides[analysis_router.get_current_user] = lambda: pro
        app.dependency_overrides[analysis_router.get_db] = lambda: MagicMock()

        monkeypatch.setattr(
            analysis_router, "check_analysis_limit", lambda user, db: (allowed, 0, 100)
        )

        async def fake_pipeline(**kwargs):
            for event in events:
                yield event

        monkeypatch.setattr(
            analysis_router.trend_analysis_service, "stream_trend_narrative", fake_pipeline
        )
        metered: list[int] = []
        monkeypatch.setattr(
            analysis_router, "_meter_analysis_best_effort", lambda user_id: metered.append(user_id)
        )
        monkeypatch.setattr(
            analysis_router, "_emit_analysis_cost_best_effort", lambda *a, **k: None
        )
        return TestClient(app), metered

    BODY = {"mode": "annual", "start_period": "FY2021", "end_period": "FY2023"}

    def test_fresh_complete_meters_once(self, monkeypatch):
        events = [
            {"type": "progress", "stage": "writing", "percent": 30},
            {"type": "complete", "kind": "analysis", "cached": False, "usage": {}},
        ]
        client, metered = self._client(monkeypatch, events)
        response = client.post("/api/analysis/TST/stream", json=self.BODY)
        assert response.status_code == 200
        assert "data: " in response.text
        assert metered == [42]

    def test_cached_complete_never_meters(self, monkeypatch):
        events = [{"type": "complete", "kind": "analysis", "cached": True, "usage": {}}]
        client, metered = self._client(monkeypatch, events)
        assert client.post("/api/analysis/TST/stream", json=self.BODY).status_code == 200
        assert metered == []

    def test_not_enough_data_never_meters(self, monkeypatch):
        events = [{"type": "complete", "kind": "not_enough_data", "cached": False, "usage": {}}]
        client, metered = self._client(monkeypatch, events)
        assert client.post("/api/analysis/TST/stream", json=self.BODY).status_code == 200
        assert metered == []

    def test_over_cap_429s(self, monkeypatch):
        client, metered = self._client(monkeypatch, [], allowed=False)
        response = client.post("/api/analysis/TST/stream", json=self.BODY)
        assert response.status_code == 429
        assert metered == []
