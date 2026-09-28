"""Unit tests for Copilot inference-cost telemetry (roadmap 2.1).

Covers the cache-aware cost estimator (DeepSeek prices input cache-hit vs cache-miss ~120x apart),
the best-effort PostHog emit helper (event name + property filtering), and the router wiring that
turns a `complete` event's usage into a cost event.
"""

import pytest

from app.config import settings
from app.services.llm_pricing import estimate_inference_cost_usd
from app.services import posthog_client
from app.routers import summaries


# --- cache-aware cost estimator ---

def test_estimate_prices_cache_hit_and_miss_separately():
    hit, miss, completion = 100_000, 5_000, 800
    expected = round(
        (
            hit * settings.AI_INPUT_CACHE_HIT_PRICE_PER_1M
            + miss * settings.AI_INPUT_CACHE_MISS_PRICE_PER_1M
            + completion * settings.AI_OUTPUT_PRICE_PER_1M_TOKENS
        )
        / 1_000_000,
        6,
    )
    got = estimate_inference_cost_usd(
        hit + miss, completion, cache_hit_tokens=hit, cache_miss_tokens=miss
    )
    assert got == expected
    # The same input priced as all cache-miss (no split) must be strictly dearer — proving the
    # cache split actually lowers the estimate (the whole point of pricing them apart).
    assert got < estimate_inference_cost_usd(hit + miss, completion)


def test_estimate_falls_back_to_all_miss_without_split():
    pt, completion = 5_000, 800
    expected = round(
        (
            pt * settings.AI_INPUT_CACHE_MISS_PRICE_PER_1M
            + completion * settings.AI_OUTPUT_PRICE_PER_1M_TOKENS
        )
        / 1_000_000,
        6,
    )
    assert estimate_inference_cost_usd(pt, completion) == expected


@pytest.mark.parametrize("pt, ct", [(0, 0), (None, None)])
def test_estimate_is_zero_when_no_tokens(pt, ct):
    assert estimate_inference_cost_usd(pt, ct) == 0.0


# --- PostHog emit helper ---

def test_capture_copilot_inference_uses_event_name_and_keeps_fields(monkeypatch):
    calls = []
    monkeypatch.setattr(
        posthog_client, "capture_event",
        lambda distinct_id, event, properties=None: calls.append((distinct_id, event, properties)),
    )
    posthog_client.capture_copilot_inference(
        distinct_id="42", model="deepseek-v4-pro", prompt_tokens=100, completion_tokens=50,
        total_tokens=150, cache_hit_tokens=80, cache_miss_tokens=20, cost_usd=0.0001,
        filing_id=3, ticker="AAPL", kind="answer", grounded=2,
    )
    assert len(calls) == 1
    distinct_id, event, props = calls[0]
    assert distinct_id == "42"
    assert event == posthog_client.EVENT_COPILOT_INFERENCE == "copilot_inference_cost"
    assert props["model"] == "deepseek-v4-pro" and props["cost_usd"] == 0.0001
    assert props["cache_hit_tokens"] == 80 and props["cache_miss_tokens"] == 20
    assert props["filing_id"] == 3 and props["ticker"] == "AAPL"


def test_capture_copilot_inference_drops_none_properties(monkeypatch):
    calls = []
    monkeypatch.setattr(
        posthog_client, "capture_event",
        lambda distinct_id, event, properties=None: calls.append(properties),
    )
    posthog_client.capture_copilot_inference(distinct_id="42", prompt_tokens=10, completion_tokens=5)
    assert calls[0] == {"prompt_tokens": 10, "completion_tokens": 5}  # all None fields dropped


# --- router wiring: complete-event usage → cost event ---

