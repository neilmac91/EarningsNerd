"""A rejected quotation may buy one fresh attempt, never publication or a new quota unit.

These checks compose the real service/admission, native SDK and ASGI quota owners. All
provider traffic is mocked; the existing quotation verifier and locked contracts stay intact.
"""
import asyncio
import copy
import json
from types import SimpleNamespace

import httpx2
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services import copilot_service
from app.services.ai import copilot_chat
from app.services.ai.copilot_chat import merge_chat_usage
from app.services.ai.provider_requests import signal_provider_start
from app.services.openai_service import STREAM_ACTIVITY_SENTINEL, STREAM_ERROR_SENTINEL
from tests.unit.test_copilot import _as_user, _asgi_post, _qa_state, _seed_filing, _wire_events
from tests.unit.test_provider_resilience import chunk, event, service_for

KNOWN = "Demand remained robust across cloud services."
SOURCE = "Item 2. Management's Discussion. " + KNOWN + " Capacity investment continued."
INVENTED = "INVENTED demand phrase absent from every source"
POISON = "FIRST-ATTEMPT-PRIVATE-CONTEXT"
ACCESSION = "0000000001-26-000001"
FOLLOWUPS = ["What supported cloud demand?", "What did capacity investment support?"]


def filing():
    return SimpleNamespace(
        company_id=1, accession_number=ACCESSION, period_of_report="2026-06-30",
        filing_type="10-Q", filing_date=None,
        document_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/filing.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/",
        xbrl_data={"reporting_currency": "USD"},
        company=SimpleNamespace(name="Test Company", ticker="TEST", cik="1"),
        content_cache=SimpleNamespace(critical_excerpt=SOURCE, markdown_content=None),
    )


def envelope(answer, *, excerpt=KNOWN, followups=FOLLOWUPS):
    citations = [{"n": 1, "excerpt": excerpt, "section": "Item 2 — MD&A"}]
    return (answer + "\n===CITATIONS===\n" + json.dumps(citations)
            + "\n===FOLLOWUPS===\n" + json.dumps(followups))


def rejected(surface="answer"):
    if surface == "not_disclosed":
        return (f'===NOT_DISCLOSED===\nThe filing does not explain "{INVENTED}".'
                + "\n===FOLLOWUPS===\n" + json.dumps(FOLLOWUPS))
    questions = FOLLOWUPS if surface == "answer" else [f'Why did management say "{INVENTED}"?', FOLLOWUPS[1]]
    answer = f'Management said "{INVENTED}" [1].' if surface == "answer" else f'Management said "{KNOWN}" [1].'
    return envelope(answer, followups=questions)


def usage(attempt):
    return {"model": "offline-primary", "prompt_tokens": 10, "completion_tokens": 3,
            "total_tokens": 13, "estimated_cost_usd": 0.001 * attempt, "call_count": 1}


