"""Actual SDK/native and legacy transport regression gates; all requests are offline."""

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import httpx2
import pytest
from openai import AsyncOpenAI, APIError, AuthenticationError

from app.config import settings
from app.services.ai import provider_requests as requests
from app.services.openai_service import OpenAIService

KW = {
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": "filing"}],
    "max_tokens": 1200,
    "response_format": {"type": "json_object"},
}


def completion(content='{"fresh":true}', **overrides):
    return {
        "id": "offline",
        "object": "chat.completion",
        "created": 1,
        "model": "deepseek-chat",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "prompt_cache_hit_tokens": 7},
        **overrides,
    }


def chunk(content=None, **overrides):
    return {
        "id": "offline",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "deepseek-chat",
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
        **overrides,
    }


def event(data):
    return ("data: " + json.dumps(data) + "\n\n").encode()


@asynccontextmanager
async def service_for(handler, lib=httpx2):
    # Bypass construction of unused network clients, but exercise the real SDK on its native wire.
    service = object.__new__(OpenAIService)
    service.fallback_client = None
    service.model = KW["model"]
    async with AsyncOpenAI(
        api_key="offline-primary",
        base_url="https://api.deepseek.com/v1",
        max_retries=0,
        http_client=lib.AsyncClient(transport=lib.MockTransport(handler)),
    ) as client:
        service.client = client
        yield service


@pytest.fixture
def observations(monkeypatch):
    rows = []

    def record(**kwargs):
        rows.append(kwargs)
        return kwargs

    monkeypatch.setattr(requests, "record_ai_call", record)
    monkeypatch.setattr(requests, "retry_delay", lambda *args: 0)
    return rows


@pytest.mark.asyncio
@pytest.mark.parametrize("lib", [httpx2, httpx])
async def test_sdk_wire_transient_retry_and_actual_usage(lib, observations):
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return lib.Response(429, json={"error": {"type": "rate_limit_error", "message": "busy"}})
        return lib.Response(200, json=completion())

    async with service_for(handler, lib) as service:
        assert await service._request_content(KW) == '{"fresh":true}'
    assert len(calls) == 2
    assert calls[0].url.path == "/v1/chat/completions"
    body = json.loads(calls[-1].content)
    assert body["thinking"] == {"type": "disabled"} and body["response_format"] == {"type": "json_object"}
    assert [r["outcome"] for r in observations] == ["error", "success"]
    assert observations[0]["usage"] is None
    assert observations[1]["actual_model"] == "deepseek-chat"
    assert observations[1]["usage"].prompt_cache_hit_tokens == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 429, 503])
async def test_exact_attempt_count_and_sdk_retry_override(status, observations):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx2.Response(status, headers={"x-should-retry": "true"}, json={"error": {"message": "reject"}})

    async with service_for(handler) as service:
        with pytest.raises(Exception):
            await service._request_content(KW)
    assert len(calls) == (3 if status in (429, 503) else 1)
    assert len(observations) == len(calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("lib", [httpx2, httpx])
async def test_partial_stream_transport_drop_discards_old_text(lib, observations):
    calls, closed = [], []

    class Broken(lib.AsyncByteStream):
        async def __aiter__(self):
            yield event(chunk("OLD PARTIAL"))
            raise lib.ReadError("offline drop")

        async def aclose(self):
            closed.append(True)

    def handler(req):
        calls.append(json.loads(req.content))
        if len(calls) == 1:
            return lib.Response(200, headers={"content-type": "text/event-stream"}, stream=Broken())
        return lib.Response(200, json=completion())

    async with service_for(handler, lib) as service:
        result = await service._request_content(KW, stream_cb=lambda _: None)
    assert result == '{"fresh":true}' and len(calls) == 2 and closed
    assert calls[0]["stream_options"] == {"include_usage": True} and "stream" not in calls[1]
    assert observations[0]["actual_model"] == "deepseek-chat" and observations[0]["usage"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type,retries", [("authentication_error", 1), ("invalid_request_error", 1), ("server_error", 2)]
)
async def test_sse_error_body_distinguishes_rejected_credentials(error_type, retries, observations):
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=event({"error": {"type": error_type, "message": "offline"}}),
            )
        return httpx2.Response(200, json=completion())

    async with service_for(handler) as service:
        if retries == 1:
            with pytest.raises(APIError):
                await service._request_content(KW, stream_cb=lambda _: None)
        else:
            assert await service._request_content(KW, stream_cb=lambda _: None) == '{"fresh":true}'
    assert len(calls) == retries


