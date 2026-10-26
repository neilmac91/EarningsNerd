"""The depth harness's Claude API path (evals/trend_depth/providers.py).

Pins the request shapes the Claude 5.5 models accept: effort inside ``output_config``, adaptive thinking by
default, ``disabled`` thinking only where it is valid (Haiku 5.5), ``between_tools`` for Sonnet 5.5, and
no sampling parameters. Also pins the spend ledger and the ceiling checked before each call, and the prompt and
pack directory each arm runs on (the frozen prompt on packs/ unless the arm names others). The SDK is not
needed: the builder returns plain keyword arguments and the network call is faked.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import types
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

import pytest

from evals.trend_depth import providers
from evals.trend_depth.providers import (
    ARMS, CANDIDATE_PROMPT, FROZEN_PROMPT, BudgetExceeded, CallResult, IncompleteReply, KeyBusy, LedgerTorn,
    anthropic_request, call, canonical_pair, labels_by_number, list_cost, max_tokens_for, packs_dir, prompt_path,
    worst_case_usd,
)


@pytest.fixture(autouse=True)
def _release_the_key_lock():
    """Each test that spends takes the ledger lock on its own temporary ledger; release it after the test."""
    yield
    if providers._key_lock is not None:
        providers._key_lock[1].close()
        providers._key_lock = None


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


REPO = Path(__file__).resolve().parents[3]
FROZEN_SHA256 = "d558d371f739479c44f6727a2fb1166f82fbade3f74e6d37f3b2c4fc401229ba"  # the prompt eval-v1 and dev-v4 ran
EXPERIMENT = {  # DEEPSEEK-ERRORS.md §3 step 2: (prompt, packs) of the arms off the frozen prompt on packs/
    "deepseek-flash-p": (FROZEN_PROMPT, "packs-v2"),
    "deepseek-flash-q": (CANDIDATE_PROMPT, "packs"),
    "deepseek-flash-c": (CANDIDATE_PROMPT, "packs-v2"),
}


@pytest.mark.parametrize("system", [*ARMS, "current", "gold"])
def test_each_system_reads_the_prompt_and_packs_its_arm_pins(system: str, tmp_path) -> None:
    prompt, packs = EXPERIMENT.get(system, (FROZEN_PROMPT, "packs"))  # every other arm, the control included
    assert prompt_path(system, REPO) == REPO / prompt
    assert packs_dir(system, tmp_path) == tmp_path / packs


def test_the_experiment_arms_differ_from_the_control_only_in_what_they_read() -> None:
    control = ARMS["deepseek-flash"]
    for name in EXPERIMENT:
        assert replace(ARMS[name], name=control.name, prompt="", packs="") == control  # model, prices, settings


def test_the_frozen_prompt_is_the_one_eval_v1_and_dev_v4_ran() -> None:
    assert hashlib.sha256((REPO / FROZEN_PROMPT).read_bytes()).hexdigest() == FROZEN_SHA256
    runs = REPO / "tasks" / "analysis-depth-2026-10" / "runs"
    records = [json.loads(path.read_text()) for label in ("eval-v1", "dev-v4") for path in (runs / label).glob("*/*.json")]
    proposed = [r for r in records if r.get("prompt_sha256")]
    assert len(proposed) >= 90  # 4 arms x 20 companies, and 2 x 5
    for record in proposed:  # copying these records forward still finds them on their arm's own prompt
        assert record["prompt_sha256"] == hashlib.sha256(prompt_path(record["arm"], REPO).read_bytes()).hexdigest()


def test_a_draft_stands_in_for_the_candidate_prompt_only(tmp_path) -> None:
    draft = str(tmp_path / "draft.md")
    for system in ("deepseek-flash-q", "deepseek-flash-c"):
        assert prompt_path(system, REPO, draft) == Path(draft)
    for system in ("deepseek-flash", "deepseek-flash-p", "claude-sonnet-5-5"):
        assert prompt_path(system, REPO, draft) == REPO / FROZEN_PROMPT  # an arm on the frozen prompt runs nothing else


def test_each_arm_names_a_prompt_in_the_repository_and_a_packs_folder_beside_the_records() -> None:
    for arm in ARMS.values():
        assert not arm.prompt or (not Path(arm.prompt).is_absolute() and (REPO / arm.prompt).is_file())
        assert "/" not in arm.packs and ".." not in arm.packs


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


def _paid(tmp_path) -> list[dict]:
    """The ledger's rows for paid attempts, without the reservations and their releases."""
    rows = [json.loads(line) for line in (tmp_path / "spend.jsonl").read_text().splitlines()]
    return [row for row in rows if not str(row.get("estimated", "")).startswith(("reserved", "released"))]


