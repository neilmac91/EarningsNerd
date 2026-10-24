"""Model arms for the depth bake-off: one call, with measured usage, latency and list-price cost.

Each arm names a provider family (the judge never scores a pair containing its own family), a model and
a backend:

- ``openai_compat``: DeepSeek (``DEEPSEEK_API_KEY``) and Gemini (``GEMINI_API_KEY``, Google's
  OpenAI-compatible endpoint) through the ``openai`` SDK, JSON-object mode.
- ``anthropic``: Claude through the ``anthropic`` SDK when ``ANTHROPIC_API_KEY`` is set.
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
    price_note: str = ""


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
        price_note="prompts up to 100K tokens; $0.50/$2.50 above",
    ),
    "claude-haiku-5-5-low": Arm(
        "claude-haiku-5-5-low", "claude", "claude-haiku-5-5", "claude", 0.10, 0.50, 0.01, effort="low",
        price_note="prompts up to 100K tokens; $0.50/$2.50 above",
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


def list_cost(arm: Arm, input_tokens: int, cached: int, output_tokens: int) -> float:
    uncached = max(input_tokens - cached, 0)
    return round(uncached / 1e6 * arm.input_price + cached / 1e6 * arm.cached_input_price
                 + output_tokens / 1e6 * arm.output_price, 6)


async def call(arm: Arm, system: str, user: str, *, max_tokens: int = 16000, json_mode: bool = True,
               timeout_s: float = 600.0) -> CallResult:
    if arm.backend == "openai_compat":
        return await _call_openai_compat(arm, system, user, max_tokens, json_mode, timeout_s)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return await _call_anthropic(arm, system, user, max_tokens, timeout_s)
    return await _call_claude_cli(arm, system, user, timeout_s)


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


async def _call_anthropic(arm: Arm, system: str, user: str, max_tokens: int, timeout_s: float) -> CallResult:
    import anthropic

    client = anthropic.AsyncAnthropic(timeout=timeout_s)
    started = time.monotonic()
    async with client.messages.stream(
        model=arm.model,
        max_tokens=max(max_tokens, 32000),
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": arm.effort or "medium"},
    ) as stream:
        message = await stream.get_final_message()
    latency = time.monotonic() - started
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = message.usage
    input_tokens = (usage.input_tokens or 0) + (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
    cached = usage.cache_read_input_tokens or 0
    return CallResult(text, input_tokens, cached, usage.output_tokens or 0, 0, round(latency, 3),
                      list_cost(arm, input_tokens, cached, usage.output_tokens or 0), "anthropic", message.model,
                      {"stop_reason": message.stop_reason})


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