@pytest.mark.asyncio
async def test_empty_choices_usage_is_captured_once_and_stream_closed(observations):
    closed = []

    class Body(httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield event(chunk('{"fresh":true}', usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}))
            yield event(chunk(choices=[], usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}))
            yield b"data: [DONE]\n\n"

        async def aclose(self):
            closed.append(True)

    async with service_for(
        lambda req: httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Body())
    ) as service:
        assert await service._request_content(KW, stream_cb=lambda _: None) == '{"fresh":true}'
    assert len(observations) == 1 and observations[0]["usage"].total_tokens == 12 and closed


@pytest.mark.asyncio
async def test_cancel_during_stream_closes_without_retry(observations):
    entered, closed, calls = asyncio.Event(), [], []

    class Body(httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield event(chunk("partial"))
            entered.set()
            await asyncio.Event().wait()

        async def aclose(self):
            closed.append(True)

    def handler(req):
        calls.append(req)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Body())

    async with service_for(handler) as service:
        task = asyncio.create_task(service._request_content(KW, stream_cb=lambda _: None))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(calls) == 1 and closed and observations[0]["outcome"] == "cancelled"


@pytest.mark.asyncio
async def test_malformed_exhaustion_never_reuses_old_response(observations):
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx2.Response(200, json=completion(choices=[]))
        if len(calls) == 2:
            return httpx2.Response(200, json=completion("   "))
        return httpx2.Response(503, json={"error": {"message": "unavailable"}})

    async with service_for(handler) as service:
        with pytest.raises(Exception, match="unavailable"):
            await service._request_content(KW)
    assert len(calls) == 3 and all(r["outcome"] == "error" for r in observations)


@pytest.mark.asyncio
async def test_timeout_routes_alternate_before_total_budget_expires(monkeypatch, observations):
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "alternate")
    monkeypatch.setattr(settings, "AI_FALLBACK_BASE_URL", "https://alternate.invalid/v1")
    calls = []

    async def primary(req):
        calls.append("primary")
        await asyncio.sleep(10)

    def fallback(req):
        body = json.loads(req.content)
        assert body["model"] == "alternate" and "thinking" not in body
        calls.append("fallback")
        assert req.headers["authorization"] == "Bearer offline-alternate"
        return httpx2.Response(200, json=completion())

    async with service_for(primary) as service:
        async with AsyncOpenAI(
            api_key="offline-alternate",
            base_url="https://alternate.invalid/v1",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(fallback)),
        ) as alternate:
            service.fallback_client = alternate
            budget = requests.RequestBudget(asyncio.get_running_loop().time() + 0.15)
            token = requests._budget.set(budget)
            try:
                assert await service._request_content(KW, timeout=0.08) == '{"fresh":true}'
            finally:
                requests._budget.reset(token)
    assert calls == ["primary", "fallback"] and observations[-1]["provider"] == "fallback"


@pytest.mark.asyncio
async def test_shared_deadline_recovery_wait_and_concurrent_isolation(monkeypatch, observations):
    async def primary(req):
        await asyncio.sleep(0.025)
        return httpx2.Response(200, json=completion())

    async with service_for(primary) as service:
        budget = requests.RequestBudget(asyncio.get_running_loop().time() + 0.04)
        token = requests._budget.set(budget)
        try:
            await service._request_content(KW)
            with pytest.raises(TimeoutError):
                await service._request_content(KW, operation="section_recovery")
            assert len(budget.records) == 2
        finally:
            requests._budget.reset(token)
        # Each root call has its own three-attempt quota; no singleton state survives.
        out = await asyncio.gather(service._request_content(KW), service._request_content(KW))
        assert out == ['{"fresh":true}', '{"fresh":true}']


def test_retry_after_is_capped_and_auth_not_transient():
    from openai import RateLimitError

    response = httpx2.Response(
        429, headers={"retry-after": "120"}, request=httpx2.Request("POST", "https://offline.invalid")
    )
    error = RateLimitError("busy", response=response, body={})
    assert requests.retry_delay(error, 0) == 5
    auth = AuthenticationError("rejected", response=httpx2.Response(401, request=response.request), body={})
    assert requests.transient(auth) is False


