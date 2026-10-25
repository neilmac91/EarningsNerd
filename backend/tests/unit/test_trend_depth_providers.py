"""The depth harness's Claude API path (evals/trend_depth/providers.py).

Pins the request shapes the Claude 5.5 models accept: effort inside ``output_config``, adaptive thinking by
default, ``disabled`` thinking only where it is valid (Haiku 5.5), ``between_tools`` for Sonnet 5.5, and
no sampling parameters. Also pins the spend ledger and the ceiling checked before each call. The SDK is not
needed: the builder returns plain keyword arguments and the network call is faked.
"""
from __future__ import annotations

import asyncio
import json
import sys

import pytest

from evals.trend_depth import providers
from evals.trend_depth.providers import (
    ARMS, BudgetExceeded, CallResult, IncompleteReply, KeyBusy, LedgerTorn, anthropic_request, call, canonical_pair,
    labels_by_number, list_cost, max_tokens_for, worst_case_usd,
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

    async def fake(arm, system, user, max_tokens, timeout_s, tag=""):
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
    with pytest.raises(IncompleteReply) as caught:
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t2"))
    assert providers.anthropic_spend() == pytest.approx(0.50)  # the truncated call was paid for, so it is logged
    assert caught.value.result.cost_usd == pytest.approx(0.25)  # and its caller can record what it cost


def test_worst_case_counts_a_token_for_every_prompt_byte_and_every_allowed_output_token() -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    # "é" is two UTF-8 bytes; 64 tokens of framing on top.
    assert worst_case_usd(sonnet, "x" * 2000, "é" * 500, 500) == pytest.approx(list_cost(sonnet, 2000 + 1000 + 64, 0, 500))


def test_a_call_in_flight_holds_its_worst_case_against_the_ceiling(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    monkeypatch.setattr(providers, "_in_flight_usd", 0.0)
    one = worst_case_usd(sonnet, "s", "u", 16000)
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(one * 1.5))  # room for one worst case, not two

    async def scenario() -> None:
        gate, sent = asyncio.Event(), []

        async def slow(arm, system, user, max_tokens, timeout_s, tag=""):
            sent.append(arm.name)
            if len(sent) == 1:  # only the first is held in flight, so a regression fails instead of hanging
                await gate.wait()
            return CallResult("{}", 100, 0, 10, 0, 0.1, 0.01, "anthropic", arm.model, {"stop_reason": "end_turn"})

        monkeypatch.setattr(providers, "_call_anthropic", slow)
        first = asyncio.create_task(call(sonnet, "s", "u"))
        await asyncio.sleep(0)
        assert providers._in_flight_usd == pytest.approx(one)
        with pytest.raises(BudgetExceeded):
            await call(sonnet, "s", "u")
        assert len(sent) == 1  # the second call was refused before it was sent
        gate.set()
        await first
        assert providers._in_flight_usd == pytest.approx(0.0, abs=1e-9)  # released once the call is logged

    asyncio.run(scenario())


def _flaky(monkeypatch: pytest.MonkeyPatch, failures: list) -> tuple[list, list]:
    """Fake attempts: each raises the next of ``failures`` until they run out, then one succeeds."""
    sent: list = []
    waits: list = []

    async def attempt(arm, system, user, max_tokens, timeout_s, tag=""):
        sent.append(tag)
        if len(sent) <= len(failures):
            raise failures[len(sent) - 1]
        return CallResult("{}", 1000, 0, 10, 0, 0.1, 0.01, "anthropic", arm.model, {"stop_reason": "end_turn"})

    async def no_wait(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(providers, "_call_anthropic", attempt)
    monkeypatch.setattr(providers, "_sleep", no_wait)
    return sent, waits


def _cut(cost: float) -> CallResult:
    return CallResult("", 1000, 0, 16000, 0, 1.0, cost, "anthropic", "claude-sonnet-5-5", {"stop_reason": "cut short"})


def test_a_cut_attempt_is_logged_at_its_worst_case_before_the_retry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    monkeypatch.setattr(providers, "_in_flight_usd", 0.0)
    sent, waits = _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(0.3), True)])
    result = asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t"))
    assert len(sent) == 2 and waits == [10.0]
    assert result.meta["retries"] == 1 and result.meta["cut_attempts"] == 1
    rows = [json.loads(line) for line in (tmp_path / "spend.jsonl").read_text().splitlines()]
    assert [row["cost_usd"] for row in rows] == [0.3, 0.01]
    assert "estimated" in rows[0] and "estimated" not in rows[1]
    assert providers._in_flight_usd == pytest.approx(0.0, abs=1e-9)