@pytest.mark.parametrize("cap", [16000, 64000])  # a judge's cap, and a generation's
def test_a_call_in_flight_holds_its_worst_case_in_the_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path, cap: int) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    one = worst_case_usd(sonnet, "s", "u", cap)
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(one * 1.5))  # room for one worst case, not two

    async def scenario() -> None:
        gate, sent = asyncio.Event(), []

        async def slow(arm, system, user, max_tokens, timeout_s, tag=""):
            sent.append(arm.name)
            if len(sent) == 1:  # only the first is held in flight, so a regression fails instead of hanging
                await gate.wait()
            return CallResult("{}", 100, 0, 10, 0, 0.1, 0.01, "anthropic", arm.model, {"stop_reason": "end_turn"})

        monkeypatch.setattr(providers, "_call_anthropic", slow)
        first = asyncio.create_task(call(sonnet, "s", "u", max_tokens=cap))
        await asyncio.sleep(0)
        # On disk before the attempt returns, so a process killed now leaves the worst case counted.
        assert providers.anthropic_spend() == pytest.approx(one)
        with pytest.raises(BudgetExceeded):
            await call(sonnet, "s", "u", max_tokens=cap)
        assert len(sent) == 1  # the second call was refused before it was sent
        gate.set()
        await first
        assert providers.anthropic_spend() == pytest.approx(0.01)  # released once the attempt's cost is logged

    asyncio.run(scenario())


def _flaky(monkeypatch: pytest.MonkeyPatch, failures: list, cost: float = 0.01) -> tuple[list, list]:
    """Fake attempts: each raises the next of ``failures`` until they run out, then one succeeds at ``cost``."""
    sent: list = []
    waits: list = []

    async def attempt(arm, system, user, max_tokens, timeout_s, tag=""):
        sent.append(tag)
        if len(sent) <= len(failures):
            raise failures[len(sent) - 1]
        return CallResult("{}", 1000, 0, 10, 0, 0.1, cost, "anthropic", arm.model, {"stop_reason": "end_turn"})

    async def no_wait(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(providers, "_call_anthropic", attempt)
    monkeypatch.setattr(providers, "_sleep", no_wait)
    return sent, waits


def _cut(cost: float) -> CallResult:
    return CallResult("", 1000, 0, 16000, 0, 1.0, cost, "anthropic", "claude-sonnet-5-5", {"stop_reason": "cut short"})


def test_a_cut_attempt_is_logged_at_its_worst_case_before_the_retry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    sent, waits = _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(0.3), True)])
    result = asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t"))
    assert len(sent) == 2 and waits == [10.0]
    assert result.meta["retries"] == 1 and result.meta["cut_attempts"] == 1
    rows = [json.loads(line) for line in (tmp_path / "spend.jsonl").read_text().splitlines()]
    kinds = [str(row.get("estimated", "paid"))[:8] for row in rows]
    # Each attempt's worst case is reserved before it is sent and released only after its own cost is logged.
    assert kinds == ["reserved", "worst ca", "released", "reserved", "paid", "released"]
    assert [row["cost_usd"] for row in _paid(tmp_path)] == [0.3, 0.01]
    assert providers.anthropic_spend() == pytest.approx(0.31)


