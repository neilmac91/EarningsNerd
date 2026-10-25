"""Model arms for the depth bake-off: one call, with measured usage, latency and list-price cost.

Each arm names a provider family (the judge never scores a pair containing its own family), a model and
a backend:

- ``openai_compat``: DeepSeek (``DEEPSEEK_API_KEY``) and Gemini (``GEMINI_API_KEY``, Google's
  OpenAI-compatible endpoint) through the ``openai`` SDK, JSON-object mode.
- ``anthropic``: Claude through the ``anthropic`` SDK when ``ANTHROPIC_API_KEY`` is set (``pip install
  anthropic``; the app does not depend on it). Only this path can turn thinking off (the ``-nothink`` arms).
- ``claude_cli``: otherwise Claude through ``claude -p`` (the repository's judge pattern,
  ``evals/judge.py::_judge_via_cli``): Claude Code's system prompt is replaced, tools and MCP are off, no
  session persists, and it runs from a temporary directory. It calls the first-party API; its usage and
  ``total_cost_usd`` (list price) are recorded as reported, including the CLI's small fixed wrapper.

Prices are USD per million tokens, verified 2026-10-24: DeepSeek's pricing page (off-peak; peak doubles
them), Google's Gemini API pricing page (standard paid tier, the rates in force through November 2026),
and the Anthropic list prices in the claude-api skill's model table.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class Arm:
    name: str
    family: str  # deepseek | gemini | claude
    model: str
    backend: str  # openai_compat | anthropic | claude_cli (resolved at call time for claude)
    input_price: float
    output_price: float
    cached_input_price: float
    base_url: str = ""
    key_env: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    effort: str = ""
    thinking: str = ""  # Claude API only: "disabled" (Haiku 5.5) or "between_tools" (Sonnet 5.5); empty = model default
    price_note: str = ""
    # (prompt tokens above which, input, output, cache-read price): Haiku 5.5 bills a longer prompt at a higher tier
    long_prompt: Optional[tuple[int, float, float, float]] = None


ARMS: dict[str, Arm] = {
    "deepseek-flash": Arm(
        "deepseek-flash", "deepseek", "deepseek-flash", "openai_compat", 0.15, 0.60, 0.003,
        base_url="https://api.deepseek.com/v1", key_env="DEEPSEEK_API_KEY",
        extra={"extra_body": {"thinking": {"type": "disabled"}}, "temperature": 0.2},
        price_note="off-peak; peak (01-04, 06-10 UTC weekdays) is 2x",
    ),
    "deepseek-flash-thinking": Arm(
        "deepseek-flash-thinking", "deepseek", "deepseek-flash", "openai_compat", 0.15, 0.60, 0.003,
        base_url="https://api.deepseek.com/v1", key_env="DEEPSEEK_API_KEY",
        extra={"extra_body": {"thinking": {"type": "enabled"}}},
        price_note="off-peak; peak is 2x; thinking tokens bill as output",
    ),
    # A judge and auditor only, never a generator: V4 Pro service continues at its own tariff (ADR-0008 addendum).
    "deepseek-v4-pro": Arm(  # ADR-0008
        "deepseek-v4-pro", "deepseek", "deepseek-v4-pro", "openai_compat", 0.66, 1.98, 0.022,  # ADR-0008
        base_url="https://api.deepseek.com/v1", key_env="DEEPSEEK_API_KEY",
        extra={"extra_body": {"thinking": {"type": "disabled"}}, "temperature": 0.2},
        price_note="off-peak; peak is 2x",
    ),
    "gemini-4-argon": Arm(
        "gemini-4-argon", "gemini", "gemini-4-argon", "openai_compat", 2.00, 10.00, 0.10,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/", key_env="GEMINI_API_KEY",
        price_note="through 2026-11-30; $4/$20 from 2026-12-01",
    ),
    "gemini-3.8-flash": Arm(
        "gemini-3.8-flash", "gemini", "gemini-3.8-flash", "openai_compat", 0.75, 3.75, 0.075,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/", key_env="GEMINI_API_KEY",
        price_note="through 2026-12-31; $1.50/$7.50 from 2027-01-01",
    ),
    "gemma-4-31b": Arm(
        # Google's open-weights model on the Gemini API free tier: a judge outside the Claude and DeepSeek
        # families when the Gemini quota is spent. Free of charge there; no paid list price is used.
        "gemma-4-31b", "gemini", "gemma-4-31b-it", "openai_compat", 0.0, 0.0, 0.0,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/", key_env="GEMINI_API_KEY",
        price_note="free tier only",
    ),
    "claude-sonnet-5-5": Arm(
        "claude-sonnet-5-5", "claude", "claude-sonnet-5-5", "claude", 2.00, 10.00, 0.20, effort="medium",
    ),
    "claude-haiku-5-5": Arm(
        "claude-haiku-5-5", "claude", "claude-haiku-5-5", "claude", 0.10, 0.50, 0.01, effort="medium",
        long_prompt=(100_000, 0.50, 2.50, 0.05),
        price_note="prompts up to 100K tokens; $0.50/$2.50 above",
    ),
    "claude-haiku-5-5-low": Arm(
        "claude-haiku-5-5-low", "claude", "claude-haiku-5-5", "claude", 0.10, 0.50, 0.01, effort="low",
        long_prompt=(100_000, 0.50, 2.50, 0.05),
        price_note="prompts up to 100K tokens; $0.50/$2.50 above",
    ),
    # Thinking off, which the Claude API allows and the CLI cannot express: Haiku 5.5 takes "disabled" at effort
    # high or below; Sonnet 5.5 rejects "disabled" and takes "between_tools", its lowest setting.
    "claude-haiku-5-5-nothink": Arm(
        "claude-haiku-5-5-nothink", "claude", "claude-haiku-5-5", "claude", 0.10, 0.50, 0.01, effort="low",
        thinking="disabled", price_note="prompts up to 100K tokens; $0.50/$2.50 above",
        long_prompt=(100_000, 0.50, 2.50, 0.05),
    ),
    "claude-sonnet-5-5-nothink": Arm(
        "claude-sonnet-5-5-nothink", "claude", "claude-sonnet-5-5", "claude", 2.00, 10.00, 0.20, effort="medium",
        thinking="between_tools",
    ),
    "claude-opus-5-5": Arm(
        "claude-opus-5-5", "claude", "claude-opus-5-5", "claude", 4.00, 20.00, 0.20, effort="medium",
    ),
}


@dataclass
class CallResult:
    text: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_s: float
    cost_usd: float
    backend: str
    model_served: str
    meta: dict[str, Any] = field(default_factory=dict)


CACHE_WRITE_PREMIUM = 1.25  # a 5-minute cache write bills at 1.25x the input price


def list_cost(arm: Arm, input_tokens: int, cached: int, output_tokens: int, cache_write: int = 0) -> float:
    """List price of one call. ``input_tokens`` is the whole prompt: uncached, cache-read and cache-written."""
    input_price, output_price, cached_price = arm.input_price, arm.output_price, arm.cached_input_price
    if arm.long_prompt and input_tokens > arm.long_prompt[0]:
        input_price, output_price, cached_price = arm.long_prompt[1:]
    uncached = max(input_tokens - cached - cache_write, 0)
    return round(uncached / 1e6 * input_price + cached / 1e6 * cached_price
                 + cache_write / 1e6 * input_price * CACHE_WRITE_PREMIUM + output_tokens / 1e6 * output_price, 6)


class IncompleteReply(RuntimeError):
    """The reply stopped at its token cap. A larger cap is the fix, so it is a run error (retried), not an outcome.
    ``result`` is the paid call, so the caller can record what it cost."""

    def __init__(self, message: str, result: "CallResult") -> None:
        super().__init__(message)
        self.result = result


class BudgetExceeded(RuntimeError):
    """The Anthropic spend recorded in the ledger leaves no room under the ceiling; nothing was sent."""


class KeyBusy(BudgetExceeded):
    """Another harness process in this checkout is spending on the key; nothing was sent."""


class LedgerTorn(RuntimeError):
    """A ledger row was cut short and may be a Claude API call whose cost is lost; nothing is sent until it is repaired."""


# Every paid call is appended here, a stream cut short included: the spend the records alone would miss.
SPEND_LOG = Path(os.environ.get("TREND_DEPTH_SPEND_LOG")
                 or Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10" / "runs" / "spend.jsonl")


def anthropic_ceiling_usd() -> float:
    return float(os.environ.get("TREND_DEPTH_ANTHROPIC_CEILING_USD") or 75.0)


_TORN_BACKEND = re.compile(r'"backend": "([a-z_]+)"')
_TORN_COST = re.compile(r'"cost_usd": (-?[0-9.]+(?:[eE][-+]?[0-9]+)?)[,}]')


def anthropic_spend() -> float:
    """USD of Claude API calls recorded in the ledger (CLI calls bill the subscription, not the key).

    A row cut short by a crash is read for what it kept, since rows start with their backend and cost: it is
    skipped when it names another backend and counted when its cost survived. A torn row that may be a Claude
    API call with its cost lost raises ``LedgerTorn``, so the ceiling never works from an undercount.
    """
    if not SPEND_LOG.exists():
        return 0.0
    total = 0.0
    for number, line in enumerate(SPEND_LOG.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            backend, cost = _TORN_BACKEND.search(line), _TORN_COST.search(line)
            if backend and backend.group(1) != "anthropic":
                continue
            if backend and cost:
                total += float(cost.group(1))
                continue
            raise LedgerTorn(f"{SPEND_LOG} line {number} was cut short and may be a Claude API call whose cost is lost: "
                             "give it the cost the Anthropic Console shows, or delete it if it was not one; nothing was sent") from None
        if isinstance(row, dict) and row.get("backend") == "anthropic":
            total += float(row.get("cost_usd") or 0)
    return total


_in_flight_usd = 0.0  # worst-case cost of the Claude API attempts this process has sent and not yet settled
_key_lock: Optional[tuple[Path, Any]] = None  # the ledger this process holds, and the open file holding it


def worst_case_usd(arm: "Arm", system: str, user: str, max_tokens: int) -> float:
    """An upper bound on one call's cost at list price: the prompt at one token per UTF-8 byte (a byte-level
    tokenizer never needs more; these packs measure about 2.2 characters a token) plus 64 tokens of framing,
    and every allowed output token. Haiku's long-prompt tier is chosen from the same bound."""
    prompt_tokens = len(system.encode()) + len(user.encode()) + 64
    return list_cost(arm, prompt_tokens, 0, max_tokens)


