"""Unit tests for Copilot inference-cost telemetry (roadmap 2.1).

Covers the pure cost estimator, the best-effort PostHog emit helper (event name + property
filtering), and the router wiring that turns a `complete` event's usage into a cost event.
"""

import pytest

from app.config import settings
from app.services.llm_pricing import estimate_inference_cost_usd
from app.services import posthog_client
from app.routers import summaries


# --- pure cost estimator ---

def test_estimate_cost_matches_configured_rates():
    pt, ct = 12_000, 800
    expected = round(
        (pt * settings.AI_INPUT_PRICE_PER_1M_TOKENS + ct * settings.AI_OUTPUT_PRICE_PER_1M_TOKENS)
        / 1_000_000,
        6,
    )
    assert estimate_inference_cost_usd(pt, ct) == expected
    assert expected > 0  # sanity: non-zero tokens → non-zero cost


@pytest.mark.parametrize("pt, ct", [(0, 0), (None, None), (None, 0)])
def test_estimate_cost_is_zero_when_no_tokens(pt, ct):
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
        total_tokens=150, cost_usd=0.0001, filing_id=3, ticker="AAPL", kind="answer", grounded=2,
    )
    assert len(calls) == 1
    distinct_id, event, props = calls[0]
    assert distinct_id == "42"
    assert event == posthog_client.EVENT_COPILOT_INFERENCE == "copilot_inference_cost"
    assert props["model"] == "deepseek-v4-pro"
    assert props["cost_usd"] == 0.0001
    assert props["filing_id"] == 3 and props["ticker"] == "AAPL" and props["total_tokens"] == 150


def test_capture_copilot_inference_drops_none_properties(monkeypatch):
    calls = []
    monkeypatch.setattr(
        posthog_client, "capture_event",
        lambda distinct_id, event, properties=None: calls.append(properties),
    )
    posthog_client.capture_copilot_inference(distinct_id="42", prompt_tokens=10, completion_tokens=5)
    props = calls[0]
    assert props == {"prompt_tokens": 10, "completion_tokens": 5}  # all None fields dropped


# --- router wiring: complete-event usage → cost event ---

def test_router_emit_computes_cost_and_passes_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(summaries, "capture_copilot_inference", lambda **kw: captured.update(kw))
    event = {
        "type": "complete", "kind": "answer", "grounded": 2,
        "usage": {"model": "deepseek-v4-pro", "prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
    }
    summaries._emit_copilot_cost_best_effort(42, 3, "AAPL", event)
    assert captured["distinct_id"] == "42"
    assert captured["filing_id"] == 3 and captured["ticker"] == "AAPL"
    assert captured["prompt_tokens"] == 1000 and captured["total_tokens"] == 1200
    assert captured["cost_usd"] == estimate_inference_cost_usd(1000, 200)
    assert captured["grounded"] == 2 and captured["kind"] == "answer"


def test_router_emit_is_noop_without_usage(monkeypatch):
    called = []
    monkeypatch.setattr(summaries, "capture_copilot_inference", lambda **kw: called.append(kw))
    # A complete event with no usage (provider returned none) must not emit a cost event.
    summaries._emit_copilot_cost_best_effort(42, 3, "AAPL", {"type": "complete", "kind": "answer"})
    assert called == []