@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["copilot", "analysis"])
@pytest.mark.parametrize("scenario", [
    "single", "mixed", "same", "unknown_first", "unknown_last", "unknown_model",
    "retry", "all_unknown", "zero", "partial",
])
async def test_completion_telemetry_preserves_physical_call_accounting(monkeypatch, surface, scenario):
    """One gate follows real SDK call records through tool/selection rounds to both emitters."""
    import json

    import httpx2

    from app.routers import analysis
    from app.services import ai_metrics, copilot_service, llm_pricing, openai_service, trend_analysis_service
    from app.services.ai import copilot_chat
    from tests.unit.test_analysis_stream import _seed_company_with_history, _selection
    from tests.unit.test_copilot import _fake_filing
    from tests.unit.test_provider_resilience import chunk, event, service_for

    pro, flash = "deepseek-v4-pro", "deepseek-flash"
    known = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
             "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40}
    zero = dict.fromkeys(known, 0)
    partial = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    scenarios = {
        "single": [(pro, known)],
        "mixed": [(pro, known), (flash, known)],
        "same": [(pro, known), (pro, known)],
        "unknown_first": [(pro, None), (flash, known)],
        "unknown_last": [(pro, known), (flash, None)],
        "unknown_model": [(None, known), (pro, known)],
        "retry": [(None, None), (pro, known), (flash, known)],
        "all_unknown": [(pro, None)],
        "zero": [(pro, zero)],
        "partial": [(pro, partial), (flash, known)],
    }
    physical_calls = scenarios[scenario]
    requests, priced = [], []

    def estimate(model, usage):
        priced.append(model)
        # Sentinels test accounting independently of tariff constants or wall-clock peak windows.
        cost = None if usage["prompt_tokens"] is None else (
            0.0 if usage["prompt_tokens"] == 0 else {pro: 0.125, flash: 0.875}[model]
        )
        return {"cost_usd": cost, "peak": False}

    monkeypatch.setattr(llm_pricing, "estimate_call_cost_usd", estimate)
    monkeypatch.setattr(copilot_chat, "retry_delay", lambda *args: 0)
    monkeypatch.setattr(ai_metrics, "_model_labels", set())
    monkeypatch.setattr(ai_metrics, "_calls", {})
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool", lambda *args, **kw: {"error": "offline"})

    def handler(request):
        index = len(requests)
        requests.append(json.loads(request.content))
        model, usage = physical_calls[index]
        if scenario == "retry" and index == 0:
            return httpx2.Response(503, json={"error": {"message": "offline retry"}})
        last = index == len(physical_calls) - 1
        if surface == "copilot" and not last:
            choices = [{"index": 0, "delta": {"tool_calls": [{
                "index": 0, "id": "offline-tool", "type": "function",
                "function": {"name": "get_fact", "arguments": "{}"},
            }]}}]
            content = chunk(model=model, choices=choices)
        else:
            answer = "The filing describes its business." if surface == "copilot" else (
                _selection() if last else "rejected selection"
            )
            content = chunk(answer, model=model)
        body = event(content) + event(chunk(model=model, choices=[], usage=usage)) + b"data: [DONE]\n\n"
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    async with service_for(handler) as service:
        service.model = flash  # The requested model must never overwrite the actual response model.
        if surface == "copilot":
            monkeypatch.setattr(copilot_service, "openai_service", service)
            events = [e async for e in copilot_service.answer_filing_question(
                filing=_fake_filing(), question="Describe the business.",
            )]
        else:
            from app.database import engine
            from app.models import Base

            Base.metadata.create_all(bind=engine)
            company_id = _seed_company_with_history()
            monkeypatch.setattr(openai_service, "openai_service", service)
            events = [e async for e in trend_analysis_service.stream_trend_narrative(
                company_id=company_id, mode="annual", start_period="FY2021", end_period="FY2023",
            )]

    assert events[-1]["type"] == "complete", events
    assert len(requests) == len(physical_calls)
    assert priced == [model or flash for model, _ in physical_calls]
    unknown = scenario in {"unknown_first", "unknown_last", "retry", "all_unknown"}
    expected_cost = None if unknown else {"single": 0.125, "same": 0.25, "zero": 0.0}.get(scenario, 1.0)
    expected_model = None if scenario in {"unknown_model", "retry"} else (
        "mixed" if scenario in {"mixed", "unknown_first", "unknown_last", "partial"} else pro
    )
    tokens = None if unknown else (0 if scenario == "zero" else 100 * len(physical_calls))
    usage = events[-1]["usage"]
    assert usage["model"] == expected_model
    assert usage["estimated_cost_usd"] == expected_cost
    assert usage["prompt_tokens"] == tokens
    assert usage["total_tokens"] == (None if tokens is None else tokens * 120 // 100)
    assert usage["cache_hit_tokens"] == (None if unknown or scenario == "partial" else tokens * 60 // 100)

    # Completion must reuse the prices already recorded, even if the tariff/window has changed.
    def no_repricing(*args, **kwargs):
        pytest.fail("completion repriced physical calls")

    monkeypatch.setattr(llm_pricing, "estimate_call_cost_usd", no_repricing)
    captured = {}
    if surface == "copilot":
        monkeypatch.setattr(summaries, "capture_copilot_inference", lambda **kw: captured.update(kw))
        summaries._emit_copilot_cost_best_effort(42, 3, "AAPL", events[-1])
        assert captured["filing_id"] == 3
    else:
        monkeypatch.setattr(analysis, "capture_analysis_inference", lambda **kw: captured.update(kw))
        analysis._emit_analysis_cost_best_effort(42, "AAPL", "annual", events[-1])
        assert captured["mode"] == "annual" and captured["n_periods"] == 3
    assert captured["distinct_id"] == "42" and captured["ticker"] == "AAPL"
    assert captured["model"] == expected_model and captured["cost_usd"] == expected_cost
    assert captured["prompt_tokens"] == tokens
    assert captured["cache_hit_tokens"] == usage["cache_hit_tokens"]


def test_router_emit_is_noop_without_usage(monkeypatch):
    called = []
    monkeypatch.setattr(summaries, "capture_copilot_inference", lambda **kw: called.append(kw))
    summaries._emit_copilot_cost_best_effort(42, 3, "AAPL", {"type": "complete", "kind": "answer"})
    assert called == []


def test_per_model_price_table_and_peak_multiplier(monkeypatch):
    from datetime import datetime, timezone

    from app.services import llm_pricing

    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
             "cache_hit_tokens": 500_000, "cache_miss_tokens": 500_000}
    off_peak = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)   # Saturday: never peak
    peak = datetime(2026, 9, 14, 7, 30, tzinfo=timezone.utc)       # Monday 07:30 UTC
    assert llm_pricing.is_peak_hour(off_peak) is False and llm_pricing.is_peak_hour(peak) is True
    assert llm_pricing.is_peak_hour(datetime(2026, 9, 14, 4, 0, tzinfo=timezone.utc)) is False  # [start, end)
    flash = llm_pricing.estimate_call_cost_usd("deepseek-flash", usage, at=off_peak)
    assert flash == {"cost_usd": round(0.5 * 0.003 + 0.5 * 0.15 + 0.60, 6), "peak": False}
    doubled = llm_pricing.estimate_call_cost_usd("deepseek-flash", usage, at=peak)
    assert doubled["peak"] is True and doubled["cost_usd"] == round(flash["cost_usd"] * 2, 6)
    # Pro service continued after September 14; its actual-model tariff differs from Flash.
    for model in ("deepseek-v4-pro", "deepseek-v4-pro-0813"):
        pro = llm_pricing.estimate_call_cost_usd(model, usage, at=off_peak)
        assert pro == {"cost_usd": round(0.5 * 0.022 + 0.5 * 0.66 + 1.98, 6), "peak": False}
        assert llm_pricing.estimate_call_cost_usd(model, usage, at=peak) == {
            "cost_usd": round(pro["cost_usd"] * 2, 6), "peak": True,
        }
    monkeypatch.setattr(settings, "AI_PEAK_PRICE_MULTIPLIER", 3.0)
    assert llm_pricing.estimate_call_cost_usd("deepseek-flash", usage, at=peak)["cost_usd"] == round(flash["cost_usd"] * 3, 6)
    # Unknown model: the Settings constants (the configured default's rates); no split → all miss.
    monkeypatch.setattr(settings, "AI_INPUT_CACHE_MISS_PRICE_PER_1M", 1.0)
    monkeypatch.setattr(settings, "AI_OUTPUT_PRICE_PER_1M_TOKENS", 2.0)
    unknown = llm_pricing.estimate_call_cost_usd("other-model", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, at=off_peak)
    assert unknown["cost_usd"] == 3.0
    assert llm_pricing.estimate_call_cost_usd("deepseek-flash", {}, at=off_peak) == {"cost_usd": None, "peak": False}