def _hold_key_lock() -> None:
    """Hold an exclusive lock on the ledger for the rest of this process. Calls in flight are reserved in this
    process alone, so two processes spending on the key at once could pass the ceiling between them: the second
    is refused instead. (Another checkout keeps a ledger of its own; the Console's spend limit covers that.)"""
    global _key_lock
    if _key_lock is not None and _key_lock[0] == SPEND_LOG:
        return
    import fcntl

    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    handle = SPEND_LOG.open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise KeyBusy(f"another harness process is spending on the key from {SPEND_LOG}: run one Claude API step at "
                      "a time; nothing was sent") from None
    if _key_lock is not None:
        _key_lock[1].close()
    _key_lock = (SPEND_LOG, handle)


def _log_spend(arm: Arm, result: "CallResult", tag: str, estimated: str = "") -> None:
    # Backend and cost come first, so a row cut short by a crash most likely still says what it cost.
    row = {"backend": result.backend, "cost_usd": result.cost_usd, "arm": arm.name, "tag": tag,
           "model_served": result.model_served, "input_tokens": result.input_tokens,
           "cached_input_tokens": result.cached_input_tokens, "output_tokens": result.output_tokens,
           "latency_s": result.latency_s}
    if estimated:
        row["estimated"] = estimated
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a+b") as handle:  # one short row per write; appends from concurrent calls do not interleave
        lead = b""
        if handle.seek(0, os.SEEK_END):
            handle.seek(-1, os.SEEK_END)
            lead = b"" if handle.read(1) == b"\n" else b"\n"  # a row cut short keeps its own line
        handle.write(lead + (json.dumps(row) + "\n").encode())


