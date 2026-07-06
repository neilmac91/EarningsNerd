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
        "F3": {"concept": "operating_income", "label": "Operating income", "unit": "USD",
               "percent": False, "value": 300.0, "period": "FY2022", "raw_tag": None},
        "F10": {"kind": "cagr", "concept": "revenue", "label": "Revenue", "unit": "USD",
                "percent": False, "value": 0.134, "period": "FY2016..FY2025", "derived": False},
    }

    def test_renumbers_in_first_appearance_order(self):
        text = "Net income was 200 [F2] on revenue of 1,000 [F1]. Revenue again [F1]."
        final, citations, grounded, unverified = svc.resolve_narrative_citations(text, self.INDEX)
        assert "[1]" in final and "[2]" in final and "[F" not in final
        assert final.count("[1]") == 1  # F2 → 1 (first appearance)
        assert final.count("[2]") == 2  # F1 reused
        assert [c["n"] for c in citations] == [1, 2]
        assert citations[0]["concept"] == "net_income"
        assert citations[1]["section_ref"] == "XBRL · us-gaap:Revenues"
        assert grounded == 2
        assert unverified == 0

    def test_unknown_marker_stripped_swallowing_space(self):
        final, citations, grounded, unverified = svc.resolve_narrative_citations(
            "Margins expanded [F99], notably.", self.INDEX
        )
        assert final == "Margins expanded, notably."
        assert citations == []
        assert grounded == 0
        assert unverified == 1

    def test_marker_whitespace_and_case_tolerated(self):
        final, citations, _, _ = svc.resolve_narrative_citations("Revenue [f 1] grew.", self.INDEX)
        assert final == "Revenue [1] grew."
        assert citations[0]["concept"] == "revenue"

    # -- multi-reference groups (the [F58, F59, F60] leak class) --------------------------------

    def test_comma_list_resolves_as_chain(self):
        final, citations, grounded, unverified = svc.resolve_narrative_citations(
            "Margins compressed [F1, F2, F3] this year.", self.INDEX
        )
        assert final == "Margins compressed [1][2][3] this year."
        assert grounded == 3
        assert unverified == 0

    def test_range_resolves_written_endpoints(self):
        final, citations, grounded, _ = svc.resolve_narrative_citations(
            "Revenue compounded [F1..F3].", self.INDEX
        )
        assert final == "Revenue compounded [1][2]."
        assert [c["concept"] for c in citations] == ["revenue", "operating_income"]
        assert grounded == 2

    def test_vs_comparison_resolves_both(self):
        final, _, grounded, _ = svc.resolve_narrative_citations(
            "Buffer shrank [F2 vs F1].", self.INDEX
        )
        assert final == "Buffer shrank [1][2]."
        assert grounded == 2

    def test_group_drops_unknown_members_and_counts_them(self):
        final, citations, grounded, unverified = svc.resolve_narrative_citations(
            "Capex consumed cash [F1, F99].", self.INDEX
        )
        assert final == "Capex consumed cash [1]."
        assert grounded == 1
        assert unverified == 1

    def test_all_unknown_group_stripped(self):
        final, citations, grounded, unverified = svc.resolve_narrative_citations(
            "Trend held [F98, F99], broadly.", self.INDEX
        )
        assert final == "Trend held, broadly."
        assert grounded == 0
        assert unverified == 2

    def test_prose_brackets_left_untouched(self):
        text = "As noted [see F1 details], growth held."
        final, citations, grounded, unverified = svc.resolve_narrative_citations(text, self.INDEX)
        assert final == text
        assert citations == [] and grounded == 0 and unverified == 0

    @pytest.mark.parametrize("connector", ["through", "versus", "or", "and", "to"])
    def test_connector_words_resolve_as_citation_groups(self, connector):
        final, _, grounded, unverified = svc.resolve_narrative_citations(
            f"Series ran [F1 {connector} F2].", self.INDEX
        )
        assert final == "Series ran [1][2].", connector
        assert grounded == 2 and unverified == 0

    def test_cagr_marker_resolves_with_computed_ref(self):
        final, citations, grounded, _ = svc.resolve_narrative_citations(
            "Revenue compounded at 13.4% [F10].", self.INDEX
        )
        assert final == "Revenue compounded at 13.4% [1]."
        assert grounded == 1
        assert citations[0]["excerpt"] == "Revenue CAGR = +13.4% (FY2016..FY2025)"
        assert citations[0]["section_ref"] == "Computed · CAGR"
        assert citations[0]["verified"] is True
        assert citations[0]["derived"] is False


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


