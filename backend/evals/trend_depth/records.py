"""Rules over run records that every stage shares, kept free of the bootstrap so unit tests can pin them.

A generation record is *unsettled* while it holds a provider error: ``error`` (the generation failed, and the
next ``generate`` makes it again) or ``repair_error`` (its first pass stands, and the next ``generate`` retries
only the repair, which can change its output). Audits and verdicts wait until the record is settled. Each
audit and verdict stores the hash of the output it read, so one left beside a changed output is redone, and
the report leaves it out until then.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from evals.trend_depth.providers import ARMS, labels_by_number, list_cost

READ_KEYS = ("output", "narrative", "citations")  # what an auditor or a judge reads of a generation record


def output_sha256(record: dict[str, Any]) -> str:
    body = {key: record.get(key) for key in READ_KEYS}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def text_sha256(text: str) -> str:
    """The hash a gold example's audit stores: the example is its Markdown file."""
    return hashlib.sha256(text.encode()).hexdigest()


def unsettled(record: Optional[dict[str, Any]]) -> Optional[str]:
    """Why a generation record cannot be audited or judged yet, or None once its output is final."""
    if record is None:
        return "no output yet"
    if "error" in record:
        return "a provider error, which generate retries"
    if "repair_error" in record:
        return "a repair that failed on a provider error, which generate retries"
    return None


def read_same_output(saved: dict[str, Any], key: str, sha: str) -> bool:
    """Whether an audit or a verdict (``saved``) read the output whose hash is ``sha``. One written before outputs
    were hashed (eval-v1) carries none and is trusted: no eval-v1 output changed after it was audited, and
    ``copy_systems`` copies audits and verdicts only beside a byte-identical record."""
    stored = saved.get(key)
    return stored is None or stored == sha


def write_text(path: Path, text: str) -> None:
    """Write a file whole or not at all: a kill mid-write leaves the previous file (or none), never a torn one
    that every later run would fail to read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as out:
            out.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_json(path: Path, record: Any) -> None:
    write_text(path, json.dumps(record, indent=1, default=str))


def labelled(entries: Any, expected: int) -> dict[int, dict[str, Any]]:
    """An auditor's labels for items 1..``expected``: the entries that carry a non-empty label. A reply that numbers
    any entry outside that range (from 0, say, which would shift every label onto the wrong item) is malformed
    and labelled nothing, as is one with no label under the expected field name."""
    numbered = labels_by_number(entries)
    if any(not 1 <= n <= expected for n in numbered):
        return {}
    return {n: entry for n, entry in numbered.items() if isinstance(entry.get("label"), str) and entry["label"].strip()}


def excerpt(text: str, keep: int = 4000) -> str:
    """A long reply's head and tail, so a record of a failed reply shows how it ended as well as how it began."""
    if len(text) <= 2 * keep:
        return text
    return f"{text[:keep]}\n[... {len(text) - 2 * keep} characters left out ...]\n{text[-keep:]}"


def all_attempts(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Every call a record paid for: earlier generations that failed on a provider error, then its own."""
    return [*record.get("prior_attempts", []), *record.get("attempts", [])]


def first_request_cache(records: list[dict[str, Any]]) -> int:
    """The cached prefix every company's first request read: the shared system prompt. It is the least that any
    first attempt read from cache, so no first attempt is credited with a hit left by an earlier run of its pack."""
    firsts = [int(a.get("cached_input_tokens") or 0) for r in records for a in all_attempts(r)
              if a.get("attempt") == 0 and a.get("backend") == "openai_compat"]
    return min(firsts) if firsts else 0


def api_cost(record: dict[str, Any], shared_cache: int = 0) -> Optional[float]:
    """The list-price cost of every call a record paid for, its earlier failed generations included, priced as a
    company's first analysis would bill:

    - a Claude CLI call reads nothing from cache: the harness's API request sets no cache breakpoint;
    - a Claude API call is priced as billed, cache writes included;
    - an OpenAI-compatible (DeepSeek) first attempt reads at most ``shared_cache`` tokens from cache, and a later
      attempt (a JSON retry or the repair) keeps its recorded hits, because it re-sends the first attempt's
      prefix seconds later, as a fresh analysis would.
    """
    arm = ARMS.get(record.get("arm", ""))
    if arm is None:
        return record.get("cost_usd")
    total = 0.0
    for attempt in all_attempts(record):
        backend, cached, write = attempt.get("backend"), int(attempt.get("cached_input_tokens") or 0), 0
        if backend == "claude_cli":
            cached = 0
        elif backend == "anthropic":
            write = int((attempt.get("meta") or {}).get("cache_creation_input_tokens") or 0)
        elif attempt.get("attempt") == 0:
            cached = min(cached, shared_cache)
        total += list_cost(arm, attempt["input_tokens"], cached, attempt["output_tokens"], write)
    return total