async def call(arm: Arm, system: str, user: str, *, max_tokens: int = 16000, json_mode: bool = True,
               timeout_s: float = 600.0, tag: str = "") -> CallResult:
    """One call. ``max_tokens`` is the cap on everything the model writes, thinking included; ``tag`` names the
    caller in the spend ledger. A Claude API attempt is sent only when its worst case fits under the ceiling."""
    if arm.backend == "openai_compat":
        result = await _call_openai_compat(arm, system, user, max_tokens, json_mode, timeout_s)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        result = await _call_anthropic_metered(arm, system, user, max_tokens, timeout_s, tag)
    elif arm.thinking:
        raise RuntimeError(f"{arm.name}: thinking={arm.thinking!r} needs the Claude API (ANTHROPIC_API_KEY); the CLI cannot set it")
    else:
        result = await _call_claude_cli(arm, system, user, timeout_s)
    _log_spend(arm, result, tag)
    if result.meta.get("stop_reason") == "max_tokens" or result.meta.get("finish_reason") == "length":
        raise IncompleteReply(f"{arm.name}: the reply stopped at max_tokens={max_tokens} (${result.cost_usd:.4f} spent)", result)
    return result


async def _call_openai_compat(arm: Arm, system: str, user: str, max_tokens: int, json_mode: bool, timeout_s: float) -> CallResult:
    from openai import AsyncOpenAI

    key = os.environ.get(arm.key_env, "")
    if not key:
        raise RuntimeError(f"{arm.name}: {arm.key_env} is not set")
    client = AsyncOpenAI(api_key=key, base_url=arm.base_url, timeout=timeout_s, max_retries=2)
    kwargs: dict[str, Any] = {
        "model": arm.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    for key_name, value in arm.extra.items():
        kwargs[key_name] = value
    started = time.monotonic()
    response = None
    for wait in (0, 30, 90, 180):
        # Gemini's free tier answers 503 "high demand" for minutes at a time; DeepSeek rarely needs this.
        if wait:
            await asyncio.sleep(wait)
            started = time.monotonic()
        try:
            response = await client.chat.completions.create(**kwargs)
            break
        except Exception as exc:  # noqa: BLE001 - retried only for overload and rate limits, else re-raised
            status = getattr(exc, "status_code", None)
            daily_quota = status == 429 and "per day" in str(exc).lower()  # resets at midnight Pacific; waiting is futile
            if status not in (429, 500, 502, 503, 504) or wait == 180 or daily_quota:
                raise
    latency = time.monotonic() - started
    usage = response.usage
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    cached = getattr(usage, "prompt_cache_hit_tokens", None)
    if cached is None:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) if details else 0
    completion_details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(completion_details, "reasoning_tokens", 0) if completion_details else 0
    reasoning = reasoning or 0
    # Gemini's compatibility layer leaves thinking out of completion_tokens and counts it only in
    # total_tokens (measured 2026-10-24: 11 prompt + 8 completion, total 156); thinking bills as output.
    total = getattr(usage, "total_tokens", 0) or 0
    billed_output = completion
    if arm.family == "gemini" and total > prompt + completion:
        reasoning = total - prompt - completion
        billed_output = total - prompt
    text = response.choices[0].message.content or ""
    return CallResult(text, prompt, cached or 0, billed_output, reasoning, round(latency, 3),
                      list_cost(arm, prompt, cached or 0, billed_output), "openai_compat",
                      getattr(response, "model", arm.model),
                      {"finish_reason": response.choices[0].finish_reason,
                       "total_tokens": getattr(usage, "total_tokens", None)})


