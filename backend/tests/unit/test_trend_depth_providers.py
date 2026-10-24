"""The depth harness's Claude API requests (evals/trend_depth/providers.py::anthropic_request).

Pins the request shapes the Claude 5.5 models accept: effort inside ``output_config``, adaptive thinking by
default, ``disabled`` thinking only where it is valid (Haiku 5.5), ``between_tools`` for Sonnet 5.5, and
no sampling parameters. The SDK is not needed: the builder returns plain keyword arguments.
"""
from __future__ import annotations

import asyncio
import json
import sys

import pytest

from evals.trend_depth import providers
from evals.trend_depth.providers import (
    ARMS, BudgetExceeded, CallResult, IncompleteReply, anthropic_request, call, canonical_pair, labels_by_number,
    list_cost, max_tokens_for,
)


def _request(arm: str) -> dict:
    return anthropic_request(ARMS[arm], "system text", "user text", 16000)


def test_default_arms_think_adaptively_at_their_effort() -> None:
    for arm, effort in (("claude-sonnet-5-5", "medium"), ("claude-haiku-5-5-low", "low"), ("claude-opus-5-5", "medium")):
        request = _request(arm)
        assert request["output_config"] == {"effort": effort}
        assert "thinking" not in request  # adaptive is each model's default
        assert request["model"] == ARMS[arm].model


def test_thinking_off_uses_each_models_own_setting() -> None:
    haiku = _request("claude-haiku-5-5-nothink")
    assert haiku["thinking"] == {"type": "disabled"}
    assert haiku["output_config"]["effort"] in ("low", "medium", "high")  # "disabled" is refused at xhigh/max
    sonnet = _request("claude-sonnet-5-5-nothink")
    assert sonnet["thinking"] == {"type": "between_tools"}  # Sonnet 5.5 refuses "disabled"
    assert sonnet["output_config"]["effort"] in ("low", "medium", "high")


@pytest.mark.parametrize("arm", [name for name, a in ARMS.items() if a.backend == "claude"])
def test_no_sampling_parameters_and_the_callers_cap(arm: str) -> None:
    request = _request(arm)
    assert not {"temperature", "top_p", "top_k"} & set(request)
    assert request["max_tokens"] == 16000  # the caller's cap stands; generation asks for more
    assert request["messages"] == [{"role": "user", "content": "user text"}]
    assert request["system"] == "system text"


def test_generation_cap_leaves_room_for_thinking() -> None:
    assert max_tokens_for(ARMS["claude-haiku-5-5"]) == 64000  # Haiku 5.5 at medium effort has written 43,000
    assert max_tokens_for(ARMS["deepseek-flash"]) == 16000


def test_list_cost_prices_cache_writes_and_haikus_long_prompt_tier() -> None:
    sonnet, haiku = ARMS["claude-sonnet-5-5"], ARMS["claude-haiku-5-5-low"]
    assert list_cost(sonnet, 1_000_000, 0, 0) == pytest.approx(2.00)
    assert list_cost(sonnet, 1_000_000, 1_000_000, 0) == pytest.approx(0.20)  # all read from cache
    assert list_cost(sonnet, 1_000_000, 0, 0, cache_write=1_000_000) == pytest.approx(2.50)  # 1.25x to write
    assert list_cost(haiku, 100_000, 0, 1_000) == pytest.approx(0.0105)  # at the threshold: $0.10 / $0.50
    assert list_cost(haiku, 100_001, 0, 1_000) == pytest.approx(100_001 * 0.50 / 1e6 + 1_000 * 2.50 / 1e6, abs=1e-6)  # above it


def test_auditor_labels_survive_malformed_numbers() -> None:
    labels = labels_by_number([{"n": 1, "label": "a"}, {"n": "2.", "label": "b"}, {"n": None}, {"n": "x"}, "junk"])
    assert sorted(labels) == [1, 2]
    assert labels_by_number(None) == {}


def test_pairs_have_one_orientation() -> None:
    assert canonical_pair("claude-sonnet-5-5", "current") == ("current", "claude-sonnet-5-5")
    assert canonical_pair("deepseek-flash", "claude-haiku-5-5-low") == ("deepseek-flash", "claude-haiku-5-5-low")
    assert canonical_pair("claude-haiku-5-5-low", "deepseek-flash") == ("deepseek-flash", "claude-haiku-5-5-low")


def _api(monkeypatch: pytest.MonkeyPatch, tmp_path, spent: float, meta: dict) -> list:
    log = tmp_path / "spend.jsonl"
    if spent:
        log.write_text(json.dumps({"backend": "anthropic", "cost_usd": spent}) + "\n")
    monkeypatch.setattr(providers, "SPEND_LOG", log)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", "75")
    sent: list = []

    async def fake(arm, system, user, max_tokens, timeout_s):
        sent.append(max_tokens)
        return CallResult("{}", 100, 0, 10, 0, 0.1, 0.25, "anthropic", arm.model, meta)

    monkeypatch.setattr(providers, "_call_anthropic", fake)
    return sent


def test_the_ceiling_stops_a_call_before_it_is_sent(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sent = _api(monkeypatch, tmp_path, 75.0, {"stop_reason": "end_turn"})
    with pytest.raises(BudgetExceeded):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    assert sent == []


def test_every_call_is_logged_and_a_truncated_reply_is_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t1"))
    assert providers.anthropic_spend() == pytest.approx(0.25)
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "max_tokens"})
    with pytest.raises(IncompleteReply):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t2"))
    assert providers.anthropic_spend() == pytest.approx(0.50)  # the truncated call was paid for, so it is logged


def test_these_tests_never_load_the_harness_bootstrap() -> None:
    # bootstrap rewrites DATABASE_URL and the AI settings for the process; it must stay out of the test session.
    assert "evals.trend_depth.bootstrap" not in sys.modules


def test_thinking_off_arm_refuses_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="needs the Claude API"):
        asyncio.run(call(ARMS["claude-haiku-5-5-nothink"], "s", "u"))