def test_a_cut_attempt_is_in_the_callers_cost_once(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A $0.162 cut, then a $0.0021 reply: the caller records what the ledger holds, $0.1641, with the reply's own
    tokens, so a repricing of the tokens (``records.api_cost``) adds the cut from ``cut_cost_usd``, once."""
    sonnet = ARMS["claude-sonnet-5-5"]
    cut, reply = list_cost(sonnet, 1000, 0, 16000), list_cost(sonnet, 1000, 0, 10)  # _cut's tokens, and _flaky's
    assert (cut, reply) == (0.162, 0.0021)
    _api(monkeypatch, tmp_path, 0.0, {})
    _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(cut), True)], cost=reply)
    result = asyncio.run(call(sonnet, "s", "u", tag="t"))
    assert [row["cost_usd"] for row in _paid(tmp_path)] == [0.162, 0.0021]  # the ledger as before: a row each
    assert providers.anthropic_spend() == pytest.approx(0.1641) and result.cost_usd == pytest.approx(0.1641)
    assert result.meta["cut_attempts"] == 1 and result.meta["cut_cost_usd"] == pytest.approx(0.162)
    assert (result.input_tokens, result.output_tokens) == (1000, 10)  # measured: the reply's alone


def _started() -> Exception:
    return providers._AttemptFailed(ConnectionError("stream reset"), _cut(list_cost(ARMS["claude-sonnet-5-5"], 1000, 0, 16000)), True)


def _refused() -> Exception:
    return providers._AttemptFailed(ValueError("invalid request"), None, False)


@pytest.mark.parametrize("failures, raised, cuts", [
    ([_started, _refused], ValueError, 1),  # a cut, then a failure the API calls permanent
    ([_started] * 6, ConnectionError, 6),  # every attempt cut short
    ([_refused], ValueError, 0),  # no stream started, so nothing was billed and nothing is carried
])
def test_a_call_that_fails_after_a_cut_carries_its_cost(monkeypatch: pytest.MonkeyPatch, tmp_path, failures: list,
                                                         raised: type, cuts: int) -> None:
    one = list_cost(ARMS["claude-sonnet-5-5"], 1000, 0, 16000)
    _api(monkeypatch, tmp_path, 0.0, {})
    _flaky(monkeypatch, [failure() for failure in failures])
    with pytest.raises(raised) as caught:
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t"))
    assert providers.anthropic_spend() == pytest.approx(cuts * one)
    paid = getattr(caught.value, "result", None)
    if not cuts:
        assert paid is None
        return
    assert paid.cost_usd == pytest.approx(cuts * one)  # what the ledger holds, for the caller to record
    assert paid.meta == {"stop_reason": "cut short", "cut_attempts": cuts, "cut_cost_usd": pytest.approx(cuts * one)}
    assert (paid.input_tokens, paid.output_tokens) == (0, 0)  # none measured, so a repricing adds nothing twice


@pytest.mark.parametrize("where", ["backoff", "ledger"])
def test_an_interruption_or_a_ledger_error_after_a_cut_carries_its_cost(monkeypatch: pytest.MonkeyPatch, tmp_path,
                                                                         where: str) -> None:
    """Ctrl-C during the backoff after a cut, or a ledger read that fails before the next attempt: the cut's worst
    case, already in the ledger, still reaches the caller, which records it."""
    one = list_cost(ARMS["claude-sonnet-5-5"], 1000, 0, 16000)
    _api(monkeypatch, tmp_path, 0.0, {})
    _flaky(monkeypatch, [_started(), _refused()])
    raised: type = KeyboardInterrupt if where == "backoff" else OSError

    async def interrupted(seconds: float) -> None:
        raise KeyboardInterrupt

    if where == "backoff":
        monkeypatch.setattr(providers, "_sleep", interrupted)
    else:
        reads: list[int] = []

        def spend() -> float:  # the first attempt is admitted; the read before the second fails
            reads.append(1)
            if len(reads) > 1:
                raise OSError("the ledger could not be read")
            return 0.0

        monkeypatch.setattr(providers, "anthropic_spend", spend)
    with pytest.raises(raised) as caught:
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t"))
    assert caught.value.result.cost_usd == pytest.approx(one) and caught.value.result.meta["cut_attempts"] == 1


def test_a_cut_then_an_attempt_interrupted_mid_stream_carry_both(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A cut, then Ctrl-C after the retry's stream started: _call_anthropic logs the interrupted attempt at its worst
    case and marks the interruption with it, so the caller's carried cost is both, as the ledger's is."""
    one = list_cost(ARMS["claude-sonnet-5-5"], 1000, 0, 16000)
    _api(monkeypatch, tmp_path, 0.0, {})
    sent: list = []

    async def attempt(arm, system, user, max_tokens, timeout_s, tag=""):
        sent.append(tag)
        if len(sent) == 1:
            raise _started()
        stop = KeyboardInterrupt()
        cut = _cut(one)
        providers._log_spend(arm, cut, f"{tag} (interrupted)", providers.CUT_ESTIMATE)  # as the real attempt does
        setattr(stop, providers.CUT_LOGGED, True)
        setattr(stop, providers.CUT_RESULT, cut)
        raise stop

    async def no_wait(seconds: float) -> None:
        pass

    monkeypatch.setattr(providers, "_call_anthropic", attempt)
    monkeypatch.setattr(providers, "_sleep", no_wait)
    with pytest.raises(KeyboardInterrupt) as caught:
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t"))
    assert providers.anthropic_spend() == pytest.approx(2 * one)
    assert caught.value.result.cost_usd == pytest.approx(2 * one) and caught.value.result.meta["cut_attempts"] == 2


def test_a_cut_attempt_counts_against_other_calls_while_it_waits_to_retry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    one = worst_case_usd(sonnet, "s", "u", 16000)
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(one * 1.5))
    sent, _ = _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(one), True)])

    async def scenario() -> None:
        backing_off, resume = asyncio.Event(), asyncio.Event()

        async def gated(seconds: float) -> None:
            backing_off.set()
            await resume.wait()

        monkeypatch.setattr(providers, "_sleep", gated)
        first = asyncio.create_task(call(sonnet, "s", "u"))
        await asyncio.wait_for(backing_off.wait(), 5)  # a regression that stops retrying fails here, never hangs
        with pytest.raises(BudgetExceeded):  # the cut's worst case is already counted while the first waits
            await call(sonnet, "s", "u")
        assert len(sent) == 1
        resume.set()
        with pytest.raises(BudgetExceeded):
            await first

    asyncio.run(scenario())


