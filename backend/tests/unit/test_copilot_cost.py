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

def test_router_emit_computes_cache_aware_cost_and_passes_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(summaries, "capture_copilot_inference", lambda **kw: captured.update(kw))
    event = {
        "type": "complete", "kind": "answer", "grounded": 2,
        "usage": {
            "model": "deepseek-v4-pro", "prompt_tokens": 12_000, "completion_tokens": 400,
            "total_tokens": 12_400, "cache_hit_tokens": 10_000, "cache_miss_tokens": 2_000,
        },
    }
    summaries._emit_copilot_cost_best_effort(42, 3, "AAPL", event)
    assert captured["distinct_id"] == "42"
    assert captured["filing_id"] == 3 and captured["ticker"] == "AAPL"
    assert captured["cache_hit_tokens"] == 10_000 and captured["cache_miss_tokens"] == 2_000
    assert captured["cost_usd"] == estimate_inference_cost_usd(
        12_000, 400, cache_hit_tokens=10_000, cache_miss_tokens=2_000
    )


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
    monkeypatch.setattr(settings, "AI_PEAK_PRICE_MULTIPLIER", 3.0)
    assert llm_pricing.estimate_call_cost_usd("deepseek-flash", usage, at=peak)["cost_usd"] == round(flash["cost_usd"] * 3, 6)
    # Unknown model: the Settings constants (the configured default's rates); no split → all miss.
    monkeypatch.setattr(settings, "AI_INPUT_CACHE_MISS_PRICE_PER_1M", 1.0)
    monkeypatch.setattr(settings, "AI_OUTPUT_PRICE_PER_1M_TOKENS", 2.0)
    unknown = llm_pricing.estimate_call_cost_usd("other-model", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, at=off_peak)
    assert unknown["cost_usd"] == 3.0
    assert llm_pricing.estimate_call_cost_usd("deepseek-flash", {}, at=off_peak) == {"cost_usd": None, "peak": False}