def anthropic_request(arm: Arm, system: str, user: str, max_tokens: int) -> dict[str, Any]:
    """The Messages API request for a Claude arm, kept free of the SDK so tests can pin it.

    Claude 5.5 models think adaptively by default, and the depth is set by ``output_config.effort``; the CLI
    arms run the same way with ``--effort``. No sampling parameters are sent: Haiku 5.5 rejects any
    non-default temperature. ``max_tokens`` is the caller's cap on thinking and answer together, so callers leave
    room for thinking (generation asks for 64,000; Haiku 5.5 at medium effort has written 43,000).
    """
    request: dict[str, Any] = {
        "model": arm.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": arm.effort or "medium"},
    }
    if arm.thinking:
        request["thinking"] = {"type": arm.thinking}
    return request


_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504, 529}
_RETRYABLE_TYPES = {"overloaded_error", "api_error", "rate_limit_error"}


def _retryable(exc: Exception) -> bool:
    import anthropic

    if isinstance(exc, anthropic.APIConnectionError):  # network failures and timeouts
        return True
    if type(exc).__module__.split(".")[0] in ("httpx", "httpx2", "httpcore"):  # a transport error raised mid-stream
        return True
    if isinstance(exc, anthropic.APIStatusError):
        body = exc.body if isinstance(exc.body, dict) else {}
        kind = (body.get("error") or {}).get("type") if isinstance(body.get("error"), dict) else None
        return exc.status_code in _RETRYABLE_STATUS or kind in _RETRYABLE_TYPES  # a mid-stream error event too
    return False


