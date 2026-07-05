"""Model-capability flags for the AI summary/copilot paths (roadmap S2 façade split).

Leaf module: imports nothing from ``app.services`` so both the ``openai_service`` façade and the
copilot-chat mixin can depend on it without an import cycle. Extracted verbatim.
"""
from __future__ import annotations

from typing import Optional


def _thinking_disabled_model(model_name: Optional[str], base_url: Optional[str]) -> bool:
    """True for reasoning models that default to a "thinking" mode we want OFF for the
    deterministic extraction/summary task, AND that accept the OpenAI-compatible
    ``extra_body={"thinking": {"type": "disabled"}}`` switch.

    Covers DeepSeek V4 (api.deepseek.com) and Zhipu GLM served via the z.ai
    OpenAI-compatible endpoint. For these we pass the switch and keep full max_tokens
    headroom; for everything else the caller clamps max_tokens to the Gemini-safe ceiling.
    Detection is by model id OR base URL so an env-swap (OPENAI_BASE_URL/AI_DEFAULT_MODEL)
    is enough — no per-call wiring."""
    m = (model_name or "").lower()
    b = (base_url or "").lower()
    return (
        "deepseek" in m or "deepseek" in b
        or m.startswith("glm") or "glm-" in m
        or "z.ai" in b or "bigmodel" in b
    )