async def collect(selected_filing=None):
    return [row async for row in copilot_service.answer_filing_question(
        filing=selected_filing or filing(), question="What did management say about demand?",
        history=[{"role": "user", "content": "Tell me about this filing."},
                 {"role": "assistant", "content": "This filing discusses cloud services."}],
    )]


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["answer", "followup", "not_disclosed"])
async def test_quotation_retry_safety_gate(monkeypatch, surface):
    """One grouped rule gate: a private mismatch retries fresh, once, with bounded custody."""
    selected = filing()
    calls, closed, source_reads, normalizations, markers = [], [], [], [], []
    select_source, normalize = copilot_service._select_source_text, copilot_service.normalize_for_match

    def select(value):
        source_reads.append(value)
        return select_source(value)

    def normalized(value):
        normalizations.append(value)
        return normalize(value)

    def fact(_name, args, _company_id, **scope):
        concept = args["concept"]
        return {"concept": concept, "raw_tag": "us-gaap:" + concept, "accession": scope["accession_number"],
                "unit": "USD", "value": 100_000_000_000 if concept == "revenue" else 20_000_000_000,
                "period_start": "2026-01-01", "period_end": "2026-06-30", "fiscal_year": 2026,
                "fiscal_period": "Q2"}

    async def stream(messages, _tools, run_tool, **kwargs):
        attempt = len(calls) + 1
        calls.append({"messages": copy.deepcopy(messages), "deadline": kwargs.get("deadline"),
                      "usage_sink": id(kwargs["usage_sink"])})
        try:
            result = run_tool("get_financial_fact", {"concept": "revenue" if attempt == 1 else "net_income"})
            markers.append(result.get("cite"))
            merge_chat_usage(kwargs["usage_sink"], usage(attempt))
            if attempt == 1:
                # The native wrapper mutates messages with tool turns. A new attempt must
                # rebuild its original conversation rather than reuse this candidate context.
                messages.append({"role": "assistant", "content": POISON + rejected(surface)})
                yield rejected(surface)
                selected.content_cache.critical_excerpt = "UNRELATED CACHE REPLACEMENT"
            elif surface == "not_disclosed":
                yield ("===NOT_DISCLOSED===\nThis filing does not disclose monthly demand totals."
                       + "\n===FOLLOWUPS===\n" + json.dumps(FOLLOWUPS))
            else:
                yield envelope(f'Net income was $20.0B [{result["cite"]}]. Management said "{KNOWN}" [1].')
        finally:
            closed.append(attempt)

    monkeypatch.setattr(copilot_service, "_select_source_text", select)
    monkeypatch.setattr(copilot_service, "normalize_for_match", normalized)
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool", fact)
    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    before = asyncio.get_running_loop().time()
    rows = await collect(selected)
    terminal = [row for row in rows if row["type"] in {"complete", "error"}]
    assert len(calls) == 2 and closed == [1, 2]
    assert len(terminal) == 1 and terminal[0]["type"] == "complete"
    complete = terminal[0]
    assert complete["kind"] == ("not_disclosed" if surface == "not_disclosed" else "answer")
    assert all(row["type"] in {"progress", "activity", "not_disclosed", "complete"} for row in rows)
    assert POISON not in json.dumps(rows) and INVENTED not in json.dumps(rows)
    assert sum(row.get("stage") == copilot_service.PROVIDER_STARTED_STAGE for row in rows) == 1
    assert markers == ["F1", "F1"], "retry reused fact markers from its discarded candidate"
    assert source_reads == [selected] and normalizations.count(SOURCE) == 1
    assert calls[0]["usage_sink"] == calls[1]["usage_sink"]
    assert isinstance(calls[0]["deadline"], (int, float))
    assert before < calls[0]["deadline"] <= before + 75.1
    assert calls[0]["deadline"] == calls[1]["deadline"]
    assert SOURCE in json.dumps(calls[1]["messages"])
    assert "UNRELATED CACHE REPLACEMENT" not in json.dumps(calls[1]["messages"])
    assert POISON not in json.dumps(calls[1]["messages"]) and INVENTED not in json.dumps(calls[1]["messages"])
    first_system, retry_system = calls[0]["messages"][0], calls[1]["messages"][0]
    assert first_system["role"] == retry_system["role"] == "system"
    assert retry_system["content"] != first_system["content"]
    assert "quot" in retry_system["content"].lower() and "contiguous" in retry_system["content"].lower()
    assert complete["usage"]["total_tokens"] == 26
    assert complete["usage"]["call_count"] == 2
    assert complete["usage"]["estimated_cost_usd"] == pytest.approx(0.003)
    if surface != "not_disclosed":
        assert complete["grounded"] == 2
        assert len(complete["citations"]) == 2 and all(c["verified"] is True for c in complete["citations"])
        assert complete["citations"][0]["excerpt"].find("20") != -1
        assert "100" not in complete["citations"][0]["excerpt"]
        assert complete["citations"][1]["excerpt"] == KNOWN


@pytest.mark.asyncio
async def test_retry_exhaustion_has_one_terminal_error_without_private_candidates(monkeypatch):
    calls, closed = [], []

    async def stream(*_args, **kwargs):
        attempt = len(calls) + 1
        calls.append(kwargs["deadline"])
        try:
            yield rejected()
        finally:
            closed.append(attempt)

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    rows = await collect()
    assert len(calls) == 2 and closed == [1, 2]
    assert [row for row in rows if row["type"] in {"complete", "error"}] == [
        {"type": "error", "message": copilot_service._PUBLICATION_ERROR},
    ]
    assert all(row["type"] in {"progress", "error"} for row in rows)
    assert INVENTED not in json.dumps(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["malformed", "citation", "upstream", "ambiguous", "missing_source", "elided"])
async def test_other_rejections_do_not_buy_another_generation(monkeypatch, case):
    selected = filing()
    payload = {
        "malformed": 'A private answer [1].\n===CITATIONS===[{"n":1,',
        "citation": envelope("The filing supports this claim [1].", excerpt=INVENTED),
        "upstream": STREAM_ERROR_SENTINEL + "offline provider failed",
        "ambiguous": envelope(f'The filing said "{KNOWN}" [1]. [More](https://example.invalid)'),
        "missing_source": f'The filing said "{KNOWN}".\n===CITATIONS===[]',
        "elided": envelope('The filing said "Demand ... across cloud services" [1].'),
    }[case]
    if case == "missing_source":
        selected.content_cache.critical_excerpt = None
    calls = []

    async def stream(*_args, **_kwargs):
        calls.append(True)
        yield payload

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    rows = await collect(selected)
    assert len(calls) == 1
    assert len([row for row in rows if row["type"] == "error"]) == 1
    assert all(row["type"] in {"progress", "error"} for row in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["cancel", "aclose"])