def _fake_stream_seq(attempts, calls=None):
    """Sequence-aware fake: call N serves attempts[N] (last one repeats) — for retry tests."""
    state = {"i": 0}

    async def fake(messages, **kwargs):
        if calls is not None:
            calls.append(messages)
        usage_sink = kwargs.get("usage_sink")
        if usage_sink is not None:
            usage_sink.update({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        chunks = attempts[min(state["i"], len(attempts) - 1)]
        state["i"] += 1
        for chunk in chunks:
            yield chunk

    return fake


async def _drain(company_id, monkeypatch, chunks, *, force=False, calls=None, fake=None):
    from app.services import openai_service as oa

    monkeypatch.setattr(oa.openai_service, "stream_chat", fake or _fake_stream(chunks, calls))
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
        chunks = ["## The trajectory\nRevenue reached ", "1,500 [F3] this year."]
        events = await _drain(company_id, monkeypatch, chunks)

        types = [e["type"] for e in events]
        assert types[0] == "progress" and "token" in types and types[-1] == "complete"

        complete = events[-1]
        assert complete["kind"] == "analysis"
        assert complete["cached"] is False
        assert complete["invalidated"] is False  # first generation — no cached row existed
        assert complete["n_periods"] == 3
        assert "[1]" in complete["narrative"]
        assert complete["grounded"] == 1
        assert complete["unverified"] == 0
        assert complete["citations"][0]["verified"] is True
        assert complete["usage"]["prompt_tokens"] == 100  # clean draft — exactly one model call

        db = SessionLocal()
        row = db.query(TrendAnalysis).filter_by(company_id=company_id).one()
        assert row.id == complete["analysis_id"]
        assert row.period_key == "FY2021..FY2023"
        assert row.prompt_version == svc.PROMPT_VERSION
        assert row.narrative_md == complete["narrative"]
        assert row.unverified == 0
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
        # User-initiated refresh over a still-valid cache is NOT system-invalidated (it meters).
        assert events[-1]["invalidated"] is False
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
        # A stale cached row triggered this regeneration — flagged so the route skips the meter.
        assert events[-1]["invalidated"] is True

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


@pytest.mark.requires_db
class TestRegenerateOnStrip:
    """One-shot retry when the draft carries citation defects (audit D2): illegal refs or
    figures that don't match the cited dataset values."""

    @pytest.mark.asyncio
    async def test_retry_fires_once_and_replaces_the_defective_draft(self, monkeypatch):
        from app.database import SessionLocal
        from app.models import TrendAnalysis

        company_id = _seed_company_with_history()
        calls: list = []
        fake = _fake_stream_seq(
            [
                ["Revenue reached 1,500 [F3]. Bogus [F99]."],  # draft 1: illegal ref
                ["Revenue reached 1,500 [F3] this year."],  # retry: clean
            ],
            calls,
        )
        events = await _drain(company_id, monkeypatch, None, fake=fake)

        assert len(calls) == 2
        complete = events[-1]
        # The clean retry wins: no unverified refs, and the retry's text is the narrative.
        assert complete["unverified"] == 0
        assert "this year" in complete["narrative"]
        assert "F99" not in complete["narrative"]
        # Usage sums BOTH model calls (cost telemetry must not undercount retried runs).
        assert complete["usage"]["prompt_tokens"] == 200
        # The user keeps watching draft 1 — attempt-2 tokens are never streamed.
        streamed = "".join(e["text"] for e in events if e["type"] == "token")
        assert "Bogus" in streamed and "this year" not in streamed
        # A "verifying" progress event announces the re-check.
        assert any(e["type"] == "progress" and e.get("stage") == "verifying" for e in events)

        db = SessionLocal()
        row = db.query(TrendAnalysis).filter_by(company_id=company_id).one()
        assert row.unverified == 0
        db.close()

    @pytest.mark.asyncio
    async def test_retry_prompt_carries_draft_and_illegal_refs(self, monkeypatch):
        company_id = _seed_company_with_history()
        calls: list = []
        fake = _fake_stream_seq(
            [["Solid [F1]. Bogus [F99]."], ["Solid [F1]."]],
            calls,
        )
        await _drain(company_id, monkeypatch, None, fake=fake)
        retry_messages = calls[1]
        assert retry_messages[-2]["role"] == "assistant"
        assert "Bogus" in retry_messages[-2]["content"]
        assert retry_messages[-1]["role"] == "user"
        assert "[F99]" in retry_messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_worse_retry_keeps_the_first_draft(self, monkeypatch):
        company_id = _seed_company_with_history()
        calls: list = []
        fake = _fake_stream_seq(
            [
                ["Revenue [F3]. Bogus [F99]."],  # 1 defect
                ["Revenue [F98]. Bogus [F99]. Also [F97]."],  # 3 defects — must not replace
            ],
            calls,
        )
        events = await _drain(company_id, monkeypatch, None, fake=fake)
        assert len(calls) == 2
        complete = events[-1]
        assert complete["unverified"] == 1  # draft 1's count
        assert complete["grounded"] == 1

    @pytest.mark.asyncio
    async def test_numeric_mismatch_triggers_the_retry(self, monkeypatch):
        company_id = _seed_company_with_history()
        calls: list = []
        fake = _fake_stream_seq(
            [
                # [F3] is real (revenue FY2023 = 1,500) but the printed figure is wrong: the
                # resolver passes it, the deterministic fidelity scan must not.
                ["Revenue reached 9,999 [F3]."],
                ["Revenue reached 1,500 [F3]."],
            ],
            calls,
        )
        events = await _drain(company_id, monkeypatch, None, fake=fake)
        assert len(calls) == 2
        assert "1,500" in events[-1]["narrative"]

    @pytest.mark.asyncio
    async def test_clean_draft_never_retries(self, monkeypatch):
        company_id = _seed_company_with_history()
        calls: list = []
        events = await _drain(
            company_id, monkeypatch, ["Revenue reached 1,500 [F3]."], calls=calls
        )
        assert len(calls) == 1
        assert events[-1]["usage"]["prompt_tokens"] == 100


class TestNumericFidelityScan:
    """Deterministic backstop behind the 'every cited figure' claim — pure text vs dataset."""

    def _index(self):
        return {
            "F1": {"concept": "revenue", "period": "FY2024", "value": 1_500_000_000.0,
                   "yoy": 0.183, "percent": False},
            "F2": {"concept": "net_margin", "period": "FY2024", "value": 38.3,
                   "yoy": -9.0, "percent": True},
        }

    def _citation(self, n, concept, period, value):
        return {"n": n, "concept": concept, "period": period, "value": value}

    def test_matching_compact_money_passes(self):
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        assert svc.scan_numeric_fidelity("Revenue hit $1.5B [1].", citations, self._index()) == []

    def test_wrong_figure_is_flagged(self):
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        assert svc.scan_numeric_fidelity("Revenue hit $9.9B [1].", citations, self._index()) == [1]

    def test_qualitative_reference_passes(self):
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        assert svc.scan_numeric_fidelity("Revenue kept climbing [1].", citations, self._index()) == []

    def test_pp_delta_of_the_cited_point_is_licensed(self):
        # Rule 1 lets the narrative cite the pp move with the value's marker:
        # "net margin eased to 38.3% [2], down 9.0pp YoY [2]".
        citations = [self._citation(2, "net_margin", "FY2024", 38.3)]
        text = "Net margin eased to 38.3% [2], down 9.0pp YoY [2]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == []

    def test_relative_growth_prints_x100_of_the_yoy_fraction(self):
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        text = "Revenue grew +18.3% [1]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == []

    def test_period_identifiers_are_not_figures(self):
        # FY2024 must not be parsed as the number 2024 and flagged as a mismatch.
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        assert svc.scan_numeric_fidelity("Held up in FY2024 [1].", citations, self._index()) == []

    def test_chained_markers_never_flag_each_other(self):
        # Review finding: the digit inside a preceding resolved "[1]" must never be parsed as
        # the figure claimed by "[2]" — chains are the resolver's own multi-ref output.
        citations = [
            self._citation(1, "revenue", "FY2024", 1_500_000_000.0),
            self._citation(2, "net_margin", "FY2024", 38.3),
        ]
        text = "Revenue hit $1.5B and margins held at 38.3% [1][2]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == []

    def test_window_bounded_at_previous_marker(self):
        # The claim before an earlier marker belongs to THAT marker: a qualitative reference
        # right after a quantitative one must not inherit its figure.
        citations = [
            self._citation(1, "revenue", "FY2024", 1_500_000_000.0),
            self._citation(2, "net_margin", "FY2024", 38.3),
        ]
        text = "Revenue hit $1.5B [1], and margins stayed resilient [2]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == []

    def test_any_matching_figure_in_the_claim_passes(self):
        # "from $X to $Y [a][b]" — the first marker's window holds both endpoints; one match
        # is enough (the prompt's canonical two-figure sentence).
        citations = [
            self._citation(1, "revenue", "FY2024", 1_500_000_000.0),
            self._citation(2, "revenue", "FY2024", 1_500_000_000.0),
        ]
        text = "Revenue went from $1.5B to $9.9B [1][2]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == []

    def test_small_bare_counts_are_not_figures(self):
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        text = "Growth held for 5 straight years [1]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == []

    def test_bn_style_suffix_parses_scaled(self):
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        assert svc.scan_numeric_fidelity("Revenue hit $1.5bn [1].", citations, self._index()) == []
        assert svc.scan_numeric_fidelity("Revenue hit $9.9bn [1].", citations, self._index()) == [1]

    def test_x100_not_licensed_for_monetary_values(self):
        # A hallucinated figure exactly 100× the cited USD value is the scale-slip class the
        # backstop exists for — only CAGR (fraction) markers may print ×100.
        citations = [self._citation(1, "revenue", "FY2024", 1_500_000_000.0)]
        text = "Revenue hit $150.0B [1]."
        assert svc.scan_numeric_fidelity(text, citations, self._index()) == [1]

    def test_cagr_fraction_prints_x100(self):
        index = {"F9": {"concept": "revenue", "period": "FY2016..FY2025", "value": 0.134,
                        "kind": "cagr"}}
        citations = [self._citation(1, "revenue", "FY2016..FY2025", 0.134)]
        text = "Revenue compounded at +13.4% [1]."
        assert svc.scan_numeric_fidelity(text, citations, index) == []


class TestStreamRouteMetering:
    def _client(self, monkeypatch, events, *, allowed=True, cached_exists=False):
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
        monkeypatch.setattr(
            analysis_router.trend_analysis_service,
            "has_cached_analysis",
            lambda *a, **k: cached_exists,
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

    def test_system_invalidated_regeneration_never_meters(self, monkeypatch):
        # Prompt bump / new facts under an existing cached row: fresh model call, but the
        # regeneration is system-triggered — the user's fair-use quota must not burn for it.
        events = [{
            "type": "complete", "kind": "analysis", "cached": False, "invalidated": True,
            "analysis_id": 7, "usage": {},
        }]
        client, metered = self._client(monkeypatch, events)
        assert client.post("/api/analysis/TST/stream", json=self.BODY).status_code == 200
        assert metered == []

    def test_invalidated_without_persist_still_meters(self, monkeypatch):
        # The exemption requires a SUCCESSFUL cache persist — if the write failed
        # (analysis_id None), every request would regenerate "invalidated" forever, so those
        # runs meter to bound the unmetered-model-call exposure.
        events = [{
            "type": "complete", "kind": "analysis", "cached": False, "invalidated": True,
            "analysis_id": None, "usage": {},
        }]
        client, metered = self._client(monkeypatch, events)
        assert client.post("/api/analysis/TST/stream", json=self.BODY).status_code == 200
        assert metered == [42]

    def test_over_cap_with_cached_key_proceeds_unmetered(self, monkeypatch):
        # At-cap user re-opening an existing range: the run can only resolve free (cache hit or
        # system-invalidated regen), so the 429 gate must not block it — otherwise the very
        # prompt bump that invalidates the fleet locks at-cap users out of their analyses.
        events = [{"type": "complete", "kind": "analysis", "cached": True, "usage": {}}]
        client, metered = self._client(monkeypatch, events, allowed=False, cached_exists=True)
        assert client.post("/api/analysis/TST/stream", json=self.BODY).status_code == 200
        assert metered == []

    def test_over_cap_force_refresh_still_429s(self, monkeypatch):
        client, metered = self._client(monkeypatch, [], allowed=False, cached_exists=True)
        response = client.post("/api/analysis/TST/stream", json={**self.BODY, "force": True})
        assert response.status_code == 429
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