def test_each_retry_is_admitted_against_the_ceiling_again(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    monkeypatch.setattr(providers, "_in_flight_usd", 0.0)
    one = worst_case_usd(sonnet, "s", "u", 16000)
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(one * 1.5))
    sent, _ = _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(one), True)])
    with pytest.raises(BudgetExceeded):
        asyncio.run(call(sonnet, "s", "u"))
    assert len(sent) == 1  # the cut attempt's worst case left no room for a second
    assert providers.anthropic_spend() == pytest.approx(one)


def test_a_call_whose_worst_case_does_not_fit_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    one = worst_case_usd(sonnet, "s", "u", 16000)
    sent = _api(monkeypatch, tmp_path, 75.0 - one / 2, {"stop_reason": "end_turn"})  # spent is under the ceiling
    with pytest.raises(BudgetExceeded):
        asyncio.run(call(sonnet, "s", "u"))
    assert sent == []


def test_a_failure_the_api_calls_permanent_is_raised_without_a_retry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    monkeypatch.setattr(providers, "_in_flight_usd", 0.0)
    sent, waits = _flaky(monkeypatch, [providers._AttemptFailed(ValueError("invalid request"), None, False)])
    with pytest.raises(ValueError, match="invalid request"):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    assert len(sent) == 1 and waits == []
    assert providers.anthropic_spend() == 0.0  # it never started, so nothing was billed or logged
    assert providers._in_flight_usd == pytest.approx(0.0, abs=1e-9)  # and its reservation was released


@pytest.mark.parametrize("interruption", [asyncio.CancelledError, KeyboardInterrupt])
def test_an_interrupted_attempt_releases_its_reservation(monkeypatch: pytest.MonkeyPatch, tmp_path, interruption) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    monkeypatch.setattr(providers, "_in_flight_usd", 0.0)
    _flaky(monkeypatch, [interruption()])
    with pytest.raises(interruption):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    assert providers._in_flight_usd == pytest.approx(0.0, abs=1e-9)
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(worst_case_usd(ARMS["claude-sonnet-5-5"], "s", "u", 16000) * 1.5))
    sent = _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(worst_case_usd(ARMS["claude-sonnet-5-5"], "s", "u", 16000) * 1.5))
    asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))  # room for one worst case: sent only if none leaked
    assert sent == [16000]


def test_a_second_process_on_the_key_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import fcntl

    sent = _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    log = tmp_path / "spend.jsonl"
    log.touch()
    with log.open("a") as other:  # an open of its own, as another process holds it
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(KeyBusy):
            asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    assert sent == []


def test_a_torn_ledger_row_is_read_for_what_it_kept(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    log = tmp_path / "spend.jsonl"
    log.write_text('{"backend": "anthropic", "cost_usd": 1.5}\n'
                   '{"backend": "anthropic", "cost_usd": 0.25, "arm": "claude-so\n'  # torn after its cost
                   '{"backend": "openai_compat", "cost_u\n'  # torn, another backend
                   '\n[1, 2]\n{"backend": "claude_cli", "cost_usd": 9}\n')
    monkeypatch.setattr(providers, "SPEND_LOG", log)
    assert providers.anthropic_spend() == pytest.approx(1.75)  # CLI calls bill the subscription, not the key


@pytest.mark.parametrize("torn", ['{"backend": "anthropic", "cost_usd": 0.7', '{"backe'])
def test_a_torn_row_that_may_have_lost_a_claude_cost_stops_spending(monkeypatch: pytest.MonkeyPatch, tmp_path, torn: str) -> None:
    log = tmp_path / "spend.jsonl"
    log.write_text(torn)
    monkeypatch.setattr(providers, "SPEND_LOG", log)
    with pytest.raises(LedgerTorn):
        providers.anthropic_spend()


def test_a_row_after_a_torn_one_starts_its_own_line(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    log = tmp_path / "spend.jsonl"
    log.write_text('{"backend": "anthropic", "cost_usd": 0.5, "ar')
    monkeypatch.setattr(providers, "SPEND_LOG", log)
    providers._log_spend(ARMS["claude-sonnet-5-5"], CallResult("{}", 1, 0, 1, 0, 0.1, 0.25, "anthropic", "m", {}), "t")
    assert providers.anthropic_spend() == pytest.approx(0.75)


def test_these_tests_never_load_the_harness_bootstrap() -> None:
    # bootstrap rewrites DATABASE_URL and the AI settings for the process; it must stay out of the test session.
    assert "evals.trend_depth.bootstrap" not in sys.modules


def test_thinking_off_arm_refuses_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="needs the Claude API"):
        asyncio.run(call(ARMS["claude-haiku-5-5-nothink"], "s", "u"))