def test_each_retry_is_admitted_against_the_ceiling_again(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    one = worst_case_usd(sonnet, "s", "u", 16000)
    monkeypatch.setenv("TREND_DEPTH_ANTHROPIC_CEILING_USD", str(one * 1.5))
    sent, _ = _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(one), True)])
    with pytest.raises(BudgetExceeded) as caught:
        asyncio.run(call(sonnet, "s", "u"))
    assert len(sent) == 1  # the cut attempt's worst case left no room for a second
    assert providers.anthropic_spend() == pytest.approx(one)
    assert caught.value.result.cost_usd == pytest.approx(one)  # and the refusal carries it to the caller's record


def test_a_call_whose_worst_case_does_not_fit_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    sonnet = ARMS["claude-sonnet-5-5"]
    one = worst_case_usd(sonnet, "s", "u", 16000)
    sent = _api(monkeypatch, tmp_path, 75.0 - one / 2, {"stop_reason": "end_turn"})  # spent is under the ceiling
    with pytest.raises(BudgetExceeded):
        asyncio.run(call(sonnet, "s", "u"))
    assert sent == []


def test_a_failure_the_api_calls_permanent_is_raised_without_a_retry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    sent, waits = _flaky(monkeypatch, [providers._AttemptFailed(ValueError("invalid request"), None, False)])
    with pytest.raises(ValueError, match="invalid request"):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    assert len(sent) == 1 and waits == []
    assert _paid(tmp_path) == []  # it never started, so nothing was billed or logged
    assert providers.anthropic_spend() == pytest.approx(0.0, abs=1e-9)  # and its reservation was released


@pytest.mark.parametrize("interruption", [asyncio.CancelledError, KeyboardInterrupt])
def test_an_interruption_whose_cost_is_unknown_keeps_its_worst_case(monkeypatch: pytest.MonkeyPatch, tmp_path, interruption) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    _flaky(monkeypatch, [interruption()])
    with pytest.raises(interruption):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    assert _paid(tmp_path) == []  # nothing says what it cost, so its reservation is not released
    assert providers.anthropic_spend() == pytest.approx(worst_case_usd(ARMS["claude-sonnet-5-5"], "s", "u", 16000))


@pytest.mark.parametrize("cut", [False, True])  # the attempt returned, or failed after it started
def test_an_interruption_before_the_cost_row_is_written_keeps_the_reservation(monkeypatch: pytest.MonkeyPatch, tmp_path, cut: bool) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    if cut:
        _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(0.3), True)])
    real_log = providers._log_spend

    def interrupted(arm, result, tag, estimated=""):
        raise KeyboardInterrupt  # a second Ctrl-C before the attempt's own row is on disk

    monkeypatch.setattr(providers, "_log_spend", interrupted)
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u"))
    monkeypatch.setattr(providers, "_log_spend", real_log)
    assert providers.anthropic_spend() == pytest.approx(worst_case_usd(ARMS["claude-sonnet-5-5"], "s", "u", 16000))