async def test_retry_cancellation_closes_the_active_provider_without_terminal_prose(monkeypatch, mode):
    started = asyncio.Event()
    calls, closed, rows = [], [], []

    async def stream(*_args, **_kwargs):
        attempt = len(calls) + 1
        calls.append(attempt)
        try:
            if attempt == 1:
                yield rejected()
            else:
                started.set()
                yield STREAM_ACTIVITY_SENTINEL + json.dumps({"name": "get_financial_fact", "args": {}, "phase": "start"})
                await asyncio.Event().wait()
        finally:
            closed.append(attempt)

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    generator = copilot_service.answer_filing_question(filing=filing(), question="What did management say?")
    if mode == "cancel":
        async def consume():
            async for row in generator:
                rows.append(row)
        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
            await generator.aclose()
    else:
        async def until_activity():
            async for row in generator:
                rows.append(row)
                if row["type"] == "activity":
                    return
        try:
            await asyncio.wait_for(until_activity(), 2)
        finally:
            await generator.aclose()
    assert calls == [1, 2] and closed == [1, 2]
    assert all(row["type"] in {"progress", "activity"} for row in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["caller", "wrapper", "expired"])
async def test_native_sdk_retry_deadline_is_the_earlier_caller_or_75s_budget(monkeypatch, limit):
    calls, closed = [], []
    monkeypatch.setattr(copilot_chat, "_CHAT_SECONDS", 0.08 if limit == "wrapper" else 0.35)

    class Body(httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield event(chunk("a" * 300))
            await asyncio.Event().wait()

        async def aclose(self):
            closed.append(True)

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Body())

    async with service_for(handler) as service:
        # Build the SDK client before starting the caller's budget. First-client setup
        # is outside this streaming method's ownership and may exceed a tiny deadline.
        before = asyncio.get_running_loop().time()
        deadline = before + (0.08 if limit == "caller" else 1000 if limit == "wrapper" else -1)
        async def receive():
            return [piece async for piece in service.stream_chat_with_tools(
                [], [], lambda *_args: {}, deadline=deadline,
            )]
        output = await asyncio.wait_for(receive(), 0.5)
    assert asyncio.get_running_loop().time() - before < 0.2
    assert output[-1].startswith(STREAM_ERROR_SENTINEL)
    assert len(calls) == (0 if limit == "expired" else 1)
    assert len(closed) == len(calls)


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.mark.requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("is_pro", [False, True])
@pytest.mark.parametrize("outcome", ["recovered", "exhausted"])
async def test_real_asgi_retry_meters_once_and_refunds_only_terminal_failure(client, monkeypatch, is_pro, outcome):
    from app.routers import summaries as router

    calls, between_attempts, charged, refunded, completed_cost = [], [], [], [], []
    meter, refund = router._meter_qa_best_effort, router._refund_qa_best_effort
    user_id = None

    def metering(*args, **kwargs):
        charged.append(True)
        return meter(*args, **kwargs)

    def refunding(*args, **kwargs):
        refunded.append(True)
        return refund(*args, **kwargs)

    async def stream(*_args, **kwargs):
        attempt = len(calls) + 1
        calls.append(attempt)
        signal_provider_start()
        if attempt == 2:
            between_attempts.append(_qa_state(user_id))
        merge_chat_usage(kwargs["usage_sink"], usage(attempt))
        yield (envelope(f'Management said "{KNOWN}" [1].')
               if attempt == 2 and outcome == "recovered" else rejected())

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", stream)
    monkeypatch.setattr(router, "_meter_qa_best_effort", metering)
    monkeypatch.setattr(router, "_refund_qa_best_effort", refunding)
    monkeypatch.setattr(router, "capture_copilot_inference", lambda **kwargs: completed_cost.append(kwargs))
    with _as_user(is_pro=is_pro, free_taste_used=1) as uid, _seed_filing(source=SOURCE, accession=ACCESSION) as fid:
        user_id = uid
        sent = await asyncio.wait_for(_asgi_post(
            f"/api/summaries/filing/{fid}/ask-stream", {"question": "What did management say about demand?"},
            disconnect_after=asyncio.Event(),
        ), 10)
        rows = _wire_events(sent)
        terminal = [row for row in rows if row["type"] in {"complete", "error"}]
        counted = ([], 1, 1) if is_pro else ([], 0, 2)
        assert sent[0]["status"] == 200 and calls == [1, 2]
        assert charged == [True] and between_attempts == [counted]
        assert len(terminal) == 1
        assert INVENTED not in json.dumps(rows) and all(row["type"] != "token" for row in rows)
        if outcome == "recovered":
            assert terminal[0]["type"] == "complete" and _qa_state(uid) == counted
            assert refunded == [] and len(completed_cost) == 1
            assert completed_cost[0]["total_tokens"] == 26
            assert completed_cost[0]["cost_usd"] == pytest.approx(0.003)
        else:
            assert terminal == [{"type": "error", "message": copilot_service._PUBLICATION_ERROR}]
            assert refunded == [True] and _qa_state(uid) == ([], 0, 1)
            assert completed_cost == []
