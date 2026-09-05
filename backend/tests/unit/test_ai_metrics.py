"""Actual SDK and vendor metadata remain honest, bounded and isolated per summary."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai.types.completion_usage import CompletionUsage, PromptTokensDetails

from app.config import settings
from app.services import ai_metrics, metrics_service


@pytest.fixture(autouse=True)
def fresh_counters(monkeypatch):
    monkeypatch.setattr(ai_metrics, "_calls", {})
    monkeypatch.setattr(ai_metrics, "_summaries", ai_metrics.Counter())
    monkeypatch.setattr(ai_metrics, "_model_labels", set())


def record(usage=None, **kwargs):
    return ai_metrics.record_ai_call(operation="summary_primary", provider="primary",
                                    actual_model="deepseek-v4-pro", usage=usage, outcome="success", **kwargs)


def test_sdk_and_vendor_cache_metadata_are_subsets_not_additional_tokens():
    sdk = CompletionUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120,
                          prompt_tokens_details=PromptTokensDetails(cached_tokens=40))
    first = record(sdk)
    assert first["usage"] == {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                              "cache_hit_tokens": 40, "cache_miss_tokens": None}
    vendor = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120,
                             prompt_cache_hit_tokens=60, prompt_cache_miss_tokens=40,
                             prompt_tokens_details=SimpleNamespace(cached_tokens=60))
    second = record(vendor)
    assert second["usage"] == {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                               "cache_hit_tokens": 60, "cache_miss_tokens": 40}
    totals = ai_metrics.get_ai_metrics()["calls"][0]["usage"]
    assert totals["total_tokens"] == {"known_total": 240, "known_calls": 2, "unknown_calls": 0}
    assert totals["cache_hit_tokens"]["known_total"] == 100
    assert totals["cache_miss_tokens"] == {"known_total": 40, "known_calls": 1, "unknown_calls": 1}


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": -1,
                                            "total_tokens": "10", "prompt_cache_hit_tokens": 1.5}])
def test_unknown_or_malformed_usage_is_unavailable_not_zero(usage):
    result = record(usage)
    assert result["usage"] == dict.fromkeys(ai_metrics._TOKEN_FIELDS)
    aggregate = ai_metrics.record_ai_summary([result], "error")
    assert all(v == {"known_total": None, "known_calls": 0, "unknown_calls": 1}
               for v in aggregate["usage"].values())


def test_contradictory_provider_counters_do_not_become_claimed_totals():
    result = record({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 20,
                     "prompt_cache_hit_tokens": 11, "prompt_cache_miss_tokens": 12})
    assert result["usage"] == {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": None,
                               "cache_hit_tokens": None, "cache_miss_tokens": None}
    result = record({"prompt_tokens": 10, "prompt_cache_hit_tokens": 6, "prompt_cache_miss_tokens": 5})
    assert result["usage"]["cache_miss_tokens"] is None


def test_untrusted_labels_and_usage_fields_are_never_logged(caplog):
    caplog.set_level("INFO", logger=ai_metrics.__name__)
    secret = "filing-123-private-prompt"
    result = ai_metrics.record_ai_call(operation=secret, provider=secret, actual_model=secret,
                                      usage={"prompt": secret, "api_key": secret}, outcome=secret)
    assert (result["operation"], result["provider"], result["actual_model"], result["outcome"]) == (
        "other", "other", None, "other")
    assert secret not in caplog.text and secret not in str(ai_metrics.get_ai_metrics())
    assert "ai_call" in caplog.text


def test_configured_actual_model_identity_is_bounded_even_if_configuration_changes(monkeypatch):
    labels = []
    for index in range(20):
        name = f"configured-model-{index}"
        monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", name)
        labels.append(ai_metrics.record_ai_call(operation="summary_fallback", provider="fallback",
                      actual_model=name, usage=None, outcome="success")["actual_model"])
    assert labels[:16] == [f"configured-model-{i}" for i in range(16)]
    assert labels[16:] == [None] * 4
    assert len(ai_metrics.get_ai_metrics()["calls"]) == 17
    missing = ai_metrics.record_ai_call(operation="section_recovery", provider="primary", actual_model=None,
                                        usage=None, outcome="timeout")
    assert missing["actual_model"] is None


@pytest.mark.parametrize("setting", ["AI_SECTION_RECOVERY_MODEL", "AI_FAST_MODEL"])
def test_actual_configured_recovery_models_are_recognized(monkeypatch, setting):
    monkeypatch.setattr(settings, setting, "configured-recovery-model")
    result = ai_metrics.record_ai_call(operation="section_recovery", provider="primary",
                                       actual_model="configured-recovery-model", usage=None, outcome="success")
    assert result["actual_model"] == "configured-recovery-model"


def test_summary_aggregate_is_call_local_and_does_not_double_count(caplog):
    caplog.set_level("INFO", logger=ai_metrics.__name__)
    first = record({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12})
    second = record({"prompt_tokens": 30, "completion_tokens": 4, "total_tokens": 34})
    a = ai_metrics.record_ai_summary([first], "complete")
    b = ai_metrics.record_ai_summary([second], "partial")
    assert a["usage"]["total_tokens"]["known_total"] == 12
    assert b["usage"]["total_tokens"]["known_total"] == 34
    assert ai_metrics.get_ai_metrics()["calls"][0]["count"] == 2
    assert ai_metrics.get_ai_metrics()["calls"][0]["usage"]["total_tokens"]["known_total"] == 46
    assert ai_metrics.get_ai_metrics()["summaries"] == {"complete": 1, "partial": 1}
    assert sum(r.message.startswith("ai_summary ") for r in caplog.records) == 2


@pytest.mark.asyncio
async def test_admin_metrics_exposes_independent_process_snapshot(monkeypatch):
    from app.services import redis_service
    monkeypatch.setattr(redis_service, "check_redis_health", AsyncMock(return_value={"healthy": True}))
    record({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12})
    ai_metrics.record_ai_summary([], "cancelled")
    result = await metrics_service.get_all_metrics()
    assert result["ai"] == ai_metrics.get_ai_metrics()
    assert result["ai"]["scope"] == "process" and result["ai"]["calls"][0]["count"] == 1
    result["ai"]["calls"][0]["usage"]["total_tokens"]["known_total"] = 999
    assert ai_metrics.get_ai_metrics()["calls"][0]["usage"]["total_tokens"]["known_total"] == 12
