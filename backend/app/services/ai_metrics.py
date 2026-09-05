"""Bounded, process-local AI telemetry. Never records prompts, keys or filing identities.

The caller supplies ONE final cumulative usage snapshot per provider attempt. Cache tokens
are subsets of prompt tokens, never additional tokens. Unknown fields remain unavailable.
Summary records are call-local; only aggregate counters live in this module. Cloud Run
instances and job processes each have their own counters; logs provide the durable view.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import json
import logging
import re
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)
_OPERATIONS = frozenset({"summary_primary", "summary_fallback", "section_recovery", "chat_stream"})
_PROVIDERS = frozenset({"primary", "fallback"})
_OUTCOMES = frozenset({"success", "complete", "partial", "error", "timeout", "cancelled"})
_TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens", "cache_hit_tokens", "cache_miss_tokens")
_MAX_MODEL_LABELS = 16
_model_labels: set[str] = set()
_calls: dict[tuple, dict] = {}
_summaries: Counter = Counter()
_lock = Lock()


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def _tokens(value: Any) -> int | None:
    # SDK counters are integers; bool/float/string values are malformed provider metadata.
    return value if type(value) is int and 0 <= value <= 10**12 else None


def _usage(usage: Any) -> dict[str, int | None]:
    prompt = _tokens(_field(usage, "prompt_tokens"))
    completion = _tokens(_field(usage, "completion_tokens"))
    total = _tokens(_field(usage, "total_tokens"))
    hit = _tokens(_field(usage, "prompt_cache_hit_tokens"))
    if hit is None:
        hit = _tokens(_field(_field(usage, "prompt_tokens_details"), "cached_tokens"))
    miss = _tokens(_field(usage, "prompt_cache_miss_tokens"))
    if prompt is not None:
        if hit is not None and hit > prompt:
            hit = None
        if miss is not None and (miss > prompt or (hit is not None and hit + miss > prompt)):
            miss = None
    # Preserve provider-reported totals; never add cache hits/misses to those totals.
    if total is not None and prompt is not None and completion is not None and total != prompt + completion:
        total = None
    return dict(zip(_TOKEN_FIELDS, (prompt, completion, total, hit, miss)))


def _model(actual_model: Any) -> str | None:
    if not isinstance(actual_model, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", actual_model):
        return None
    # Preserve actual returned version/routing drift, with a hard lifetime cardinality cap.
    if actual_model not in _model_labels and len(_model_labels) >= _MAX_MODEL_LABELS:
        return None
    _model_labels.add(actual_model)
    return actual_model


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


def record_ai_call(*, operation: str, provider: str, actual_model: Any, usage: Any, outcome: str) -> dict:
    """Normalize external response metadata once; return the caller's independent record."""
    normalized = _usage(usage)
    with _lock:
        record = {
            "operation": operation if operation in _OPERATIONS else "other",
            "provider": provider if provider in _PROVIDERS else "other",
            "actual_model": _model(actual_model),
            "outcome": outcome if outcome in _OUTCOMES else "other",
            "usage": normalized,
        }
        key = tuple(record[field] for field in ("operation", "provider", "actual_model", "outcome"))
        bucket = _calls.setdefault(key, {"count": 0, "usage": _empty_usage()})
        bucket["count"] += 1
        _add_usage(bucket["usage"], normalized)
    logger.info("ai_call %s", json.dumps(record, separators=(",", ":")))
    return record


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
                      count=bucket["count"], usage={field: dict(value) for field, value in bucket["usage"].items()})
                 for key, bucket in _calls.items()]
        return {"scope": "process", "calls": calls, "summaries": dict(_summaries)}
