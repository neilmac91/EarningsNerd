"""Model registry and provider dispatch for the bake-off.

Candidates span providers. Claude is called through the official `anthropic` SDK (native
structured outputs); the OpenAI-compatible providers (Google AI Studio / Gemini, Qwen,
Kimi/Moonshot, DeepSeek) are called through the `openai` SDK with per-provider base URLs.

PRICING NOTE: per-1M-token prices are used only for the secondary cost column, not the
quality verdict. Claude prices are VERIFIED against the claude-api skill (cache 2026-05-26).
Non-Claude prices are marked UNVERIFIED — confirm against each provider's pricing page before
relying on the cost numbers. Override any price via the registry below.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from evals.schema import EVAL_SUMMARY_JSON_SCHEMA


@dataclass
class ModelConfig:
    name: str  # registry key, e.g. "claude-opus"
    provider: str  # "anthropic" | "openai_compat"
    model_id: str
    input_price_per_1m: float
    output_price_per_1m: float
    price_verified: bool = False
    # openai_compat only:
    base_url_env: Optional[str] = None  # env var holding the base URL
    base_url_default: Optional[str] = None
    api_key_env: Optional[str] = None
    json_mode: str = "schema"  # "schema" | "object" | "none"


# Registry. `baseline` is handled specially by the runner (current openai_service pipeline);
# it is listed here only for pricing/reporting symmetry.
REGISTRY: Dict[str, ModelConfig] = {
    "baseline": ModelConfig(
        name="baseline", provider="openai_compat",
        model_id=os.environ.get("AI_DEFAULT_MODEL", "gemini-3.1-pro-preview"),
        input_price_per_1m=2.0, output_price_per_1m=12.0, price_verified=False,
        base_url_env="OPENAI_BASE_URL", api_key_env="OPENAI_API_KEY", json_mode="none",
    ),
    "gemini-json": ModelConfig(
        name="gemini-json", provider="openai_compat", model_id="gemini-3.1-pro-preview",
        input_price_per_1m=2.0, output_price_per_1m=12.0, price_verified=False,
        base_url_env="OPENAI_BASE_URL",
        base_url_default="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="OPENAI_API_KEY", json_mode="schema",
    ),
    "claude-sonnet": ModelConfig(
        name="claude-sonnet", provider="anthropic", model_id="claude-sonnet-4-6",
        input_price_per_1m=3.0, output_price_per_1m=15.0, price_verified=True,
        api_key_env="ANTHROPIC_API_KEY", json_mode="schema",
    ),
    "claude-opus": ModelConfig(
        name="claude-opus", provider="anthropic", model_id="claude-opus-4-8",
        input_price_per_1m=5.0, output_price_per_1m=25.0, price_verified=True,
        api_key_env="ANTHROPIC_API_KEY", json_mode="schema",
    ),
    "qwen": ModelConfig(
        name="qwen", provider="openai_compat", model_id="qwen-max",
        input_price_per_1m=1.6, output_price_per_1m=6.4, price_verified=False,
        base_url_env="QWEN_BASE_URL",
        base_url_default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        api_key_env="QWEN_API_KEY", json_mode="object",
    ),
    "kimi": ModelConfig(
        name="kimi", provider="openai_compat", model_id="kimi-k2-0905-preview",
        input_price_per_1m=0.6, output_price_per_1m=2.5, price_verified=False,
        base_url_env="KIMI_BASE_URL",
        base_url_default="https://api.moonshot.ai/v1",
        api_key_env="KIMI_API_KEY", json_mode="object",
    ),
    "deepseek": ModelConfig(
        name="deepseek", provider="openai_compat", model_id="deepseek-chat",
        input_price_per_1m=0.28, output_price_per_1m=1.10, price_verified=False,
        base_url_env="DEEPSEEK_BASE_URL",
        base_url_default="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY", json_mode="object",
    ),
}


def cost_usd(cfg: ModelConfig, input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens / 1e6 * cfg.input_price_per_1m
        + output_tokens / 1e6 * cfg.output_price_per_1m,
        6,
    )


async def call_model(
    cfg: ModelConfig, system: str, user: str, max_tokens: int = 4096
) -> Tuple[str, int, int, float]:
    """Run one structured-extraction request. Returns (raw_text, in_tokens, out_tokens, seconds)."""
    started = time.time()
    if cfg.provider == "anthropic":
        raw, in_tok, out_tok = await _call_anthropic(cfg, system, user, max_tokens)
    else:
        raw, in_tok, out_tok = await _call_openai_compat(cfg, system, user, max_tokens)
    return raw, in_tok, out_tok, round(time.time() - started, 3)


async def _call_openai_compat(
    cfg: ModelConfig, system: str, user: str, max_tokens: int
) -> Tuple[str, int, int]:
    from openai import AsyncOpenAI

    base_url = os.environ.get(cfg.base_url_env or "", "") or cfg.base_url_default
    api_key = os.environ.get(cfg.api_key_env or "", "")
    if not api_key:
        raise RuntimeError(f"{cfg.name}: missing API key (set {cfg.api_key_env})")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    kwargs: Dict[str, Any] = {
        "model": cfg.model_id,
        "max_tokens": max_tokens,
        "temperature": 0.2,  # pinned low for extraction
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if cfg.json_mode == "schema":
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "eval_summary", "schema": EVAL_SUMMARY_JSON_SCHEMA, "strict": True},
        }
    elif cfg.json_mode == "object":
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = await client.chat.completions.create(**kwargs)
    except Exception:
        # Some OpenAI-compat shims reject json_schema; retry once with plain json_object.
        if cfg.json_mode == "schema":
            kwargs["response_format"] = {"type": "json_object"}
            resp = await client.chat.completions.create(**kwargs)
        else:
            raise
    raw = resp.choices[0].message.content or ""
    usage = resp.usage
    return raw, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0


async def _call_anthropic(
    cfg: ModelConfig, system: str, user: str, max_tokens: int
) -> Tuple[str, int, int]:
    try:
        import anthropic  # lazy: not a core dependency. `pip install anthropic` to bake off Claude.
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "anthropic SDK not installed. Run `pip install anthropic` to include Claude in the bake-off."
        ) from exc

    api_key = os.environ.get(cfg.api_key_env or "", "")
    if not api_key:
        raise RuntimeError(f"{cfg.name}: missing API key (set {cfg.api_key_env})")
    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Native structured outputs; adaptive thinking left off (default) to keep this an
    # extraction task with comparable latency/cost — tune if grounding needs it.
    resp = await client.messages.create(
        model=cfg.model_id,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": EVAL_SUMMARY_JSON_SCHEMA}},
    )
    raw = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    usage = resp.usage
    return raw, getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0