@pytest.mark.parametrize("backend", ["openai_compat", "claude_cli"])
def test_a_call_on_another_backend_is_logged_when_it_returns(monkeypatch: pytest.MonkeyPatch, tmp_path, backend: str) -> None:
    _api(monkeypatch, tmp_path, 0.0, {})
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    arm = ARMS["deepseek-flash" if backend == "openai_compat" else "claude-sonnet-5-5"]
    finish = [{"stop_reason": "end_turn"}, {"finish_reason": "length"}]

    async def reply(*args, **kwargs):
        return CallResult("{}", 1000, 0, 10, 0, 0.1, 0.02, backend, arm.model, finish.pop(0))

    monkeypatch.setattr(providers, "_call_openai_compat" if backend == "openai_compat" else "_call_claude_cli", reply)
    asyncio.run(call(arm, "s", "u", tag="t"))
    with pytest.raises(IncompleteReply):  # cut at its cap: still paid, so logged before it is raised
        asyncio.run(call(arm, "s", "u", tag="t"))
    rows = _paid(tmp_path)
    assert [(row["backend"], row["cost_usd"]) for row in rows] == [(backend, 0.02), (backend, 0.02)]


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


class _FakeStream:
    """The SDK's message stream as _call_anthropic uses it: a context manager, the final message, the snapshot."""

    def __init__(self, started: bool, final: Any = None, error: Optional[Exception] = None,
                 snapshot_stop: Optional[str] = None) -> None:
        self.started, self.final, self.error, self.snapshot_stop = started, final, error, snapshot_stop

    async def __aenter__(self) -> "_FakeStream":
        return self

    async def __aexit__(self, *exc_info: Any) -> bool:
        return False

    async def get_final_message(self) -> Any:
        if self.error is not None:
            raise self.error
        return self.final

    @property
    def current_message_snapshot(self) -> Any:
        assert self.started, "no message_start yet"
        return _message(self.snapshot_stop)


