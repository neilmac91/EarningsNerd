"""The depth harness's Claude API requests (evals/trend_depth/providers.py::anthropic_request).

Pins the request shapes the Claude 5.5 models accept: effort inside ``output_config``, adaptive thinking by
default, ``disabled`` thinking only where it is valid (Haiku 5.5), ``between_tools`` for Sonnet 5.5, and
no sampling parameters. The SDK is not needed: the builder returns plain keyword arguments.
"""
from __future__ import annotations

import asyncio

import pytest

from evals.trend_depth.providers import ARMS, anthropic_request, call


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
def test_no_sampling_parameters_and_room_for_thinking(arm: str) -> None:
    request = _request(arm)
    assert not {"temperature", "top_p", "top_k"} & set(request)
    assert request["max_tokens"] >= 32000
    assert request["messages"] == [{"role": "user", "content": "user text"}]
    assert request["system"] == "system text"


def test_thinking_off_arm_refuses_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="needs the Claude API"):
        asyncio.run(call(ARMS["claude-haiku-5-5-nothink"], "s", "u"))
