"""W3-8b: the pre-classified 6-K class reaches prompt selection and the stored summary audit."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import openai_service as service_module
from app.services.openai_service import OpenAIService
from tests.unit.test_statement_relationship_integration import model_sections


def _service_with_one_streamed_chunk():
    service = OpenAIService()
    encoded = json.dumps(model_sections())

    async def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded))])

    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=chunks()))))
    service.fallback_client = None
    return service


@pytest.mark.asyncio
async def test_sixk_class_selects_the_variant_prompt_and_is_recorded_for_audit(monkeypatch):
    service = _service_with_one_streamed_chunk()
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value={}))
    selected = []
    real_get_prompt = service_module.get_prompt

    def spy(filing_type, sixk_class=None):
        selected.append((filing_type, sixk_class))
        return real_get_prompt(filing_type, sixk_class=sixk_class)

    monkeypatch.setattr(service_module, "get_prompt", spy)
    audit = {"class": "governance", "earnings_cues": 1, "governance_cues": 11, "money_tokens": 1, "regulatory_return": False}

    async def receive(_text):
        return None

    result = await service.summarize_filing("Exhibit 99.1 AGM notice", "Issuer", "6-K",
                                            filing_excerpt="Exhibit 99.1 AGM notice", stream_cb=receive,
                                            sixk_class="governance", sixk_class_audit=audit)
    assert selected == [("6-K", "governance")]
    raw = result["raw_summary"]
    assert raw["sixk_class"] == "governance" and raw["sixk_class_audit"] == audit


@pytest.mark.asyncio
async def test_without_a_class_the_generic_prompt_is_used_and_nothing_is_recorded(monkeypatch):
    service = _service_with_one_streamed_chunk()
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value={}))
    selected = []
    real_get_prompt = service_module.get_prompt
    monkeypatch.setattr(service_module, "get_prompt",
                        lambda filing_type, sixk_class=None: (selected.append((filing_type, sixk_class)) or real_get_prompt(filing_type, sixk_class=sixk_class)))

    async def receive(_text):
        return None

    result = await service.summarize_filing("Exhibit 99.1", "Issuer", "6-K", filing_excerpt="Exhibit 99.1", stream_cb=receive)
    assert selected == [("6-K", None)]
    assert "sixk_class" not in result["raw_summary"] and "sixk_class_audit" not in result["raw_summary"]
