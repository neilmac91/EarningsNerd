"""Tests for the flagged structured-output extraction path (roadmap S1).

Verifies that USE_STRUCTURED_OUTPUT changes the Phase-A extraction call as designed, and that
the default (flag off) path is unchanged — so the live flow can't regress until the eval
harness (S3) proves the new path beats baseline.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services.openai_service import openai_service


def _fake_completion(content: str = "{}"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
    )


async def _capture_create_kwargs(monkeypatch) -> list[dict]:
    """Patch the AI client's create() to record call kwargs; returns the recorded list."""
    calls: list[dict] = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return _fake_completion()

    monkeypatch.setattr(openai_service.client.chat.completions, "create", AsyncMock(side_effect=fake_create))
    return calls


@pytest.mark.asyncio
async def test_flag_off_uses_narrative_prompt_but_still_enforces_json(monkeypatch):
    monkeypatch.setattr(settings, "USE_STRUCTURED_OUTPUT", False)
    calls = await _capture_create_kwargs(monkeypatch)

    await openai_service.generate_structured_summary(
        filing_text="Net sales were $100,000 thousand. Item 1A Risk Factors. Item 7 MD&A.",
        company_name="Acme Corp",
        filing_type="10-K",
    )

    assert calls, "AI create() was never called"
    first = calls[0]
    # Phase 0: JSON is now ALWAYS enforced at the API layer (provider-agnostic), independent of
    # the flag. The flag now only controls the prompt (narrative vs schema-first) and temperature.
    assert first.get("response_format") == {"type": "json_object"}
    assert first["temperature"] == 0.2
    user_prompt = first["messages"][1]["content"]
    # The narrative analyst prompt (the contradiction S1 removes) is present when flag is off.
    assert "single, cohesive" in user_prompt.lower() or "600-1000 words" in user_prompt.lower()


@pytest.mark.asyncio
async def test_flag_on_enforces_json_and_uses_schema_first_prompt(monkeypatch):
    monkeypatch.setattr(settings, "USE_STRUCTURED_OUTPUT", True)
    calls = await _capture_create_kwargs(monkeypatch)

    await openai_service.generate_structured_summary(
        filing_text="Net sales were $100,000 thousand. Item 1A Risk Factors. Item 7 MD&A.",
        company_name="Acme Corp",
        filing_type="10-K",
    )

    assert calls, "AI create() was never called"
    first = calls[0]
    assert first.get("response_format") == {"type": "json_object"}  # enforced at API layer
    assert first["temperature"] == 0.1  # pinned low for determinism
    user_prompt = first["messages"][1]["content"]
    # The schema-first prompt is used; the contradictory narrative-format block is gone.
    assert "structured extraction agent" in user_prompt.lower()
    assert "600-1000 words" not in user_prompt.lower()
    assert "single, cohesive" not in user_prompt.lower()
