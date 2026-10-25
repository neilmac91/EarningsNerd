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
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from evals.trend_depth.providers import ARMS, labels_by_number, list_cost

READ_KEYS = ("output", "narrative", "citations")  # what an auditor or a judge reads of a generation record


def output_sha256(record: dict[str, Any]) -> str:
    body = {key: record.get(key) for key in READ_KEYS}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def text_sha256(text: str) -> str:
    """The hash a gold example's audit stores: the example is its Markdown file."""
    return hashlib.sha256(text.encode()).hexdigest()


def pack_sha256(pack: dict[str, Any]) -> str:
    """An evidence pack's hash. Its ``snapshot_id`` names the production dataset the pack was built from, so a pack
    rebuilt over the same data (packs-v2 beside packs, or packs-v2 rebuilt in place) keeps it; this hash does not."""
    return hashlib.sha256(json.dumps(pack, sort_keys=True, default=str).encode()).hexdigest()


def same_inputs(record: dict[str, Any], prompt_sha256: str, pack: dict[str, Any]) -> bool:
    """Whether a generation record was made from this prompt and this evidence pack, so its first pass may be repaired
    or copied rather than made again. A record written before packs were hashed (eval-v1, dev-v4, all on packs/)
    is held to its snapshot_id alone."""
    return (record.get("prompt_sha256") == prompt_sha256 and record.get("snapshot_id") == pack["snapshot_id"]
            and read_same_output(record, "pack_sha256", pack_sha256(pack)))


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


def own_spend(audit: dict[str, Any]) -> float:
    """What the calls made into an audit's own folder cost: its call and the earlier ones it replaced there. A copy
    from the other folder (``copied_from``) carries the other folder's call, so only its own earlier spend counts."""
    own = 0.0 if audit.get("copied_from") else audit.get("cost_usd", 0) or 0
    return round(own + (audit.get("prior_cost_usd", 0) or 0), 6)


def all_attempts(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Every call a record paid for: earlier generations that failed on a provider error, then its own."""
    return [*record.get("prior_attempts", []), *record.get("attempts", [])]


def first_reads(record: dict[str, Any]) -> list[int]:
    """What each OpenAI-compatible (DeepSeek) first attempt of a record read from cache, its replaced generations'
    included."""
    return [int(a.get("cached_input_tokens") or 0) for a in all_attempts(record)
            if a.get("attempt") == 0 and a.get("backend") == "openai_compat"]


def first_request_cache(records: list[dict[str, Any]]) -> int:
    """The cached prefix every company's first request shares, the system prompt, from ``records`` of one model and
    prompt: the read most of their first attempts share (the smaller on a tie). Once the prompt is cached, every
    company's first request reads exactly it. Two other reads are rarer: a prompt's first requests, sent before it is
    cached, read less (nothing, or the part an earlier prompt shares: dev-v4's first three read 1,024 of the frozen
    prompt's 1,920), and a repeat of a label's inputs reads each company's whole prompt, a length of its own per company
    (eval-v1's five companies dev-v4 had just run). The least read, the rule before, fell to the first, pricing a new
    prompt's every analysis cold beside one already cached, and, taken within one label, rose to the second: a repeated
    label whose every first request was warm cost half."""
    counts = Counter(read for r in records for read in first_reads(r))
    return min(counts, key=lambda read: (-counts[read], read)) if counts else 0


def prefix_key(record: dict[str, Any]) -> Optional[str]:
    """The cache a record's first request reads: its model's, for its prompt (``prompt_sha256``). The four DeepSeek
    flash arms share one model, so K0 and P (the frozen prompt) share a prefix, as Q and C (the candidate) do. None
    for a record made before prompts were hashed (dev-v3)."""
    if not record.get("prompt_sha256"):
        return None
    arm = ARMS.get(record.get("arm", ""))
    return f"{record.get('model') or (arm.model if arm else '')} {record['prompt_sha256']}"


def shared_prefixes(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    """``first_request_cache`` per model and prompt (``prefix_key``), over every recorded label's records passed, so a
    warm repeat of one label can neither raise its prompt's prefix nor stand alone. A record without a prompt hash is
    left out: its own label's records are its only peers."""
    by_prompt: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = prefix_key(record)
        if key is not None:
            by_prompt.setdefault(key, []).append(record)
    return {key: first_request_cache(group) for key, group in by_prompt.items()}


def warm_first_attempts(records: list[dict[str, Any]], prefix: Callable[[dict[str, Any]], int]) -> tuple[int, int]:
    """(first attempts that read more than their prompt's shared ``prefix`` from cache, first attempts): a warm read of
    an earlier request's pack, which ``api_cost`` prices as the prefix alone."""
    reads = [(read, prefix(r)) for r in records for read in first_reads(r)]
    return sum(1 for read, shared in reads if read > shared), len(reads)


def api_cost(record: dict[str, Any], shared_cache: int = 0) -> Optional[float]:
    """The list-price cost of every call a record paid for, its earlier failed generations included, priced as a
    company's first analysis would bill:

    - a Claude CLI call reads nothing from cache: the harness's API request sets no cache breakpoint;
    - a Claude API call is priced as billed, cache writes included;
    - an OpenAI-compatible (DeepSeek) first attempt reads at most ``shared_cache`` tokens from cache (its prompt's
      ``first_request_cache`` over every label), and a later attempt (a JSON retry or the repair) keeps its recorded
      hits, because it re-sends the first attempt's prefix seconds later, as a fresh analysis would.
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