def _message(stop_reason: Optional[str]) -> Any:
    usage = types.SimpleNamespace(input_tokens=50000, output_tokens=1, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return types.SimpleNamespace(stop_reason=stop_reason, content=[types.SimpleNamespace(type="text", text="{")], usage=usage,
                                 model="claude-sonnet-5-5")


def _fake_sdk(monkeypatch: pytest.MonkeyPatch, stream: _FakeStream) -> Any:
    sdk = types.ModuleType("anthropic")
    sdk.APIConnectionError = type("APIConnectionError", (Exception,), {})
    sdk.APIStatusError = type("APIStatusError", (Exception,), {})
    sdk.AsyncAnthropic = lambda **options: types.SimpleNamespace(messages=types.SimpleNamespace(stream=lambda **request: stream))
    monkeypatch.setitem(sys.modules, "anthropic", sdk)
    return sdk


def _attempt_failure(arm: str = "claude-sonnet-5-5") -> Any:
    with pytest.raises(providers._AttemptFailed) as caught:
        asyncio.run(providers._call_anthropic(ARMS[arm], "s", "u", 64000, 60.0))
    return caught.value


def test_a_stream_that_ends_before_the_message_does_is_a_cut_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    # The SDK hands back the partial message, with no stop_reason and one output token, when a stream closes early.
    _fake_sdk(monkeypatch, _FakeStream(started=True, final=_message(None)))
    failure = _attempt_failure()
    assert failure.retryable and failure.cut is not None
    assert (failure.cut.input_tokens, failure.cut.output_tokens) == (50000, 64000)  # its worst case, not 1 token
    assert failure.cut.cost_usd == pytest.approx(list_cost(ARMS["claude-sonnet-5-5"], 50000, 0, 64000))


def test_a_stream_that_fails_after_it_starts_carries_its_worst_case(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _FakeStream(started=True)
    sdk = _fake_sdk(monkeypatch, stream)
    stream.error = sdk.APIConnectionError("connection reset mid-stream")
    failure = _attempt_failure()
    assert failure.retryable and failure.cut is not None and failure.cut.output_tokens == 64000


def test_a_finished_reply_whose_connection_then_failed_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _FakeStream(started=True, snapshot_stop="end_turn")  # message_delta arrived before the failure
    sdk = _fake_sdk(monkeypatch, stream)
    stream.error = sdk.APIConnectionError("peer closed connection after the message")
    result = asyncio.run(providers._call_anthropic(ARMS["claude-sonnet-5-5"], "s", "u", 64000, 60.0))
    assert result.meta["stop_reason"] == "end_turn" and result.output_tokens == 1  # its own usage, not a worst case


def test_an_attempt_interrupted_mid_stream_is_logged_at_its_worst_case(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {})
    monkeypatch.setattr(providers, "_call_anthropic", _REAL_ATTEMPT)
    _fake_sdk(monkeypatch, _FakeStream(started=True, error=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError) as caught:
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", max_tokens=64000, tag="t"))
    rows = _paid(tmp_path)
    assert [row["tag"] for row in rows] == ["t (interrupted)"] and rows[0]["output_tokens"] == 64000
    worst = list_cost(ARMS["claude-sonnet-5-5"], 50000, 0, 64000)
    assert providers.anthropic_spend() == pytest.approx(worst)
    assert caught.value.result.cost_usd == pytest.approx(worst)  # the caller carries what the ledger holds


def test_an_attempt_interrupted_before_it_started_keeps_its_reservation(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {})
    monkeypatch.setattr(providers, "_call_anthropic", _REAL_ATTEMPT)
    _fake_sdk(monkeypatch, _FakeStream(started=False, error=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", max_tokens=64000))
    assert _paid(tmp_path) == []
    assert providers.anthropic_spend() == pytest.approx(worst_case_usd(ARMS["claude-sonnet-5-5"], "s", "u", 64000))


def test_a_request_that_never_started_costs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_sdk(monkeypatch, _FakeStream(started=False, error=ValueError("invalid request")))
    failure = _attempt_failure()
    assert not failure.retryable and failure.cut is None


# The real SDK over a mock transport (no network), where it is installed: the harness's venv has it, CI does not.
_SSE_START = {"type": "message_start", "message": {
    "id": "m", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [], "stop_reason": None,
    "stop_sequence": None, "usage": {"input_tokens": 50000, "output_tokens": 1, "cache_read_input_tokens": 0,
                                     "cache_creation_input_tokens": 0}}}
_SSE_BODY = [{"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
             {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "{}"}}]
_SSE_DELTA = [{"type": "content_block_stop", "index": 0},
              {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 3000}}]
_SSE_STOP = [{"type": "message_stop"}]


def _sse(events: list) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


@pytest.mark.parametrize("first, cut, sent", [
    ("overloaded", False, 2),  # a 529 before the stream: retried, nothing billed
    ("error event", True, 2),  # an error event after message_start: logged at its worst case, retried
    ("reset", True, 2),  # the connection reset mid-stream
    ("ends early", True, 2),  # the stream closed cleanly before message_delta
    ("reset after the end", False, 1),  # message_delta arrived, then the connection failed: the reply is kept
])
def test_the_real_sdk_path_logs_what_each_failure_may_cost(monkeypatch: pytest.MonkeyPatch, tmp_path, first: str, cut: bool, sent: int) -> None:
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2")
    requests: list = []

    class Dropping(httpx.AsyncByteStream):
        def __init__(self, body: bytes) -> None:
            self.body = body

        async def __aiter__(self):
            yield self.body
            raise httpx.RemoteProtocolError("peer closed connection without sending complete message body")

    def handler(request):
        requests.append(request)
        stream = {"content-type": "text/event-stream"}
        if len(requests) > 1:
            return httpx.Response(200, headers=stream, content=_sse([_SSE_START, *_SSE_BODY, *_SSE_DELTA, *_SSE_STOP]))
        if first == "overloaded":
            return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
                                  headers={"retry-after": "0"})
        if first == "error event":
            error = {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
            return httpx.Response(200, headers=stream, content=_sse([_SSE_START, *_SSE_BODY, error]))
        if first == "reset":
            return httpx.Response(200, headers=stream, stream=Dropping(_sse([_SSE_START, *_SSE_BODY])))
        if first == "ends early":
            return httpx.Response(200, headers=stream, content=_sse([_SSE_START, *_SSE_BODY]))
        return httpx.Response(200, headers=stream, stream=Dropping(_sse([_SSE_START, *_SSE_BODY, *_SSE_DELTA])))

    real = anthropic.AsyncAnthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **options: real(
        api_key="test-key-not-real", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), **options))
    _api(monkeypatch, tmp_path, 0.0, {})
    monkeypatch.setattr(providers, "_call_anthropic", _REAL_ATTEMPT)

    async def no_wait(seconds: float) -> None:
        pass

    monkeypatch.setattr(providers, "_sleep", no_wait)
    result = asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", max_tokens=64000, tag="t"))
    assert len(requests) == sent and result.meta["stop_reason"] == "end_turn" and result.text == "{}"
    estimated = [row for row in _paid(tmp_path) if row.get("estimated")]
    assert len(estimated) == int(cut)
    if cut:
        assert (estimated[0]["input_tokens"], estimated[0]["output_tokens"]) == (50000, 64000)
    paid = [row for row in _paid(tmp_path) if not row.get("estimated")]
    assert len(paid) == 1 and paid[0]["output_tokens"] == 3000  # the reply's own usage, from its message_delta
    assert paid[0]["cost_usd"] == pytest.approx(list_cost(ARMS["claude-sonnet-5-5"], 50000, 0, 3000))


_REAL_ATTEMPT = providers._call_anthropic  # kept before any test replaces it


def _deepseek_overloaded(monkeypatch: pytest.MonkeyPatch, clock: list, overloads: int) -> None:
    """A fake OpenAI-compatible client: each request takes 4 s on ``clock``, and the first ``overloads`` answer 503."""

    class Overloaded(Exception):
        status_code = 503

    sent: list = []

    class Completions:
        async def create(self, **kwargs: Any) -> Any:
            sent.append(kwargs["model"])
            clock[0] += 4.0
            if len(sent) <= overloads:
                raise Overloaded("high demand")
            usage = types.SimpleNamespace(prompt_tokens=1000, completion_tokens=100, total_tokens=1100,
                                          prompt_cache_hit_tokens=0)
            choice = types.SimpleNamespace(message=types.SimpleNamespace(content="{}"), finish_reason="stop")
            return types.SimpleNamespace(usage=usage, choices=[choice], model="deepseek-flash")

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = types.SimpleNamespace(completions=Completions())

    async def backoff(seconds: float) -> None:
        clock[0] += seconds

    openai = types.ModuleType("openai")
    openai.AsyncOpenAI = Client
    monkeypatch.setitem(sys.modules, "openai", openai)
    monkeypatch.setattr(providers, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(providers, "_sleep", backoff)
    monkeypatch.setenv(ARMS["deepseek-flash"].key_env, "test-key-not-real")


@pytest.mark.parametrize("overloads, latency", [(0, 4.0), (1, 38.0), (2, 132.0)])
def test_an_overload_retry_counts_in_the_latency_a_reader_waits(monkeypatch: pytest.MonkeyPatch, tmp_path,
                                                                overloads: int, latency: float) -> None:
    """generate sums each call's latency and the report's percentiles read it, so a peak-hour run whose requests
    answer 503 must not look as fast as one whose did not: the failed requests and the backoff count."""
    clock = [100.0]
    _deepseek_overloaded(monkeypatch, clock, overloads)
    monkeypatch.setattr(providers, "SPEND_LOG", tmp_path / "spend.jsonl")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = asyncio.run(call(ARMS["deepseek-flash"], "s", "u", tag="t"))
    assert result.latency_s == pytest.approx(latency)  # 4 s a request, 30 s and then 90 s of backoff
    row = json.loads((tmp_path / "spend.jsonl").read_text())
    assert row["latency_s"] == pytest.approx(4.0)  # the ledger times the attempt, as each Claude attempt's row does
    if overloads:
        assert result.meta["retries"] == overloads and result.meta["attempt_latency_s"] == pytest.approx(4.0)
        assert row["retries"] == overloads and row["call_latency_s"] == pytest.approx(latency)
    else:
        assert "retries" not in result.meta and "attempt_latency_s" not in result.meta and "retries" not in row


def test_a_retried_claude_call_reports_the_whole_wait_and_keeps_the_attempt_time(monkeypatch: pytest.MonkeyPatch,
                                                                                tmp_path) -> None:
    _api(monkeypatch, tmp_path, 0.0, {"stop_reason": "end_turn"})
    clock = [0.0]
    sent, waits = _flaky(monkeypatch, [providers._AttemptFailed(ConnectionError("stream reset"), _cut(0.3), True)])

    async def backoff(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(providers, "time", types.SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(providers, "_sleep", backoff)
    result = asyncio.run(call(ARMS["claude-sonnet-5-5"], "s", "u", tag="t"))
    assert len(sent) == 2 and waits == [10.0]
    assert result.latency_s == pytest.approx(10.0) and result.meta["attempt_latency_s"] == pytest.approx(0.1)