def _backoff_s(error: Exception, attempt: int) -> float:
    response = getattr(error, "response", None)
    after = response.headers.get("retry-after") if response is not None else None
    if after and after.replace(".", "", 1).isdigit():
        return min(float(after), 120.0)
    return min(120.0, 10.0 * 2 ** attempt)


_sleep = asyncio.sleep  # the retry backoff's clock (tests replace it)


class _AttemptFailed(Exception):
    """One API attempt failed. ``cut`` is its worst-case cost when its stream had started, since it may be billed."""

    def __init__(self, error: Exception, cut: Optional[CallResult], retryable: bool) -> None:
        super().__init__(str(error))
        self.error, self.cut, self.retryable = error, cut, retryable


CUT_ESTIMATE = "worst case: the stream failed after it started, so the output so far is not known"


async def _call_anthropic_metered(arm: Arm, system: str, user: str, max_tokens: int, timeout_s: float, tag: str) -> CallResult:
    """Up to six attempts, each admitted against the ceiling on its own, with its worst case reserved while it is
    in flight. An attempt whose stream started and then failed may be billed, so it is logged at its worst case
    before the next attempt is admitted: the ledger can overstate what the key spent, never understate it."""
    global _in_flight_usd
    _hold_key_lock()
    reserve = worst_case_usd(arm, system, user, max_tokens)
    cut_attempts = 0
    for attempt in range(6):
        spent, ceiling = anthropic_spend(), anthropic_ceiling_usd()
        if spent + _in_flight_usd + reserve > ceiling:
            raise BudgetExceeded(f"Anthropic spend ${spent:.2f}, with ${_in_flight_usd:.2f} reserved for calls in flight, "
                                 f"leaves no room for this call's worst case of ${reserve:.2f} under the ${ceiling:.2f} "
                                 "ceiling (TREND_DEPTH_ANTHROPIC_CEILING_USD); nothing was sent")
        _in_flight_usd += reserve
        failure: Optional[_AttemptFailed] = None
        try:
            result = await _call_anthropic(arm, system, user, max_tokens, timeout_s, tag)
        except _AttemptFailed as exc:
            failure = exc
        finally:
            _in_flight_usd -= reserve
        if failure is None:
            result.meta.update({"retries": attempt, "cut_attempts": cut_attempts})
            return result
        if failure.cut is not None:
            cut_attempts += 1
            _log_spend(arm, failure.cut, f"{tag} (attempt {attempt + 1}, cut short)", CUT_ESTIMATE)
        if attempt == 5 or not failure.retryable:
            raise failure.error
        await _sleep(_backoff_s(failure.error, attempt))
    raise AssertionError("unreachable: the last attempt returns or raises")