@pytest.mark.asyncio
async def test_fallback_origin_requires_separate_key_and_sdk_retries_disabled(monkeypatch):
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "alternate")
    monkeypatch.setattr(settings, "AI_FALLBACK_BASE_URL", "https://alternate.invalid/v1")
    monkeypatch.setattr(settings, "AI_FALLBACK_API_KEY", "")
    with pytest.raises(ValueError, match="requires AI_FALLBACK_API_KEY"):
        requests.fallback_client()
    monkeypatch.setattr(settings, "AI_FALLBACK_API_KEY", "offline-alternate")
    client = requests.fallback_client()
    assert client.api_key == "offline-alternate" and client.max_retries == 0
    await client.close()
    monkeypatch.setattr(settings, "AI_FALLBACK_BASE_URL", settings.OPENAI_BASE_URL)
    monkeypatch.setattr(settings, "AI_FALLBACK_API_KEY", "")
    client = requests.fallback_client()
    assert client.api_key == settings.OPENAI_API_KEY
    await client.close()
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "")
    assert requests.fallback_client() is None
    service = OpenAIService()
    assert service.client.max_retries == 0 and service.fallback_client is None
    await service.client.close()


@pytest.mark.asyncio
async def test_sdk_preheader_timeout_selects_fallback(monkeypatch, observations):
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "alternate")
    monkeypatch.setattr(settings, "AI_FALLBACK_BASE_URL", "https://alternate.invalid/v1")
    calls = []

    def primary(req):
        calls.append("primary")
        raise httpx2.ReadTimeout("offline headers timeout", request=req)

    def fallback(req):
        body = json.loads(req.content)
        assert body["model"] == "alternate" and "thinking" not in body
        calls.append("fallback")
        return httpx2.Response(200, json=completion())

    async with service_for(primary) as service:
        async with AsyncOpenAI(
            api_key="offline-alternate",
            base_url="https://alternate.invalid/v1",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(fallback)),
        ) as client:
            service.fallback_client = client
            assert await service._request_content(KW) == '{"fresh":true}'
    assert calls == ["primary", "fallback"]
    assert observations[0]["outcome"] == "timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("tools", [False, True])
@pytest.mark.parametrize("failure", ["before", "after", "close", "cancel"])
async def test_native_chat_retry_boundary_and_owned_stream_close(tools, failure, monkeypatch):
    from app.services.ai import copilot_chat

    monkeypatch.setattr(copilot_chat, "retry_delay", lambda *args: 0)
    calls, closed = [], []
    entered = asyncio.Event()

    class Body(httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield event(chunk("a" * 300))
            if failure == "after":
                raise httpx2.ReadError("offline dropped")
            if failure in ("close", "cancel"):
                entered.set()
                await asyncio.Event().wait()
            yield event(chunk(choices=[], usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}))
            yield b"data: [DONE]\n\n"

        async def aclose(self):
            closed.append(True)

    def handler(req):
        calls.append(req)
        if failure == "before" and len(calls) == 1:
            return httpx2.Response(503, json={"error": {"message": "busy"}})
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Body())

    async with service_for(handler) as service:
        sink = {}
        gen = (
            service.stream_chat_with_tools([], [], lambda *args: None, usage_sink=sink)
            if tools
            else service.stream_chat([], usage_sink=sink)
        )
        try:
            first = await anext(gen)
            assert first == "a" * 300
            if failure == "close":
                await gen.aclose()
            elif failure == "cancel":
                task = asyncio.create_task(anext(gen))
                await entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                rest = [part async for part in gen]
                if failure == "after":
                    assert len(rest) == 1 and rest[0].startswith(copilot_chat.STREAM_ERROR_SENTINEL)
                else:
                    assert rest == [] and sink["total_tokens"] == 12
            assert len(calls) == (2 if failure == "before" else 1) and closed
        finally:
            await gen.aclose()


@pytest.mark.asyncio
async def test_native_tools_fragments_execute_once_and_usage_accumulates():
    calls, executed, closed = [], [], []

    class Body(httpx2.AsyncByteStream):
        def __init__(self, round):
            self.round = round

        async def __aiter__(self):
            if self.round == 1:
                yield event(
                    chunk(
                        choices=[
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call1",
                                            "type": "function",
                                            "function": {"name": "fact", "arguments": '{"metric":'},
                                        }
                                    ]
                                },
                            }
                        ]
                    )
                )
                yield event(
                    chunk(
                        choices=[
                            {
                                "index": 0,
                                "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"revenue"}'}}]},
                            }
                        ]
                    )
                )
            else:
                yield event(chunk("The filing reports revenue."))
            yield event(chunk(choices=[], usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}))
            yield b"data: [DONE]\n\n"

        async def aclose(self):
            closed.append(True)

    def handler(req):
        calls.append(json.loads(req.content))
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Body(len(calls)))

    def tool(name, args):
        executed.append((name, args))
        return {"value": 100}

    async with service_for(handler) as service:
        sink = {}
        output = [
            part
            async for part in service.stream_chat_with_tools(
                [],
                [{"type": "function", "function": {"name": "fact", "parameters": {"type": "object"}}}],
                tool,
                usage_sink=sink,
            )
        ]
    assert executed == [("fact", {"metric": "revenue"})] and len(calls) == 2 and len(closed) == 2
    assert output[-1] == "The filing reports revenue." and sink["total_tokens"] == 24
    assert calls[1]["messages"][-1]["tool_call_id"] == "call1"


