"""One gate for the E8 programme's durable admission/retention invariant."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from openai import AsyncOpenAI

from evals.e8_budget import AdmissionStopped, BudgetTransport, CAP, CONTEXT, Ledger, SLOT


@pytest.mark.asyncio
async def test_e8_every_send_is_reserved_and_unknown_usage_stops_both_corpora(tmp_path, monkeypatch):
    import yaml
    workflow = yaml.safe_load((Path(__file__).resolve().parents[3] / ".github/workflows/ci.yml").read_text())
    assert workflow["jobs"]["eval-baseline"]["if"] is False
    pilot = workflow["jobs"]["e8-pilot"]
    assert pilot["concurrency"]["cancel-in-progress"] is False
    steps = {step.get("name"): step for step in pilot["steps"] if step.get("name")}
    assert 'test "$RUN_ATTEMPT" = 1' in steps["Refuse reruns"]["run"]
    assert '"$PRIOR_RUN" -lt "$CURRENT_RUN"' in steps["Refuse a second programme dispatch"]["run"]
    assert steps["Preserve all incurred response bytes, ledgers and partial corpora"]["if"] == "always()"
    sent = []
    release = asyncio.Event()

    async def uncertain(request):
        sent.append(request)
        await release.wait()
        return httpx.Response(200, stream=httpx.ByteStream(
            b'{"model":"deepseek-flash","choices":[],"usage":null}'))

    ledger = Ledger(tmp_path / "parallel")
    async with httpx.AsyncClient(transport=BudgetTransport(httpx.MockTransport(uncertain), ledger)) as client:
        kwargs = {"model": "deepseek-flash", "max_tokens": 100, "thinking": {"type": "disabled"}}
        tasks = [asyncio.create_task(client.post("https://api.deepseek.com/v1/chat/completions", json=kwargs))
                 for _ in range(20)]
        for _ in range(50):
            await asyncio.sleep(0)
        maximum = CAP // (CONTEXT * 300 + 100 * 1200)
        observed_sends = len(sent)
        occupied = sum(row["accounted_nanousd"] for row in ledger.snapshot()["requests"].values())
        release.set()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        assert observed_sends == maximum
        assert occupied <= CAP
        assert sum(isinstance(item, AdmissionStopped) for item in outcomes) == 20 - maximum
    assert all(row["state"] == "unknown" and row["accounted_nanousd"] == row["reserved_nanousd"]
               for row in ledger.snapshot()["requests"].values())
    with pytest.raises(FileExistsError):
        Ledger(tmp_path / "parallel")

    # A cancelled send may already be billable; keep its pre-send reservation durable.
    cancelled = Ledger(tmp_path / "cancelled")
    entered = asyncio.Event()

    async def waiting(_request):
        entered.set()
        await asyncio.Event().wait()

    async with httpx.AsyncClient(transport=BudgetTransport(httpx.MockTransport(waiting), cancelled)) as client:
        task = asyncio.create_task(client.post("https://api.deepseek.com/v1/chat/completions", json=kwargs))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    row = next(iter(cancelled.snapshot()["requests"].values()))
    assert row["state"] == "unknown" and row["accounted_nanousd"] == row["reserved_nanousd"]
    assert cancelled.snapshot()["stopped"]

    # Real SDK + existing request owner, retaining a full input sentinel. The SDK
    # closes SSE on DONE (not HTTP EOF); this is the actual stream settlement boundary.
    ledger = Ledger(tmp_path / "paired")
    bodies = []
    mode = "valid"

    class Wire(httpx.AsyncByteStream):
        async def __aiter__(self):
            packet = {"id": "fixture", "object": "chat.completion.chunk", "created": 1,
                      "model": "deepseek-flash", "choices": [{"index": 0, "delta": {"content": "{}"}, "finish_reason": "stop"}],
                      "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110,
                                "prompt_cache_hit_tokens": 70, "prompt_cache_miss_tokens": 30}}
            if mode == "unknown":
                packet["usage"]["prompt_cache_miss_tokens"] = 31
            yield b"data: " + json.dumps(packet).encode() + b"\n\ndata: [DONE]\n\n"

    async def reply(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, stream=Wire(), headers={"Content-Type": "text/event-stream"})

    from app.config import settings
    from app.services.openai_service import openai_service
    monkeypatch.setattr(settings, "AI_DEFAULT_MODEL", "deepseek-flash")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "")
    monkeypatch.setattr(settings, "AI_SUMMARY_THINKING_EFFORT", "")
    sdk = AsyncOpenAI(api_key="test-not-a-key", base_url=settings.OPENAI_BASE_URL, max_retries=0,
                     http_client=httpx.AsyncClient(transport=BudgetTransport(httpx.MockTransport(reply), ledger)))
    monkeypatch.setattr(openai_service, "client", sdk)
    source = "Retained filing sentinel at the start. " + "Complete provided filing data. " * 1000 + " Tail sentinel."
    parsed = openai_service._parse_and_clean_text("RAW MUST NOT APPEAR", "10-K", source)
    assert "Tail sentinel." in parsed["filing_sample"] and "RAW MUST NOT APPEAR" not in parsed["filing_sample"]

    async def preview(_text):
        pass

    try:
        for corpus in (1, 2):
            token = SLOT.set(f"n{corpus}:fixture")
            try:
                await openai_service._request_content(
                    {"model": "deepseek-flash", "messages": [{"role": "user", "content": source}],
                     "max_tokens": 100}, stream_cb=preview,
                )
            finally:
                SLOT.reset(token)
        assert len(bodies) == 2 and all(body["messages"][0]["content"] == source for body in bodies)
        rows = list(ledger.snapshot()["requests"].values())
        assert {row["slot"] for row in rows} == {"n1:fixture", "n2:fixture"}
        assert all(row["state"] == "usage_settled" and row["accounted_nanousd"] == 21420 for row in rows)
        assert len(list(ledger.directory.glob("*.response.body"))) == 2
        mode = "unknown"
        await openai_service._request_content(
            {"model": "deepseek-flash", "messages": [{"role": "user", "content": source}],
             "max_tokens": 100}, stream_cb=preview,
        )
        assert ledger.snapshot()["stopped"] == "inconsistent provider usage"
        unknown = list(ledger.snapshot()["requests"].values())[-1]
        assert unknown["accounted_nanousd"] == unknown["reserved_nanousd"]
        with pytest.raises(AdmissionStopped):
            ledger.reserve(b"{}", 100)
        assert len(bodies) == 3
        with pytest.raises(FileExistsError):
            Ledger(tmp_path / "paired")
    finally:
        await sdk.close()