def _cut_cost(arm: Arm, stream: Any, max_tokens: int, elapsed: float) -> Optional[CallResult]:
    """A failed attempt's worst case, once its stream has started: the prompt as message_start reported it, and
    the full ``max_tokens`` of output, because usage reports the output only when the message ends."""
    try:
        snapshot = stream.current_message_snapshot if stream is not None else None
    except AssertionError:  # no message_start yet: the request never started
        snapshot = None
    if snapshot is None:
        return None
    usage = snapshot.usage
    read, write = usage.cache_read_input_tokens or 0, usage.cache_creation_input_tokens or 0
    input_tokens = (usage.input_tokens or 0) + read + write
    return CallResult("", input_tokens, read, max_tokens, 0, round(elapsed, 3),
                      list_cost(arm, input_tokens, read, max_tokens, write), "anthropic", snapshot.model,
                      {"stop_reason": "cut short", "cache_creation_input_tokens": write})


async def _call_anthropic(arm: Arm, system: str, user: str, max_tokens: int, timeout_s: float, tag: str = "") -> CallResult:
    """One attempt; ``_call_anthropic_metered`` retries. A failure is raised as ``_AttemptFailed``. An interruption
    (Ctrl-C, a cancelled task) is not retried, but an attempt it cut short is logged before it propagates."""
    import anthropic

    client = anthropic.AsyncAnthropic(timeout=timeout_s, max_retries=0)
    request = anthropic_request(arm, system, user, max_tokens)
    started = time.monotonic()
    stream = None
    try:
        async with client.messages.stream(**request) as stream:
            message = await stream.get_final_message()
    except Exception as exc:  # noqa: BLE001 - re-raised with what the attempt may have cost
        raise _AttemptFailed(exc, _cut_cost(arm, stream, max_tokens, time.monotonic() - started), _retryable(exc)) from exc
    except BaseException:
        cut = _cut_cost(arm, stream, max_tokens, time.monotonic() - started)
        if cut is not None:
            _log_spend(arm, cut, f"{tag} (interrupted)", CUT_ESTIMATE)
        raise
    if message.stop_reason is None:  # the stream ended before message_stop: a partial reply, its output uncounted
        raise _AttemptFailed(RuntimeError("the stream ended before the message did"),
                             _cut_cost(arm, stream, max_tokens, time.monotonic() - started), True)
    # The measured latency is this attempt's alone (as on openai_compat).
    latency = time.monotonic() - started
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = message.usage
    cache_read = usage.cache_read_input_tokens or 0
    cache_write = usage.cache_creation_input_tokens or 0
    input_tokens = (usage.input_tokens or 0) + cache_read + cache_write
    output_tokens = usage.output_tokens or 0  # includes thinking, which bills as output
    details = getattr(usage, "output_tokens_details", None)
    thinking = getattr(details, "thinking_tokens", 0) or 0
    return CallResult(text, input_tokens, cache_read, output_tokens, thinking, round(latency, 3),
                      list_cost(arm, input_tokens, cache_read, output_tokens, cache_write), "anthropic", message.model,
                      {"stop_reason": message.stop_reason, "cache_creation_input_tokens": cache_write,
                       "thinking_blocks": sum(1 for block in message.content if block.type == "thinking"),
                       # premiums list_cost cannot see (inference region, speed) are recorded for the reader
                       **{key: getattr(usage, key) for key in ("service_tier", "inference_geo", "speed")
                          if getattr(usage, key, None) is not None}})