@pytest.mark.asyncio
async def test_summary_context_reports_once_and_isolates_concurrent_records(monkeypatch):
    reports = []
    monkeypatch.setattr(
        requests, "record_ai_summary", lambda records, outcome: reports.append((list(records), outcome))
    )

    async def handler(req):
        await asyncio.sleep(0.001)
        return httpx2.Response(200, json=completion())

    async with service_for(handler) as service:

        async def generate(*args, **kwargs):
            await service._request_content(KW)
            await service._run_secondary_completion("10-K", "section")
            return {"metadata": {}, "sections": {}, "markdown": "Filing summary"}

        service._task_models = {"section_recovery": "deepseek-v4-pro"}
        service.generate_structured_summary = generate
        results = await asyncio.gather(
            service.summarize_filing("Selected filing", "Issuer", "10-K", filing_excerpt="Excerpt"),
            service.summarize_filing("Selected filing", "Issuer", "10-K", filing_excerpt="Excerpt"),
        )
    assert len(reports) == 2
    assert [outcome for _, outcome in reports] == [result["status"] for result in results]
    assert all(len(records) == 2 for records, outcome in reports)
    assert all([r["operation"] for r in records] == ["summary_primary", "section_recovery"] for records, _ in reports)


@pytest.mark.asyncio
async def test_recovery_semaphore_wait_is_inside_parent_deadline(monkeypatch):
    called = []
    async with service_for(lambda req: called.append(req)) as service:
        service._recovery_semaphore = asyncio.Semaphore(0)
        service._get_section_schema_snippet = lambda key: "{}"
        service._build_section_context = lambda *args: "selected filing excerpt"

        @requests.bounded_summary()
        async def generate():
            return await service._recover_missing_sections(["risks"], "10-K", {}, "filing", {})

        monkeypatch.setattr(requests, "SUMMARY_SECONDS", 0.02)
        started = asyncio.get_running_loop().time()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(generate(), 0.2)
        assert asyncio.get_running_loop().time() - started < 0.15
    assert called == []


@pytest.mark.asyncio
async def test_delayed_tool_start_consumer_cannot_execute_after_deadline(monkeypatch):
    from app.services.ai import copilot_chat

    monkeypatch.setattr(copilot_chat, "_CHAT_SECONDS", 0.03)
    calls, executed = [], []
    data = (
        event(
            chunk(
                choices=[
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call1",
                                    "type": "function",
                                    "function": {"name": "fact", "arguments": "{}"},
                                }
                            ]
                        },
                    }
                ]
            )
        )
        + b"data: [DONE]\n\n"
    )

    def handler(req):
        calls.append(req)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=data)

    async with service_for(handler) as service:
        gen = service.stream_chat_with_tools([], [], lambda *args: executed.append(args))
        try:
            first = await anext(gen)
            assert first.startswith(copilot_chat.STREAM_ACTIVITY_SENTINEL)
            await asyncio.sleep(0.04)
            rest = [part async for part in gen]
            assert len(rest) == 1 and rest[0].startswith(copilot_chat.STREAM_ERROR_SENTINEL)
            assert executed == [] and len(calls) == 1
        finally:
            await gen.aclose()


@pytest.mark.asyncio
async def test_facade_propagates_earlier_request_timeout_to_orchestrator(monkeypatch):
    reports = []
    monkeypatch.setattr(requests, "record_ai_summary", lambda records, outcome: reports.append(outcome))
    async with service_for(lambda req: None) as service:

        async def generate(*args, **kwargs):
            raise TimeoutError("request deadline exhausted before outer timer fired")

        service.generate_structured_summary = generate
        with pytest.raises(TimeoutError, match="request deadline exhausted"):
            await service.summarize_filing("Selected filing", "Issuer", "10-K")
    assert reports == ["timeout"]
