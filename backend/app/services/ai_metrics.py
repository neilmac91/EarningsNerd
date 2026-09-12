"""Bounded, process-local AI telemetry. Never records prompts, keys or filing identities.

The caller supplies ONE final cumulative usage snapshot per provider attempt. Cache tokens
are subsets of prompt tokens, never additional tokens. Unknown fields remain unavailable.
Summary records are call-local; only aggregate counters live in this module. Cloud Run
instances and job processes each have their own counters; logs provide the durable view.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
import json
import logging
import re
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)
_OPERATIONS = frozenset({
    "summary_primary", "summary_fallback", "section_recovery", "copilot_chat", "analysis_chat",
    "chat_stream",  # legacy label kept for old log consumers; no live caller emits it
})
_TRIGGERS = frozenset({"user", "job", "eval"})
_PROVIDERS = frozenset({"primary", "fallback"})
_OUTCOMES = frozenset({"success", "complete", "partial", "error", "timeout", "cancelled"})
_TOKEN_FIELDS = (
    "prompt_tokens", "completion_tokens", "total_tokens", "cache_hit_tokens", "cache_miss_tokens",
    "reasoning_tokens",
)
_MAX_MODEL_LABELS = 16
_model_labels: set[str] = set()
_calls: dict[tuple, dict] = {}
_summaries: Counter = Counter()
_lock = Lock()
# Optional per-task observer: a caller (the eval harness) that wants the normalized records of
# every provider attempt made under its task binds a list here; records are appended after the
# process counters/log line. Independent tasks never see each other's records (ContextVar).
_observer: ContextVar[list | None] = ContextVar("ai_call_observer", default=None)
# Who asked for this call: a user request (default), a Cloud Run job, or the eval harness. Set once
# at a process/task entry point; every record made under that context carries the label so cost
# can be attributed by call path AND by trigger from the log line alone.
_trigger: ContextVar[str] = ContextVar("ai_call_trigger", default="user")


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def _tokens(value: Any) -> int | None:
    # SDK counters are integers; bool/float/string values are malformed provider metadata.
    return value if type(value) is int and 0 <= value <= 10**12 else None


def _usage(usage: Any) -> dict[str, int | None]:
    prompt = _tokens(_field(usage, "prompt_tokens"))
    completion = _tokens(_field(usage, "completion_tokens"))
    total = _tokens(_field(usage, "total_tokens"))
    details = _field(usage, "prompt_tokens_details")
    # DeepSeek reports the cache split at the top level today and documents the nested
    # ``prompt_tokens_details`` names; read both so a wire-shape change never drops the split.
    hit = _tokens(_field(usage, "prompt_cache_hit_tokens"))
    if hit is None:
        hit = _tokens(_field(details, "prompt_cache_hit_tokens"))
    if hit is None:
        hit = _tokens(_field(details, "cached_tokens"))
    miss = _tokens(_field(usage, "prompt_cache_miss_tokens"))
    if miss is None:
        miss = _tokens(_field(details, "prompt_cache_miss_tokens"))
    # Thinking mode is disabled on every path; a non-zero value here means the provider silently
    # enabled it (ADR-0008), which is exactly the drift this field exists to expose.
    reasoning = _tokens(_field(_field(usage, "completion_tokens_details"), "reasoning_tokens"))
    if prompt is not None:
        if hit is not None and hit > prompt:
            hit = None
        if miss is not None and (miss > prompt or (hit is not None and hit + miss > prompt)):
            miss = None
    # Preserve provider-reported totals; never add cache hits/misses to those totals.
    if total is not None and prompt is not None and completion is not None and total != prompt + completion:
        total = None
    if reasoning is not None and completion is not None and reasoning > completion:
        reasoning = None
    return dict(zip(_TOKEN_FIELDS, (prompt, completion, total, hit, miss, reasoning)))


def _model(actual_model: Any) -> str | None:
    if not isinstance(actual_model, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", actual_model):
        return None
    # Preserve actual returned version/routing drift, with a hard lifetime cardinality cap.
    if actual_model not in _model_labels and len(_model_labels) >= _MAX_MODEL_LABELS:
        return None
    _model_labels.add(actual_model)
    return actual_model


def _fingerprint(value: Any) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", value) else None


def _latency(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 10**8 else None


def _empty_usage() -> dict:
    return {key: {"known_total": None, "known_calls": 0, "unknown_calls": 0} for key in _TOKEN_FIELDS}


def _add_usage(totals: dict, usage: dict) -> None:
    for key in _TOKEN_FIELDS:
        item = totals[key]
        value = usage[key]
        if value is None:
            item["unknown_calls"] += 1
        else:
            item["known_calls"] += 1
            item["known_total"] = (item["known_total"] or 0) + value


def record_ai_call(
    *,
    operation: str,
    provider: str,
    actual_model: Any,
    usage: Any,
    outcome: str,
    requested_model: Any = None,
    system_fingerprint: Any = None,
    latency_ms: Any = None,
    first_token_ms: Any = None,
) -> dict:
    """Normalize external response metadata once; return the caller's independent record.

    ``requested_model`` is what we asked for and ``actual_model`` what the response said it served;
    ``system_fingerprint`` is the provider's backend build id when present. Together with
    ``latency_ms`` / ``first_token_ms`` (caller-measured) and the per-model, peak-aware
    ``estimated_cost_usd`` they make a silent provider-side routing or pricing change visible
    from the log line alone (ADR-0008)."""
    from app.services.llm_pricing import estimate_call_cost_usd  # leaf-safe: imports only Settings

    normalized = _usage(usage)
    with _lock:
        record = {
            "operation": operation if operation in _OPERATIONS else "other",
            "provider": provider if provider in _PROVIDERS else "other",
            "trigger": _trigger.get(),
            "requested_model": _model(requested_model),
            "actual_model": _model(actual_model),
            "system_fingerprint": _fingerprint(system_fingerprint),
            "outcome": outcome if outcome in _OUTCOMES else "other",
            "latency_ms": _latency(latency_ms),
            "first_token_ms": _latency(first_token_ms),
            "usage": normalized,
        }
        cost = estimate_call_cost_usd(record["actual_model"] or record["requested_model"], normalized)
        record["estimated_cost_usd"] = cost["cost_usd"]
        record["peak"] = cost["peak"]
        key = tuple(record[field] for field in ("operation", "provider", "actual_model", "outcome"))
        bucket = _calls.setdefault(key, {"count": 0, "usage": _empty_usage(), "estimated_cost_usd": 0.0})
        bucket["count"] += 1
        bucket["estimated_cost_usd"] = round(bucket["estimated_cost_usd"] + (cost["cost_usd"] or 0.0), 6)
        _add_usage(bucket["usage"], normalized)
    logger.info("ai_call %s", json.dumps(record, separators=(",", ":")))
    sink = _observer.get()
    if sink is not None:
        sink.append(record)
    return record


def set_trigger(trigger: str) -> Any:
    """Label every subsequent record in this context as ``user`` / ``job`` / ``eval``; returns a
    reset token. Set once at a process or task entry point (job scripts, the eval harness)."""
    return _trigger.set(trigger if trigger in _TRIGGERS else "user")


def reset_trigger(token: Any) -> None:
    _trigger.reset(token)


def observe_ai_calls() -> tuple[list, Any]:
    """Bind a fresh record list for the current task; returns ``(records, reset_token)``.

    The caller must pass ``reset_token`` to :func:`stop_observing` when done so the binding does
    not leak into unrelated work on the same context."""
    records: list = []
    return records, _observer.set(records)


def stop_observing(token: Any) -> None:
    _observer.reset(token)


def record_ai_summary(records: Sequence[dict], outcome: str) -> dict:
    """Log one bounded aggregate per summary; call counters are not incremented again."""
    totals = _empty_usage()
    for record in records:
        _add_usage(totals, record["usage"])
    normalized_outcome = outcome if outcome in _OUTCOMES else "other"
    aggregate = {"outcome": normalized_outcome, "calls": len(records), "usage": totals}
    with _lock:
        _summaries[normalized_outcome] += 1
    logger.info("ai_summary %s", json.dumps(aggregate, separators=(",", ":")))
    return aggregate


def get_ai_metrics() -> dict:
    """Copy bounded counters for the existing admin metrics endpoint, never a last response."""
    with _lock:
        calls = [dict(zip(("operation", "provider", "actual_model", "outcome"), key),
                      count=bucket["count"], estimated_cost_usd=bucket.get("estimated_cost_usd", 0.0),
                      usage={field: dict(value) for field, value in bucket["usage"].items()})
                 for key, bucket in _calls.items()]
        return {"scope": "process", "calls": calls, "summaries": dict(_summaries)}