async def _call_claude_cli(arm: Arm, system: str, user: str, timeout_s: float) -> CallResult:
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY",)}
    args = ["claude", "-p", "--model", arm.model, "--output-format", "json", "--system-prompt", system,
            "--tools", "", "--strict-mcp-config", "--no-session-persistence"]
    if arm.effort:
        args += ["--effort", arm.effort]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="trend-depth-cli-") as cwd:
        # The prompt goes in through a file, not a pipe: the CLI gives up on stdin after 3 s, and a pipe write
        # waits on this event loop, which a burst of synchronous pack loading can hold longer than that.
        prompt_path = Path(cwd) / "prompt.txt"
        prompt_path.write_text(user, encoding="utf-8")
        with prompt_path.open("rb") as stdin:
            proc = await asyncio.create_subprocess_exec(
                *args, stdin=stdin, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
            )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except BaseException:
            proc.kill()
            await proc.wait()
            raise
    latency = time.monotonic() - started
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI exit {proc.returncode}: {err.decode('utf-8', 'replace')[:300]}")
    outer = json.loads(out.decode("utf-8"))
    if outer.get("is_error") or outer.get("subtype") not in (None, "success"):
        raise RuntimeError(f"claude CLI error result: {str(outer)[:300]}")
    usage = outer.get("usage") or {}
    cached = int(usage.get("cache_read_input_tokens") or 0)
    input_tokens = int(usage.get("input_tokens") or 0) + cached + int(usage.get("cache_creation_input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    model_usage = outer.get("modelUsage") or {}
    served = next(iter(model_usage), arm.model)
    cost = float(outer.get("total_cost_usd") or list_cost(arm, input_tokens, cached, output_tokens))
    api_ms = outer.get("duration_api_ms")
    return CallResult(str(outer.get("result", "")), input_tokens, cached, output_tokens,
                      int((usage.get("output_tokens_details") or {}).get("thinking_tokens") or 0),
                      round(latency, 3), round(cost, 6), "claude_cli", served,
                      {"duration_api_ms": api_ms, "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
                       "list_cost_usd": list_cost(arm, input_tokens, cached, output_tokens)})


def parse_json_object(text: str) -> Optional[dict[str, Any]]:
    """The first complete JSON object in a reply (models sometimes wrap it in a code fence)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        stripped = stripped.rsplit("```", 1)[0]
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end > start:
            try:
                value = json.loads(stripped[start:end + 1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def labels_by_number(entries: Any) -> dict[int, dict[str, Any]]:
    """An auditor's numbered labels; an entry whose ``n`` is not a whole number is skipped, never fatal."""
    out: dict[int, dict[str, Any]] = {}
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            try:
                out[int(str(entry.get("n", "")).strip().rstrip("."))] = entry
            except ValueError:
                continue
    return out


SYSTEM_RANK = ["current", *ARMS]


def canonical_pair(x: str, y: str) -> tuple[str, str]:
    """A judged pair's fixed orientation (current first, then the ARMS order), so a cached verdict is found
    whatever order --systems lists the systems in. Every eval-v1 verdict file already follows it."""
    rank = {name: i for i, name in enumerate(SYSTEM_RANK)}
    return (x, y) if rank.get(x, len(rank)) <= rank.get(y, len(rank)) else (y, x)


def max_tokens_for(arm: Arm) -> int:
    """The generation cap, thinking included: Claude 5.5 thinks adaptively, and Haiku at medium effort has written
    43,000 tokens for one analysis; the other providers answer in under 3,000."""
    return 64000 if arm.family == "claude" else 16000

