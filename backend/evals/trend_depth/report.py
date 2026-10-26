"""Aggregate a bake-off run: fact-check gate, sentence mix, cost and latency, pairwise judge matrix.

    cd backend && python -m evals.trend_depth.report --label eval-v1 --systems current,deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5

Writes ``runs/<label>/REPORT.md`` and ``runs/<label>/summary.json``. Development and held-out companies are
reported side by side; the held-out half is the result, the development half is where the prompt was tuned.

Cost is the list-price cost of the measured tokens (``providers.list_cost``: uncached input, cached input,
cache writes and output at each provider's published rate), including every attempt of every generation,
failed ones too, priced as a company's first analysis would bill (``records.api_cost``). A first request
reads from cache only the prefix every company shares, the system prompt, read per prompt over every label in
``runs/`` (``records.first_request_cache``), so a run whose first requests find their whole prompt still cached is
priced as a cold one; each arm's count of such warm first attempts is shown beside its cost. A repair re-sends its
first pass's prefix seconds later and keeps the hits DeepSeek recorded. The harness's Claude API request sets no cache
breakpoint, so a Claude call reads nothing from cache. The cost each provider recorded is in ``summary.json``
as ``cost_recorded_mean``. Extrapolation multiplies the mean cost of a fresh generation, including any repair
call, by the monthly run count.

A record still waiting on a provider error (``records.unsettled``) is counted apart, as is an audit or verdict
that failed, was refused, or read an output that has since changed: none of them is reported as a result, but a
record awaiting its repair counts as an analysis that did not pass without one (``arm_measures``).

Every arm is also scored on the measures of DEEPSEEK-ERRORS.md §3 (``arm_measures``, in ``summary.json`` under each
split's ``measures``), beside §3's target for the candidate, and every item they count is listed for hand reading.
A record made with ``generate --pipeline v2`` (``pipeline: "v2"``) adds the repair area's fields: the gate on the
model's own first output (``raw_first_pass_gate``), the sentences the code retyped (``retyped``) and the repair's kind
(``repair_kind``). A record without them is version 1 (eval-v1 and earlier). A version-2 record made before
auto-citation was removed also carries ``autocite``, which no measure reads: a figure stated without its own ID is a
first-try gate error of the model's own output, whatever the code then did with it. Its build is another
("v2 with auto-citation", ``records.pipeline_of``), so pooling it with the version 2 of now is warned.
Every measure is on one basis for every record and arm, and reads the pack the arm read but where stated:

- passes without a model repair count what each arm's own pipeline did: a failed generation, and a record whose
  repair generate still owes (``records.awaiting_repair``: its first pass failed the gate), count as not passing, and
  a warning at the top names every record generate still owes (``pending_warnings``). A repair sent for the gate's
  broken_debt backstop alone has a row of its own: only an arm reading ``packs-v2/`` can have one;
- first-try errors score the model's own first output (``first_output``) under the gate as it is now, in two rows:
  the gate's failing claims, and the claims its backstops fail beyond them (``first_try``);
- mislabels are distinct sentences, from the probes of a number said about another ratio, basis or year
  (``MISLABEL_KINDS``) and Opus's substantive flags (``OPUS``), each per 1,000 verified claims, in two rows: the
  probes alone over every output, and with Opus over the outputs Opus read (§3's target; P and Q have no Opus
  audit). The probes' other gate kinds have rows of their own (``OWN_ROW_KINDS``);
- broken net cash reads the breaks the company's ``packs-v2/`` pack records whatever pack the arm read
  (``broken_net_cash``), so a withheld figure cited by its ID (an arm reading ``packs/``) and the same figure
  rebuilt from the lines ``packs-v2/`` still shows count alike;
- latency quantiles are linear between the two nearest ranks, the basis of §3's baselines (``records.quantile``);
- the judge's verdicts are shown per criterion, as §3's judge target reads them, and across runs per criterion and
  summed (``judge_runs``).

Each arm's builds (pipeline, prompt and packs, ``build``) are listed, with a warning at the top when one label, or the
runs pooled, hold more than one. Several runs of the same arms:

    cd backend && python -m evals.trend_depth.report --labels dev-v5-r1,dev-v5-r2 --systems deepseek-flash,deepseek-flash-c

prints each measure per run, its range and the runs pooled, beside the targets, and writes them to
``runs/<label>+<label>/`` (``--out`` writes elsewhere); it never picks the better run.
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional

from evals.trend_depth import calibration, factcheck, probes
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, SECTION_KEYS, load_pack, sentences_of
from evals.trend_depth.judge import CRITERIA, _family
from evals.trend_depth.providers import ARMS, packs_dir, parse_json_object
from evals.trend_depth.records import (
    api_cost, awaiting_repair, first_reads, first_request_cache, output_sha256, pack_sha256, pipeline_of, prefix_key,
    quantile, read_same_output, shared_prefixes, text_sha256, unsettled, warm_first_attempts,
)
from evals.trend_depth.semantics import classify_flag

OPUS = "claude-opus-5-5"  # the auditor §3 counts mislabels and cause support with
OLD_GATE = "b3ed8ef"  # the gate before wave 1 narrowed it (DEEPSEEK-ERRORS.md was measured on it): continuity, as in replay.py
REFERENCE_PACKS = "packs-v2"  # the breaks it records (data checks, withheld IDs) say which figures rest on a broken line
QUANTILE = "linear between the two nearest ranks, as §3's baselines"  # the latency rows' note (``records.quantile``)
# DEEPSEEK-ERRORS.md §3's judge target, read jointly: C wins or ties both grounding and calibration in the same pair.
# Each criterion is shown apart beside the joint count (``judge_matrix``).
BOTH_CRITERIA = ("grounding", "calibration")
JUDGE_TARGET = ("C wins or ties both grounding and calibration in the same pair on at least 12 of 20 per split (two runs "
                "of 10); loses depth on no more than 5")
# The probes' gate kinds, each counted once: a number said about another ratio, basis or year is a mislabel (§1.2's
# root causes); an unsigned fall, a unitless dollar figure and a margin gap's direction each have a row of their own
# (§1.4's logic slips, fix 11, fix 9); broken_debt is the broken-net-cash measure.
MISLABEL_KINDS = ("R1", "R2a", "R2c", "R3")
OWN_ROW_KINDS = ("U1", "unitless_dollars", "gap_direction")

FAILURE_CLASSES = (
    ("unknown citation", "unknown_citation"), ("no citation", "uncited_number"), ("other way", "direction"),
    ("not in the period", "period"), ("matches nothing", "no_match"), ("cites no filing passage", "cause_without_passage"),
    ("generation failed", "generation_failed"),
)


def _class(failure: str) -> str:
    return next((name for needle, name in FAILURE_CLASSES if needle in failure), "other")


def _pct(n: float, d: float) -> str:
    return f"{n / d * 100:.0f}%" if d else "—"


def load(label: str, system: str, tickers: list[str]) -> list[dict[str, Any]]:
    out = []
    for ticker in tickers:
        path = RUNS / label / system / f"{ticker}.json"
        if path.exists():
            out.append(json.loads(path.read_text()))
    return out


def recorded_prefixes() -> dict[str, int]:
    """``records.shared_prefixes`` over every generation record in ``runs/``, every label's."""
    found = []
    for path in RUNS.glob("*/*/*.json"):
        if path.parent.name in ARMS:
            record = json.loads(path.read_text())
            if isinstance(record, dict):
                found.append(record)
    return shared_prefixes(found)


def gate_now(sentences: list[dict[str, Any]], pack: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """The gate as it is now, as the record's pipeline runs it: with the backstops for a version-2 record (``generate
    --pipeline v2`` decides with them), without them for version 1."""
    if record.get("pipeline") == "v2":
        return factcheck.check(sentences, pack, backstops=True)
    return factcheck.check(sentences, pack)


def arm_stats(records: list[dict[str, Any]], prefixes: Optional[dict[str, int]] = None) -> dict[str, Any]:
    """One arm's table row. ``prefixes`` is each prompt's shared cached prefix (``recorded_prefixes``, read when
    None); a record without a prompt hash shares one with the records passed that lack it too."""
    n = len(records)
    pending = [r for r in records if awaiting_repair(r)]  # a first pass whose repair generate still owes
    errored = [r for r in records if "error" in r]  # a provider failure generate retries, not the model's own
    ok = [r for r in records if r.get("generation_ok") and not unsettled(r)]
    stats: dict[str, Any] = {"n": n, "generated": len(ok), "pending_repairs": len(pending), "provider_errors": len(errored)}
    if not ok:
        return stats
    if ok[0]["arm"] == "current":
        stats.update({
            "words_mean": statistics.mean(r["words"] for r in ok),
            "cost_mean": statistics.mean(r.get("cost_usd") or 0 for r in ok),
            "latency_p50": quantile([r["latency_s"] for r in ok], 0.5),
            "latency_p90": quantile([r["latency_s"] for r in ok], 0.9),
        })
        return stats
    gates = [r["gate"] for r in ok]
    first = [r.get("first_pass_gate", r["gate"]) for r in ok]
    # The same outputs under the gate as it is now: fixes made after the run (each a false positive, listed in
    # REPORT.md) change these counts but not the outputs, which were generated under the gate as it was then.
    now_final = [gate_now(sentences_of(r["output"]), load_pack(r["ticker"], r["arm"]), r)["passed"] for r in ok]
    now_first = [gate_now(sentences_of(r.get("first_pass_output", r["output"])), load_pack(r["ticker"], r["arm"]), r)["passed"]
                 for r in ok]
    failures = Counter(_class(f["failure"]) for g in first for f in g.get("failures", []))
    types: Counter[str] = Counter()
    passages_cited = []
    for r in ok:
        for section in r["output"]["sections"]:
            for sentence in section["sentences"]:
                types[sentence.get("type", "")] += 1
        cited = set()
        for detail in r["gate"].get("detail", []):
            cited.update(c for c in detail["citations"] if c[0] in "PQ")
        passages_cited.append(len(cited))
    total_sentences = sum(types.values())
    # Every paid generation counts toward cost, a failed one included; latency is the successful ones'.
    paid = [r for r in records if r.get("attempts") or r.get("prior_attempts")]
    known = {**shared_prefixes(paid), **(recorded_prefixes() if prefixes is None else prefixes)}
    unhashed = first_request_cache([r for r in paid if prefix_key(r) is None])

    def shared(r: dict[str, Any]) -> int:
        key = prefix_key(r)
        return unhashed if key is None else known.get(key, 0)

    costs = [c for c in (api_cost(r, shared(r)) for r in paid) if c is not None]
    stats.update({
        "first_pass_gate": sum(1 for g in first if g["passed"]),
        "final_gate": sum(1 for g in gates if g["passed"]),
        "first_pass_gate_now": sum(now_first),
        "final_gate_now": sum(now_final),
        "repaired": sum(1 for r in ok if "first_pass_gate" in r),
        "claims_mean": statistics.mean(g["claims"] for g in gates),
        "first_pass_claims": sum(g["claims"] for g in first),
        "first_pass_failed_claims": sum(g["failed_claims"] for g in first),
        "final_failed_claims": sum(g["failed_claims"] for g in gates),
        "failure_classes_first_pass": dict(failures),
        "sentence_mix": {k: types[k] / total_sentences for k in ("fact", "comparison", "cause", "judgement")} if total_sentences else {},
        "sentences_mean": total_sentences / len(ok),
        "causes_mean": types["cause"] / len(ok),
        "passages_cited_mean": statistics.mean(passages_cited),
        "words_mean": statistics.mean(r["words"] for r in ok),
        "words_max": max(r["words"] for r in ok),
        "cost_mean": statistics.mean(costs) if costs else None, "cost_n": len(costs),
        "cost_recorded_mean": statistics.mean((r.get("cost_usd") or 0) + (r.get("prior_cost_usd") or 0) for r in paid) if paid else None,
        # The prefix each prompt's first requests are priced with, and the first attempts that read more (warm).
        "shared_prefix_tokens": {str(r.get("prompt_sha256") or "no prompt hash")[:8]: shared(r) for r in paid if first_reads(r)},
        "warm_first_attempts": list(warm_first_attempts(paid, shared)),
        "failed_generations": n - len(ok) - len(pending) - len(errored),  # the model's own failures
        # The calls of every failed generation, the model's or the provider's, and of those a record replaced.
        "failed_generation_cost": round(sum((api_cost(r, shared(r)) or 0) if not r.get("generation_ok")
                                            else (api_cost({"arm": r["arm"], "attempts": r.get("prior_attempts", [])}, shared(r)) or 0)
                                            for r in paid), 6),
        "backends": sorted({a.get("backend", "?") for r in paid for a in r.get("attempts", [])}),
        "input_tokens_mean": statistics.mean(r["usage"]["input_tokens"] for r in ok),
        "output_tokens_mean": statistics.mean(r["usage"]["output_tokens"] for r in ok),
        "latency_p50": quantile([r["latency_s"] for r in ok], 0.5),
        "latency_p90": quantile([r["latency_s"] for r in ok], 0.9),
    })
    return stats


def audit_folders(label: str, kind: str) -> list[str]:
    """``causes`` (each system audited by another family) first, then any same-auditor ``causes-by-<arm>``."""
    root = RUNS / label
    extra = sorted(p.name for p in root.glob(f"{kind}-by-*") if p.is_dir()) if root.exists() else []
    return ([kind] if (root / kind).exists() else []) + extra


def _generation(label: str, system: str, ticker: str) -> Optional[dict[str, Any]]:
    path = RUNS / label / system / f"{ticker}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _audit_state(label: str, audit: dict[str, Any], system: str, ticker: str) -> str:
    """``ok``, ``refused``, or ``pending``: the audit failed, its output is not final, or it read an earlier one."""
    if "error" in audit:
        return "pending"
    if system == "gold":
        from evals.trend_depth.gold import GOLD
        sha = text_sha256((GOLD / f"{ticker}.md").read_text()) if (GOLD / f"{ticker}.md").exists() else ""
    else:
        generation = _generation(label, system, ticker)
        if unsettled(generation):
            return "pending"
        sha = output_sha256(generation)
    if not read_same_output(audit, "output_sha256", sha):
        return "pending"
    return "refused" if audit.get("refused") else "ok"


def cause_support(label: str, systems: list[str], tickers: list[str], folder: str = "causes") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for system in systems:
        counts: Counter[str] = Counter()
        auditors: Counter[str] = Counter()
        left_out: Counter[str] = Counter()
        for ticker in tickers:
            path = RUNS / label / folder / system / f"{ticker}.json"
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            state = _audit_state(label, record, system, ticker)
            if state != "ok":
                left_out[state] += 1
                continue
            auditors[record.get("auditor") or "none"] += 1
            counts.update(item["label"] for item in record.get("items", []))
        if counts or left_out:
            out[system] = {"counts": dict(counts), "auditors": dict(auditors), "left_out": dict(left_out)}
    return out


def semantic_support(label: str, systems: list[str], tickers: list[str], folder: str = "semantics") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for system in systems:
        counts: Counter[str] = Counter()
        auditors: Counter[str] = Counter()
        views: Counter[str] = Counter()
        left_out: Counter[str] = Counter()
        flagged: list[dict[str, str]] = []
        for ticker in tickers:
            path = RUNS / label / folder / system / f"{ticker}.json"
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            state = _audit_state(label, record, system, ticker)
            if state != "ok":
                left_out[state] += 1
                continue
            auditors[record.get("auditor") or "none"] += 1
            views[str(record.get("view", 1))] += 1  # the auditor's view of the matches (semantics.VIEW)
            output = _generation(label, system, ticker)["output"]
            for item in record.get("items", []):
                counts[item["label"]] += 1
                if item["label"] == "mismatch":
                    kind = classify_flag(item, sentences_of(output), load_pack(ticker, system), record.get("view", 1))
                    counts[f"mismatch_{kind}"] += 1
                    flagged.append({"ticker": ticker, "kind": kind, "claim": item["claim"], "sentence": item["sentence"],
                                    "reason": item["reason"]})
        if counts or left_out:
            out[system] = {"counts": dict(counts), "auditors": dict(auditors), "analyses": sum(auditors.values()),
                           "left_out": dict(left_out), "flagged": flagged, "views": dict(views)}
    return out


# --- DEEPSEEK-ERRORS.md §3 measures ---------------------------------------------------------------------------------

def repaired(record: dict[str, Any]) -> bool:
    """Whether a model repair was sent: a repair attempt, in a version-1 or a version-2 record alike."""
    return any(a.get("attempt") == "repair" for a in record.get("attempts", []))


_BROKEN_DEBT_FAILURE = "backstop broken_debt:"  # factcheck.check's failure string for that backstop's hit


def broken_debt_repair(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The failures a repair was sent or is owed (``awaiting_repair``) for, when the gate's broken_debt backstop is all of
    them: every failure of the verdict that sent it (``first_pass_gate`` once the repair ran, else ``gate``); else none.
    That backstop reads the breaks of the arm's own pack, and packs/ records none, so only an arm reading packs-v2 (P,
    C) can have one: version 2's fix 8 lets the gate catch a figure it withholds, which K0 and Q state uncaught (broken
    net cash counts both alike). The pass row counts what each arm's pipeline did, so this row says how much of P's
    and C's shortfall against K0 is that catch."""
    if not (repaired(record) or awaiting_repair(record)):
        return []
    failures = (record.get("first_pass_gate") or record.get("gate") or {}).get("failures", [])
    return failures if failures and all(f["failure"].startswith(_BROKEN_DEBT_FAILURE) for f in failures) else []


def first_output(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The model's first output, before the code's retyping or any repair. A version-1 record's is its first pass (its
    output when no repair ran). A version-2 record's first pass carries the retyping, so its first valid reply is read
    from its attempts instead; None if none parses."""
    if record.get("pipeline") != "v2":
        first = record.get("first_pass_output")
        return first if isinstance(first, dict) else record["output"]
    replies = [a for a in record.get("attempts", []) if a.get("attempt") != "repair" and not a.get("problems")]
    parsed = parse_json_object(replies[-1].get("raw") or "") if replies else None
    return parsed if isinstance(parsed, dict) and isinstance(parsed.get("sections"), list) else None


def _plain(text: str) -> str:
    return " ".join(factcheck.CITATION_RE.sub("", text).split())


def broken_net_cash(sentences: list[dict[str, Any]], pack: dict[str, Any], reference: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Figures built on a break, on one basis for every arm: the breaks are those the company's version-2 pack
    (``reference``) records (``probes.debt_breaks``), and ``probes.broken_debt`` finds a figure it withholds whether
    the sentence cites it by its ID (an arm reading version 1, which still shows it) or rebuilds it from the lines
    version 2 still shows (cash less the one debt line left, which the gate verifies as a difference), in a sentence
    that does not disclose the break. None when the reference records no break at all.

    - ``state``, for a company whose reference names a debt or liquidity break (None otherwise): ``disclosed`` if a
      sentence discloses a break by the rule the gate's backstop and ``stated`` read (``probes.discloses``: a
      disclosure word in a clause about debt or cash, so "Net cash was $8.8 billion, though one-off tax payments
      understate free cash flow" discloses nothing and states the broken figure), else ``stated as fact`` if a
      sentence states a broken figure, else ``silent``. Words alone decide, never a cited withheld ID, which only an
      arm reading version 1 could cite;
    - ``stated``: each sentence stating a figure of a ``debt_break`` or ``liquidity_break`` without disclosing it in
      that sentence, its breaks and claims, whatever the analysis says elsewhere;
    - ``peer``: each sentence citing a version-1 net-cash peer rank or median built on a peer's broken year
      (``peer_break``), which only an arm reading version 1 can cite, as version 2 replaces it with a checked one.
    """
    breaks = probes.debt_breaks(reference)
    if not (breaks.debt_years or breaks.cash_years or breaks.ids):
        return None
    grouped: dict[str, dict[tuple[str, str], dict[str, Any]]] = {"stated": {}, "peer": {}}
    for hit in probes.broken_debt(sentences, pack, reference=reference):
        entry = grouped["peer" if hit["break"] == "peer_break" else "stated"].setdefault(
            (hit["section"], hit["sentence"]), {"section": hit["section"], "sentence": hit["sentence"], "breaks": [], "claims": []})
        entry["breaks"] = sorted({*entry["breaks"], hit["break"]})
        entry["claims"].append(f"'{hit['claim']}' {hit['detail']}")
    checks = [kind for kind, years in (("debt_break", breaks.debt_years), ("liquidity_break", breaks.cash_years)) if years]
    disclosed = [{"section": s.get("section", ""), "sentence": s["text"]} for s in sentences
                 if probes.discloses(_plain(s["text"]))] if checks else []
    stated = list(grouped["stated"].values())
    state = None if not checks else "disclosed" if disclosed else "stated as fact" if stated else "silent"
    return {"state": state, "checks": checks, "stated": stated, "disclosed": disclosed, "peer": list(grouped["peer"].values())}


_GATE_FAILED = ("no_match", "period_mismatch", "direction_mismatch")  # a claim the gate fails
_REPEATS_ITS_CLAIMS = "number(s) with no citation"  # a sentence-level failure its claims' own "matches nothing" repeat


def first_try(sentences: list[dict[str, Any]], pack: dict[str, Any], keys: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A first output's errors under the gate as it is now, each counted once: (the gate's own: each claim it fails and
    each sentence-level failure, a cause without its passage or an unknown citation; the backstops': each verified
    claim a backstop gate kind fails, its kinds named, but ``broken_debt``, which ``broken_net_cash`` measures on one
    basis for every arm, while the gate's own backstop reads only the pack's own breaks and so fires on version 2
    alone). ``check(..., backstops=True)`` lists a claim once per kind (CAT's "-35.6%" fails R2a and R2c) and an
    uncited number twice."""
    gate: list[dict[str, Any]] = []
    backstops: list[dict[str, Any]] = []
    for sentence in sentences:
        result, resolved = factcheck.analyse_sentence(sentence, pack)
        where = {"section": sentence.get("section", ""), "sentence": sentence["text"]}
        claim_failures = [f for f in result.failures if f.startswith("'")]  # one per failed claim, in claim order
        gate += [{**where, "claim": "", "failure": f} for f in result.failures
                 if not f.startswith("'") and not f.startswith(_REPEATS_ITS_CLAIMS)]
        gate += [{**where, "claim": r.claim.text, "failure": f}
                 for r, f in zip([r for r in resolved if r.status in _GATE_FAILED], claim_failures)]
        hits: dict[str, dict[str, Any]] = {}
        for hit in probes.probe_sentence(sentence, pack, resolved, keys):
            if hit["kind"] in probes.GATE_KINDS:
                entry = hits.setdefault(hit["claim"], {**where, "claim": hit["claim"], "kinds": [], "detail": []})
                entry["kinds"].append(hit["kind"])
                entry["detail"].append(hit["detail"])
        backstops += list(hits.values())
    return gate, backstops


def build(record: dict[str, Any], pack: Optional[dict[str, Any]]) -> str:
    """What made a generation record: its pipeline, its prompt (the sha256's head) and the packs it read, marked when
    the record read another build of its pack than the one on disk (``pack``) or predates pack hashes."""
    folder = record.get("packs") or packs_dir(record.get("arm", ""), RUNS.parent).name
    if pack is None:
        state = ""
    elif record.get("pack_sha256"):
        state = "" if record["pack_sha256"] == pack_sha256(pack) else " (an earlier build)"
    else:  # eval-v1 and dev-v4, held to the dataset's snapshot (records.same_inputs)
        state = " (no pack hash)" if record.get("snapshot_id") == pack.get("snapshot_id") else " (another snapshot)"
    return f"{pipeline_of(record)} · prompt {str(record.get('prompt_sha256') or 'unhashed')[:8]} · {folder}{state}"


def _reference_pack(ticker: str) -> Optional[dict[str, Any]]:
    """The company's version-2 pack (``REFERENCE_PACKS``), whose debt-break checks the broken-net-cash measure reads
    for every arm: a version-1 pack keeps every ID it has, but names no break."""
    folder = RUNS.parent / REFERENCE_PACKS
    for path in (folder / f"{ticker}.json.gz", folder / f"{ticker}.json"):
        if path.exists():
            raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
            return json.loads(raw)
    return None


def _audit_by(label: str, kind: str, system: str, ticker: str, auditor: str) -> Optional[dict[str, Any]]:
    """``auditor``'s finished audit of this output, counted once: from its same-auditor folder and from the default
    folder when that auditor made it (deepseek-flash's default auditor is Opus); the later view when both hold one (a
    view-2 re-audit beside a view-1 copy). None while the same-auditor folder holds that auditor's failed, refused
    or stale audit: a re-audit that labelled nothing must not fall back to the other folder's earlier one, which
    would mix views under one count."""
    found = []
    for folder in (f"{kind}-by-{auditor}", kind):
        path = RUNS / label / folder / system / f"{ticker}.json"
        record = json.loads(path.read_text()) if path.exists() else None
        if record is None or record.get("auditor") != auditor:
            continue
        if _audit_state(label, record, system, ticker) == "ok":
            found.append(record)
        elif folder != kind:
            return None
    return max(found, key=lambda record: record.get("view", 1)) if found else None


def arm_measures(label: str, system: str, records: list[dict[str, Any]], stats: dict[str, Any],
                 old_gate: Optional[tuple[str, ModuleType]] = None) -> dict[str, Any]:
    """DEEPSEEK-ERRORS.md §3's measures for one arm's analyses, with every counted item for hand reading. ``stats`` is
    the arm's ``arm_stats`` (cost and latency); ``old_gate``, (commit, the gate as committed there:
    ``replay.base_gate``), scores the first and final outputs for continuity with eval-v1.

    - A failed generation (the model's own outcome: invalid replies, or a refusal) is an analysis that did not pass.
    - A record awaiting its repair (``records.awaiting_repair``) did not pass either: generate repairs only a first
      pass that failed the gate. Its first output is final, so the first-output measures (first-try errors, retypes,
      the old gate's first try) score it; its final output is not, so the final-output measures
      (mislabels, calibration, broken net cash, form, audits) wait for it. Left out, a provider outage during the
      repairs removed exactly the failing analyses: eval-v1's DeepSeek read 13 of 13 instead of 13 of 20.
    - A provider error (``error``) has no output yet: it is left out until generate makes it, and counted.
    - Every measure reads the pack the arm read (``own_pack``), but broken net cash, which reads packs-v2's breaks
      for every arm (``broken_net_cash``).
    """
    if system == "current" or not records:
        return {}
    settled = [r for r in records if not unsettled(r)]
    ok = [r for r in settled if r.get("generation_ok")]
    failed = [r for r in settled if not r.get("generation_ok")]
    owed = [r for r in records if awaiting_repair(r)]
    errored = [r for r in records if "error" in r]
    firsts = ok + owed  # every analysis whose model's first output is final
    v2 = [r for r in firsts if r.get("pipeline") == "v2"]
    packs: dict[str, dict[str, Any]] = {}

    def own_pack(ticker: str) -> dict[str, Any]:
        """The pack this arm read, loaded once: the builds and every measure read it, so none reads another arm's."""
        if ticker not in packs:
            packs[ticker] = load_pack(ticker, system)
        return packs[ticker]

    builds: Counter[str] = Counter()
    pack_hashes: dict[str, str] = {}
    for r in records:  # every record of the label, a failed or pending one too: each was made by some build
        if r.get("attempts") or r.get("prior_attempts"):
            builds[build(r, own_pack(r["ticker"]))] += 1
            pack_hashes[r["ticker"]] = str(r.get("pack_sha256") or "")[:12]
    first_gate: list[dict[str, Any]] = []
    first_backstops: list[dict[str, Any]] = []
    first_scored = 0
    as_run: list[dict[str, Any]] = []
    probe_hits: list[dict[str, Any]] = []
    opus_flags: list[dict[str, Any]] = []
    opus_other: list[dict[str, Any]] = []
    opus_views: Counter[str] = Counter()
    opus_read: set[str] = set()
    causes: Counter[str] = Counter()
    causes_read = 0
    verified: Counter[str] = Counter()
    judgement: Counter[str] = Counter()
    evaluative: list[dict[str, Any]] = []
    evaluative_scope = 0
    forecasts: list[dict[str, Any]] = []
    watch_items = 0
    forms: list[dict[str, Any]] = []
    debt: list[dict[str, Any]] = []
    old: Counter[str] = Counter()
    for r in firsts:
        ticker = r["ticker"]
        pack = own_pack(ticker)
        first = first_output(r)
        if first is not None:  # the model's own first output, every record and pipeline alike, under the gate now
            gate_items, backstop_items = first_try(sentences_of(first), pack, probes.series_by_id(pack))
            first_scored += 1
            first_gate += [{"ticker": ticker, **item} for item in gate_items]
            first_backstops += [{"ticker": ticker, **item} for item in backstop_items]
            if old_gate is not None:
                old["first"] += bool(old_gate[1].check(sentences_of(first), pack)["passed"])
        recorded = r.get("raw_first_pass_gate") if r.get("pipeline") == "v2" else r.get("first_pass_gate", r["gate"])
        if isinstance(recorded, dict):  # as run: the cross-check, under the gate of its day
            as_run.append({"ticker": ticker, "basis": "raw_first_pass_gate" if r.get("pipeline") == "v2" else "first_pass_gate",
                           "failures": len(recorded.get("failures", []))})
    for r in ok:
        ticker = r["ticker"]
        pack = own_pack(ticker)
        keys = probes.series_by_id(pack)
        final = sentences_of(r["output"])
        for sentence in final:
            result, resolved = factcheck.analyse_sentence(sentence, pack)
            verified[ticker] += sum(1 for c in result.claims if c["status"] == "verified")
            probe_hits += [{"ticker": ticker, **hit} for hit in probes.probe_sentence(sentence, pack, resolved, keys)]
        audit = _audit_by(label, "semantics", system, ticker, OPUS)
        if audit is not None:
            view = audit.get("view", 1)
            opus_views[str(view)] += 1
            opus_read.add(ticker)
            for item in audit.get("items", []):
                if item["label"] != "mismatch":
                    continue
                kind = classify_flag(item, final, pack, view)
                flag = {"ticker": ticker, "source": f"{OPUS} (view {view})", "sentence": item["sentence"], "claim": item["claim"],
                        "detail": item.get("reason", "")}
                if kind == "substantive":
                    opus_flags.append(flag)
                else:  # not counted, but listed for reading, never dropped
                    opus_other.append({**flag, "class": kind})
        cause_audit = _audit_by(label, "causes", system, ticker, OPUS)
        if cause_audit is not None:
            causes_read += 1
            causes.update(item["label"] for item in cause_audit.get("items", []))
        judgement.update(calibration.judgement_outside_watch(final))
        found = calibration.evaluative(final)
        evaluative += [{"ticker": ticker, **hit} for hit in found["hits"]]
        evaluative_scope += found["sentences"]
        watch = calibration.watch_forecasts(final)
        forecasts += [{"ticker": ticker, **hit} for hit in watch["hits"]]
        watch_items += watch["items"]
        forms.append(calibration.form(r["output"], SECTION_KEYS))
        reference = _reference_pack(ticker)
        state = broken_net_cash(final, pack, reference) if reference else None
        if state is not None:
            debt.append({"ticker": ticker, **state})
        if old_gate is not None:
            old["final"] += bool(old_gate[1].check(final, pack)["passed"])
    # Mislabels are sentences: a probe and the auditor on one error, or two figures of one error ("from -$34.3 billion
    # to -$92.2 billion"), count once. A sentence the broken-net-cash measure counts as stated is counted there alone.
    stated = {(d["ticker"], _plain(s["sentence"])) for d in debt for s in d["stated"]}
    disclosing = {(d["ticker"], _plain(s["sentence"])) for d in debt for s in d["disclosed"]}
    mislabels: dict[tuple[str, str, str], dict[str, Any]] = {}
    for hit in [{"source": f"probe {h['kind']}", **h} for h in probe_hits if h["kind"] in MISLABEL_KINDS] + opus_flags:
        key = (hit["ticker"], _plain(hit["sentence"]), hit["claim"])
        if key in mislabels:  # a probe and the auditor on the same claim: one claim, both sources named
            mislabels[key]["source"] += f" + {hit['source']}"
        else:
            mislabels[key] = {k: hit[k] for k in ("ticker", "source", "sentence", "claim", "detail")}
            if key[:2] in stated:
                mislabels[key]["also"] = "also in broken net cash, counted there"
            elif key[:2] in disclosing:
                mislabels[key]["also"] = "a sentence disclosing a break"
    sentences = {key[:2] for key in mislabels} - stated
    by_source = {name: {key[:2] for key, item in mislabels.items() if name in item["source"]} & sentences
                 for name in ("probe", OPUS)}
    # Two bases, each the same for every arm: the probes alone over every output (P and Q have no Opus audit), and
    # the probes with Opus's flags over the outputs Opus read (§3's target), never one beside the other in one row.
    audited = {key for key in sentences if key[0] in opus_read}
    in_scope = [d for d in debt if d["state"] is not None]
    n = len(ok)
    return {
        "analyses": n, "failed_generations": len(failed), "pipeline_v2": len(v2),
        "awaiting_repair": len(owed), "provider_errors": len(errored),
        "builds": dict(builds), "pack_sha256": dict(sorted(pack_hashes.items())),
        "passes_without_repair": sum(1 for r in ok if not repaired(r) and r["gate"].get("passed")),
        "repairs": dict(Counter(r.get("repair_kind") or ("version 1" if r.get("pipeline") != "v2" else "unknown")
                                for r in ok if repaired(r))),
        "repairs_sent_or_owed": sum(1 for r in firsts if repaired(r) or awaiting_repair(r)),
        "repairs_for_broken_debt_alone": [{"ticker": r["ticker"], "failures": failures} for r in firsts
                                          if (failures := broken_debt_repair(r))],
        "code_fixed_passes": sum(1 for r in v2 if not repaired(r) and r["gate"].get("passed")
                                 and not (r.get("raw_first_pass_gate") or {}).get("passed", True)),
        "first_try_scored": first_scored, "first_try_errors": len(first_gate), "first_try_failures": first_gate,
        "first_try_backstops": len(first_backstops), "first_try_backstop_hits": first_backstops, "first_try_as_run": as_run,
        "retyped": [{"ticker": r["ticker"], **change} for r in v2 for change in r.get("retyped") or []],
        "verified_claims": sum(verified.values()), "mislabels": len(sentences), "mislabel_claims": len(mislabels),
        "probe_mislabels": len(by_source["probe"]), "opus_mislabels": len(by_source[OPUS]),
        "audited_verified_claims": sum(verified[ticker] for ticker in opus_read), "audited_mislabels": len(audited),
        "audited_probe_mislabels": len(by_source["probe"] & audited), "audited_opus_mislabels": len(by_source[OPUS] & audited),
        "opus_substantive": len(opus_flags), "opus_audited": sum(opus_views.values()), "opus_views": dict(opus_views),
        "opus_other": opus_other, "mislabel_list": list(mislabels.values()),
        **{kind: [h for h in probe_hits if h["kind"] == kind] for kind in OWN_ROW_KINDS},
        "logic_slips": [h for h in probe_hits if h["kind"] in probes.MEASURE_KINDS],
        "judgement_outside_watch": [judgement["judgements"], judgement["sentences"]],
        "evaluative": [len(evaluative), evaluative_scope], "evaluative_list": evaluative,
        "watch_forecasts": [len(forecasts), watch_items], "watch_forecast_list": forecasts,
        "broken_net_cash": {
            "analyses": len(in_scope), "stated_as_fact": sum(1 for d in in_scope if d["state"] == "stated as fact"),
            "disclosed": sum(1 for d in in_scope if d["state"] == "disclosed"),
            # Per check kind: (analyses stating a figure of that kind as fact, analyses whose company has the check).
            "by_check": {kind: [sum(1 for d in in_scope if kind in d["checks"] and d["state"] == "stated as fact"
                                    and any(kind in s["breaks"] for s in d["stated"])),
                                sum(1 for d in in_scope if kind in d["checks"])] for kind in ("debt_break", "liquidity_break")},
            "stated_sentences": sum(len(d["stated"]) for d in in_scope),
            "peer_sentences": sum(len(d["peer"]) for d in debt), "peer_analyses": sum(1 for d in debt if d["peer"]),
            "list": debt},
        "cause_support": {"audited": causes_read, **{k: causes.get(k, 0) for k in ("supported", "partial", "unsupported")}},
        "causes_per_analysis": sum(1 for r in ok for s in sentences_of(r["output"]) if s["type"] == "cause") / n if n else None,
        "form": {"words_mean": statistics.mean(f["words"] for f in forms) if forms else None,
                 "words_max": max((f["words"] for f in forms), default=None),
                 "sentences_mean": statistics.mean(f["sentences"] for f in forms) if forms else None,
                 "sentences_max": max((f["sentences"] for f in forms), default=None),
                 "all_sections": sum(1 for f in forms if not f["missing"]),
                 "within_target": sum(1 for f in forms if f["words"] <= 700 and f["sentences"] <= 30 and not f["missing"])},
        "cost_mean": stats.get("cost_mean"), "cost_n": stats.get("cost_n"),
        "latency_p50": stats.get("latency_p50"), "latency_p90": stats.get("latency_p90"),
        "shared_prefix_tokens": stats.get("shared_prefix_tokens", {}), "warm_first_attempts": stats.get("warm_first_attempts"),
        "old_gate": ({"commit": old_gate[0], "first_try": old["first"], "first_try_of": first_scored, "final": old["final"]}
                     if old_gate is not None else None),
    }


def _left_out_lines(table: dict[str, Any]) -> list[str]:
    notes = [f"{system}: {', '.join(f'{n} {state}' for state, n in sorted(data['left_out'].items()))}"
             for system, data in table.items() if data.get("left_out")]
    return [f"Left out (refused by the auditor, or pending: a failed audit, or one of an output that has since "
            f"changed or is not final): {'; '.join(notes)}.", ""] if notes else []


def _panel_verdict(results: list[dict[str, Any]], criterion: str) -> str:
    finals = {r["result"][criterion]["final"] for r in results}
    return finals.pop() if len(finals) == 1 else "tie"


def judge_matrix(label: str, systems: list[str], tickers: list[str]) -> dict[str, Any]:
    """One verdict per (company, pair). Each judge's own verdict needs both orders to agree. Where judges
    from neither output's family exist, the verdict is theirs (all of them agreeing); otherwise it is the
    consensus panel's (one judge from each family, both agreeing), counted only when the panel is complete.
    ``consensus`` keeps the consensus panel's verdicts separately wherever one ran, for comparison."""
    panels: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    generations: dict[tuple[str, str], Optional[dict[str, Any]]] = {}
    stale = 0
    for path in (RUNS / label / "judge").glob("*/*.json"):
        record = json.loads(path.read_text())
        if record["ticker"] in tickers and record["x"] in systems and record["y"] in systems:
            sides = []
            for side, key in ((record["x"], "x_sha256"), (record["y"], "y_sha256")):
                if (side, record["ticker"]) not in generations:
                    generations[(side, record["ticker"])] = _generation(label, side, record["ticker"])
                sides.append((generations[(side, record["ticker"])], key))
            if any(unsettled(g) or not read_same_output(record, key, output_sha256(g)) for g, key in sides):
                stale += 1  # a verdict on an output that is not final, or that has since changed
                continue
            panels[(record["ticker"], record["x"], record["y"])].append(record)
    wins: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    consensus: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    criteria: dict[tuple[str, str], dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    both: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    by_judge: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    agreement: dict[str, list[bool]] = defaultdict(list)
    between_judges: list[bool] = []
    panel_kinds: Counter[str] = Counter()
    judged_by: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    judged = incomplete = unjudged = 0
    for (_, x, y), records in panels.items():
        key = (x, y)
        forfeit = next((r for r in records if "forfeit" in r), None)
        if forfeit:
            wins[key][y if forfeit["forfeit"] == x else x if forfeit["forfeit"] == y else "tie"] += 1
            continue
        results = [r for r in records if r.get("result")]
        if not results:  # every judge call for this pair failed or was refused: no verdict yet, not a panel
            unjudged += 1
            continue
        for r in results:
            agreement[r["judge"]].append(r["result"]["overall"]["agreed"])
            by_judge[f"{x}|{y}"][r["judge"]][r["result"]["overall"]["final"]] += 1
        own_family = [r for r in results if ARMS[r["judge"]].family in {_family(x), _family(y)}]
        neutral = [r for r in results if r not in own_family]
        if len(own_family) >= 2:
            consensus[key][_panel_verdict(own_family, "overall")] += 1
            between_judges.append(len({r["result"]["overall"]["final"] for r in own_family}) == 1)
        panel = neutral or (own_family if len(own_family) >= 2 else [])
        if not panel:
            incomplete += 1
            continue
        judged += 1
        panel_kinds["neutral" if neutral else "consensus"] += 1
        judged_by[key][" + ".join(sorted(r["judge"] for r in neutral)) if neutral
                       else "consensus of " + " + ".join(sorted(r["judge"] for r in own_family))] += 1
        wins[key][_panel_verdict(panel, "overall")] += 1
        verdicts = {criterion: _panel_verdict(panel, criterion) for criterion in CRITERIA}
        for criterion, verdict in verdicts.items():
            criteria[key][criterion][verdict] += 1
        both[key]["of"] += 1
        for side in (x, y):  # §3's judge target read jointly: one pair's grounding and calibration, each won or tied
            both[key][side] += all(verdicts[c] in (side, "tie") for c in BOTH_CRITERIA)
    return {
        "judged_pairs": judged,
        "incomplete_panels": incomplete,
        "unjudged_pairs": unjudged,
        "stale_verdicts": stale,
        "panels": dict(panel_kinds),
        "wins": {f"{x}|{y}": dict(c) for (x, y), c in wins.items()},
        "consensus": {f"{x}|{y}": dict(c) for (x, y), c in consensus.items()},
        "judged_by": {f"{x}|{y}": dict(c) for (x, y), c in judged_by.items()},
        "criteria": {f"{x}|{y}": {k: dict(v) for k, v in c.items()} for (x, y), c in criteria.items()},
        "grounding_and_calibration": {f"{x}|{y}": dict(c) for (x, y), c in both.items()},
        "by_judge": {pair: {judge: dict(c) for judge, c in judges.items()} for pair, judges in by_judge.items()},
        "swap_agreement": {judge: (sum(v) / len(v) if v else None, len(v)) for judge, v in agreement.items()},
        "between_judges": (sum(between_judges) / len(between_judges) if between_judges else None, len(between_judges)),
    }


JOINT = "grounding and calibration, each won or tied"


def judge_criteria(matrix: dict[str, Any], pair: str) -> list[tuple[str, tuple[int, int, int]]]:
    """A pair's (``x|y``) panel verdicts per criterion, as (x's wins, y's wins, ties or splits), then ``JOINT``: (the
    pairs whose grounding and calibration x each won or tied, the same for y, the pairs judged on criteria)."""
    x, y = pair.split("|")
    by = matrix["criteria"].get(pair, {})
    both = matrix.get("grounding_and_calibration", {}).get(pair, {})
    return ([(c, (by.get(c, {}).get(x, 0), by.get(c, {}).get(y, 0), by.get(c, {}).get("tie", 0))) for c in CRITERIA]
            + [(JOINT, (both.get(x, 0), both.get(y, 0), both.get("of", 0)))])


def build_warnings(runs: dict[str, dict[str, Any]], systems: list[str]) -> list[str]:
    """A warning per arm whose records in one run (``runs``: label -> summary), or across the runs, came from more than
    one build: another pipeline, prompt or pack build (``build``), or, between runs, another pack of one company. Its
    measures pool those builds, so the warning goes at the top of the report."""
    out = []
    for system in systems:
        measured = {label: (summary["splits"]["all"].get("measures") or {}).get(system) for label, summary in runs.items()}
        measured = {label: m for label, m in measured.items() if m}
        builds = {label: sorted(m.get("builds", {})) for label, m in measured.items()}
        for label, made in builds.items():
            if len(made) > 1:
                counts = measured[label]["builds"]
                out.append(f"`{system}` in `{label}` holds records of {len(made)} builds, pooled in its measures: "
                           + "; ".join(f"{b} ({counts[b]})" for b in made) + ".")
        if len(measured) > 1:
            distinct = {tuple(made) for made in builds.values()}
            hashes: dict[str, set[str]] = defaultdict(set)
            for m in measured.values():
                for ticker, sha in m.get("pack_sha256", {}).items():
                    hashes[ticker].add(sha)
            moved = sorted(ticker for ticker, shas in hashes.items() if len(shas) > 1)
            if len(distinct) > 1 or moved:
                out.append(f"`{system}`'s runs were made by different builds, so its range and pooled values mix them: "
                           + "; ".join(f"{label}: {', '.join(made)}" for label, made in builds.items())
                           + (f"; another pack in one run than another for {', '.join(moved)}" if moved else "") + ".")
    return [f"> **Warning:** {line}" for line in out] + ([""] if out else [])


def pending_warnings(runs: dict[str, dict[str, Any]], systems: list[str]) -> list[str]:
    """A warning per arm and run (``runs``: label -> summary) whose records generate still owes a call: a repair (each
    counted as not passing, its final output in no row) or a whole generation after a provider error (in no row).
    The run is not finished, and its pass rate is not the one the stop rules read, so the warning goes at the top."""
    out = []
    for label, summary in runs.items():
        for system in systems:
            m = (summary["splits"]["all"].get("measures") or {}).get(system) or {}
            owed, errors = m.get("awaiting_repair", 0), m.get("provider_errors", 0)
            parts = ([f"{owed} repair{'s' * (owed != 1)} awaiting generate, counted as not passing"] * bool(owed)
                     + [f"{errors} generation{'s' * (errors != 1)} awaiting generate after a provider error, in no row"] * bool(errors))
            if parts:
                out.append(f"`{system}` in `{label}`: {'; '.join(parts)}. Re-run generate with the same label, then the "
                           "audits and this report, before reading its measures.")
    return [f"> **Warning:** {line}" for line in out] + ([""] if out else [])


def render(label: str, systems: list[str], summary: dict[str, Any]) -> str:
    lines = [f"# Bake-off report: `{label}`", "", "Generated by `python -m evals.trend_depth.report`.", "",
             *build_warnings({label: summary}, systems), *pending_warnings({label: summary}, systems)]
    for split in ("dev", "holdout", "all"):
        block = summary["splits"][split]
        lines += [f"## {split}: {block['companies']} companies", "",
                  "| System | Backend | Generated | Gate pass, first try (as run · current gate) | Gate pass after one repair (as run · current gate) | Failed claims, first try | Claims per analysis | Causal sentences | Passages cited | Words | API list cost per run | Latency p50 / p90 (s) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for system in systems:
            s = block["arms"].get(system, {})
            if not s:
                continue
            if system == "current":
                lines.append(f"| current (production) | production code | {s.get('generated')}/{s['n']} | by construction | — | — | — | 0 | 0 | "
                             f"{s.get('words_mean', 0):.0f} | ${s.get('cost_mean') or 0:.5f} | {s.get('latency_p50', 0):.1f} / {s.get('latency_p90', 0):.1f} |")
                continue
            generated = (f"{s.get('generated')}/{s['n']}"
                         + (f", {s['pending_repairs']} awaiting a repair" if s.get("pending_repairs") else "")
                         + (f", {s['provider_errors']} awaiting generate (provider error)" if s.get("provider_errors") else ""))
            lines.append(
                f"| {system} | {', '.join(s.get('backends', []))} | {generated} | {s.get('first_pass_gate', 0)} · {s.get('first_pass_gate_now', 0)} of {s.get('generated', 0)} | "
                f"{s.get('final_gate', 0)} · {s.get('final_gate_now', 0)} of {s.get('generated', 0)} | {s.get('first_pass_failed_claims', 0)} of {s.get('first_pass_claims', 0)} | "
                f"{s.get('claims_mean', 0):.0f} | {s.get('causes_mean', 0):.1f} | {s.get('passages_cited_mean', 0):.1f} | "
                f"{s.get('words_mean', 0):.0f} (max {s.get('words_max', 0)}) | ${s.get('cost_mean') or 0:.4f} | "
                f"{s.get('latency_p50', 0):.0f} / {s.get('latency_p90', 0):.0f} |")
        lines.append("")
        failure_rows = [(system, block["arms"][system].get("failure_classes_first_pass", {})) for system in systems
                        if system != "current" and block["arms"].get(system)]
        if failure_rows:
            classes = sorted({c for _, f in failure_rows for c in f})
            lines += ["First-try gate failures by class:", "", "| System | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
            for system, failures in failure_rows:
                lines.append(f"| {system} | " + " | ".join(str(failures.get(c, 0)) for c in classes) + " |")
            lines.append("")
        mix_rows = [(system, block["arms"][system].get("sentence_mix", {})) for system in systems if system != "current" and block["arms"].get(system)]
        if mix_rows:
            lines += ["Sentence types (share of sentences):", "", "| System | fact | comparison | cause | judgement | sentences per analysis |", "|---|---|---|---|---|---|"]
            for system, mix in mix_rows:
                lines.append(f"| {system} | " + " | ".join(f"{mix.get(k, 0) * 100:.0f}%" for k in ("fact", "comparison", "cause", "judgement"))
                             + f" | {block['arms'][system].get('sentences_mean', 0):.1f} |")
            lines.append("")
        for folder, causes in (block.get("causes") or {}).items():
            if not causes:
                continue
            title = ("auditor from another model family" if folder == "causes"
                     else f"one auditor for every system, {folder.removeprefix('causes-by-')}; a system of its own family is marked *")
            lines += [f"Causal claims checked against their cited passages ({title}):", "",
                      "| System | Supported | Partial | Unsupported | Auditor |", "|---|---|---|---|---|"]
            for system, data in causes.items():
                c = data["counts"]
                total = sum(c.values()) or 1
                own = folder != "causes" and system != "gold" and ARMS[folder.removeprefix("causes-by-")].family == _family(system)
                lines.append(f"| {system}{' *' if own else ''} | {c.get('supported', 0)} ({c.get('supported', 0) / total * 100:.0f}%) | "
                             f"{c.get('partial', 0)} ({c.get('partial', 0) / total * 100:.0f}%) | "
                             f"{c.get('unsupported', 0)} ({c.get('unsupported', 0) / total * 100:.0f}%) | "
                             f"{', '.join(data['auditors'])} |")
            lines.append("")
            lines += _left_out_lines(causes)
        for folder, semantics in (block.get("semantics") or {}).items():
            if not semantics:
                continue
            title = ("auditor from another model family" if folder == "semantics"
                     else f"one auditor for every system, {folder.removeprefix('semantics-by-')}")
            lines += [f"Verified numbers checked for the metric and period the sentence gives them ({title}). A flag on a "
                      "bound the value satisfies (under view 1, which never told the auditor the claim was a bound), or on "
                      "a number several cited values match, is counted apart from the substantive ones "
                      "(`semantics.classify_flag`). View is the auditor's view of the matches "
                      "(`semantics.VIEW`; 1 showed no signed value, bound or twin):", "",
                      "| System | Analyses | Claims consistent | Flagged | of which substantive | bound | ambiguous | Not labelled | Auditor | View |",
                      "|---|---|---|---|---|---|---|---|---|---|"]
            for system, data in semantics.items():
                c = data["counts"]
                views = ", ".join(f"{view} ({n})" for view, n in sorted(data.get("views", {}).items()))
                lines.append(f"| {system} | {data['analyses']} | {c.get('consistent', 0)} | {c.get('mismatch', 0)} | "
                             f"{c.get('mismatch_substantive', 0)} | {c.get('mismatch_bound', 0)} | {c.get('mismatch_ambiguous', 0)} | "
                             f"{c.get('missing', 0)} | {', '.join(data['auditors'])} | {views} |")
            lines.append("")
            lines += _left_out_lines(semantics)
        measured = [system for system in systems if (block.get("measures") or {}).get(system)]
        if measured:
            lines += ["DEEPSEEK-ERRORS.md §3 measures, each beside its target for the candidate (counts before hand reading; "
                      "the items are listed under \"For hand reading\"):", "",
                      "| Measure | Target for C | " + " | ".join(measured) + " |", "|---|---|" + "---|" * len(measured)]
            rows = {system: measure_rows(block["measures"][system]) for system in measured}
            for i, (name, target, *_) in enumerate(rows[measured[0]]):
                lines.append(f"| {name} | {target} | " + " | ".join(rows[system][i][2] for system in measured) + " |")
            lines += ["", "Builds (pipeline · prompt sha256 · packs; DEEPSEEK-ERRORS.md §3 step 3's record of what ran): "
                      + "; ".join(f"{system}: " + ", ".join(f"{b} ({n})" for b, n in sorted(block["measures"][system]["builds"].items()))
                                  for system in measured) + ".", ""]
        matrix = block["judge"]
        if matrix["judged_pairs"]:
            lines += [f"Pairwise preference (judged pairs: {matrix['judged_pairs']}; a verdict counts only when both orders agree; "
                      "a neutral judge's verdict where one ran, else the consensus panel's):", "",
                      "| Pair (x vs y) | x wins | y wins | tie or split | Judged by |", "|---|---|---|---|---|"]
            for pair, counts in sorted(matrix["wins"].items()):
                x, y = pair.split("|")
                who = "; ".join(f"{panel} ({n})" for panel, n in sorted(matrix["judged_by"].get(pair, {}).items()))
                lines.append(f"| {x} vs {y} | {counts.get(x, 0)} | {counts.get(y, 0)} | {counts.get('tie', 0)} | {who} |")
            if matrix["consensus"]:
                lines += ["", "Consensus panels (one judge from each output's family; a verdict only when both agree):", "",
                          "| Pair (x vs y) | x wins | y wins | tie or split |", "|---|---|---|---|"]
                for pair, counts in sorted(matrix["consensus"].items()):
                    x, y = pair.split("|")
                    lines.append(f"| {x} vs {y} | {counts.get(x, 0)} | {counts.get(y, 0)} | {counts.get('tie', 0)} |")
            lines += ["", "Each judge's own verdicts (both orders agreeing), before the panel combines them:", "",
                      "| Pair (x vs y) | Judge | x wins | y wins | tie or split |", "|---|---|---|---|---|"]
            for pair, judges in sorted(matrix["by_judge"].items()):
                x, y = pair.split("|")
                for judge, counts in sorted(judges.items()):
                    lines.append(f"| {x} vs {y} | {judge} | {counts.get(x, 0)} | {counts.get(y, 0)} | {counts.get('tie', 0)} |")
            lines += ["", f"The panel's verdicts per criterion, both orders agreeing (DEEPSEEK-ERRORS.md §3's judge target: "
                      f"{JUDGE_TARGET}). The last row of a pair counts the pairs whose grounding and calibration a side "
                      "each won or tied:", "",
                      "| Pair (x vs y) | Criterion | x | y | tie or split |", "|---|---|---|---|---|"]
            for pair in sorted(matrix["criteria"]):
                x, y = pair.split("|")
                lines += [f"| {x} vs {y} | {name} | {a} | {b} | {f'of {c}' if name == JOINT else c} |"
                          for name, (a, b, c) in judge_criteria(matrix, pair)]
            lines += ["", "Position-swap agreement on the overall verdict:", ""]
            for judge, (rate, n) in matrix["swap_agreement"].items():
                lines.append(f"- {judge}: {rate * 100:.0f}% of {n} pairs" if rate is not None else f"- {judge}: no pairs")
            rate, n = matrix["between_judges"]
            if n:
                lines.append(f"- between the judges of a two-judge panel: {rate * 100:.0f}% of {n} pairs")
            if matrix["incomplete_panels"]:
                lines.append(f"- incomplete consensus panels left out: {matrix['incomplete_panels']}")
            lines.append("")
        left_out = [(label, matrix[key]) for key, label in (
            ("unjudged_pairs", "pairs with no verdict yet (each judge call failed or was refused)"),
            ("stale_verdicts", "verdicts left out because an output is not final or has changed since")) if matrix.get(key)]
        if left_out:  # shown even when no pair was judged, which is when it matters most
            lines += [f"- {label}: {n}" for label, n in left_out] + [""]
    lines += ["## Cost at volume (fresh generations per month, API list prices)", "",
              "| System | Per run | 1,000 runs | 10,000 runs |", "|---|---|---|---|"]
    for system in systems:
        s = summary["splits"]["all"]["arms"].get(system, {})
        cost = s.get("cost_mean")
        if cost is None:
            continue
        lines.append(f"| {system} | ${cost:.4f} | ${cost * 1000:,.2f} | ${cost * 10000:,.2f} |")
    lines.append("")
    measures = summary["splits"]["all"].get("measures") or {}
    if any(measures.values()):
        lines += ["## For hand reading", "", "Every item a §3 measure counts, all companies, per system.", ""]
        for system in systems:
            if measures.get(system):
                lines += hand_reading(system, measures[system])
    return "\n".join(lines)


# --- The §3 measures as rows: one run's table, and several runs side by side ----------------------------------------

Row = tuple[str, str, str, Optional[float], Optional[tuple[float, Optional[float], float]], Callable[[float], str]]


def _count(value: float) -> str:
    return f"{value:g}"


def _percent(value: float) -> str:
    return f"{value:.0f}%"


def _percent1(value: float) -> str:
    return f"{value:.1f}%"


def _two(value: float) -> str:
    return f"{value:.2f}"


def _one(value: float) -> str:
    return f"{value:.1f}"


def _dollars(value: float) -> str:
    return f"${value:.4f}"


def measure_rows(m: dict[str, Any]) -> list[Row]:
    """Each §3 measure of one arm (``arm_measures``) as (measure, target for C, as shown, value for a range of runs,
    (numerator, denominator or None for a count, scale) to pool runs, or None, and the value's format). A row over
    analyses names its n: the outputs generated, or for a pass, every analysis a failed generation included."""
    rows: list[Row] = []

    def ratio(name: str, target: str, num: float, den: float, scale: float, shown: Callable[[float], str],
              fmt: Callable[[float], str], empty: str = "—") -> None:
        value = num / den * scale if den else None
        rows.append((name, target, shown(value) if value is not None else empty, value, (num, den, scale) if den else None, fmt))

    def count(name: str, target: str, num: float, shown: str) -> None:
        rows.append((name, target, shown, float(num), (num, None, 1.0), _count))

    def level(name: str, target: str, value: Optional[float], fmt: Callable[[float], str], shown: Optional[str] = None) -> None:
        rows.append((name, target, (shown or fmt(value)) if value is not None else "—", value, None, fmt))

    n, n2, failed = m["analyses"], m["pipeline_v2"], m.get("failed_generations", 0)
    owed, errors = m.get("awaiting_repair", 0), m.get("provider_errors", 0)
    tried = n + failed + owed
    k = m["passes_without_repair"]
    among = [f"{failed} failed generation{'s' * (failed != 1)}"] * bool(failed) + [f"{owed} awaiting a repair"] * bool(owed)
    ratio("Passes without a model repair", "at least 85% pooled; no run below 80%", k, tried, 100,
          lambda v: f"{k} of {tried} ({v:.0f}%" + (f"; {' and '.join(among)} among them" if among else "") + ")", _percent)
    count("Failed generations (the model's own: invalid replies or a refusal; each counts as not passing)", "0", failed,
          f"{failed} of {tried}")
    count("Repairs awaiting generate (a provider error or an interruption; each counts as not passing, as its first pass "
          "failed the gate; re-run generate)", "0", owed, f"{owed} of {tried}")
    count("Generations awaiting generate (a provider error: no output yet, so in no row until generate makes it)", "0",
          errors, str(errors))
    ratio("of which passed after the code's retyping (version 2 records)", "—", m["code_fixed_passes"], n2, 100,
          lambda v: f"{m['code_fixed_passes']} of {n2}", _percent)
    alone, sent = len(m.get("repairs_for_broken_debt_alone", [])), m.get("repairs_sent_or_owed", 0)
    count("Repairs sent for broken net cash alone (the gate's broken_debt backstop reads the arm's own pack's breaks, and "
          "packs/ records none: only an arm reading packs-v2 can have one; K0's and Q's same figures count under broken "
          "net cash below)", "—", alone, f"{alone} of {sent} repairs")
    e, b, scored = m["first_try_errors"], m["first_try_backstops"], m["first_try_scored"]
    ratio("First-try gate failures per analysis: failing claims of the model's own first output, gate now "
          "(subtract gate artefacts by hand)", "0.15 or less", e, scored, 1, lambda v: f"{v:.2f} ({e} in {scored} first outputs)", _two)
    ratio("First-try backstop hits per analysis: claims the backstops fail beyond the gate's (broken net cash apart)",
          "— (each a repair under --pipeline v2)", b, scored, 1, lambda v: f"{v:.2f} ({b} in {scored} first outputs)", _two)
    probe, claims = m["probe_mislabels"], m["verified_claims"]
    ratio("Mislabelled sentences per 1,000 verified claims, probes R1, R2a, R2c and R3 alone, every output (a sentence "
          "stating broken net cash is counted there instead)", "— (the basis every arm shares: P and Q have no Opus audit)",
          probe, claims, 1000, lambda v: f"{v:.1f} ({probe} sentence{'s' * (probe != 1)} in {claims:,} verified claims of {n} outputs)",
          _one)
    hits, read, audited = m["audited_mislabels"], m["audited_verified_claims"], m["opus_audited"]
    views = ", ".join(f"{view} ({c})" for view, c in sorted(m["opus_views"].items()))
    ratio("Mislabelled sentences per 1,000 verified claims: probes R1, R2a, R2c, R3 and Opus substantive flags, over the "
          "outputs Opus read (a sentence stating broken net cash is counted there instead)",
          "3.5 or less in each run, after hand reading", hits, read, 1000,
          lambda v: f"{v:.1f} ({hits} sentence{'s' * (hits != 1)} in {read:,} verified claims of the {audited} of {n} outputs "
                    f"Opus read: probes {m['audited_probe_mislabels']}, Opus {m['audited_opus_mislabels']}; view {views})", _one,
          empty=f"— (Opus read none of {n})")  # never a probes-only rate under the probes-and-Opus target
    j, d = m["judgement_outside_watch"]
    ratio("Judgement share outside the watch list", "3–12%", j, d, 100, lambda v: f"{v:.1f}% ({j} of {d})", _percent1)
    w, d = m["evaluative"]
    ratio("Evaluative words in fact and comparison sentences, outside arc and watch", "3% or less", w, d, 100,
          lambda v: f"{v:.1f}% ({w} of {d})", _percent1)
    f, d = m["watch_forecasts"]
    ratio("Watch items with forecast wording, per 60 (read by hand)", "2 or fewer per 60", f, d, 60,
          lambda v: f"{v:.1f} ({f} of {d})", _one)
    count("Unsigned falls (probe U1)", "0 (guard)", len(m["U1"]), str(len(m["U1"])))
    count("Dollar figures without a scale matched to a passage's raw literal (probe unitless_dollars)", "—",
          len(m["unitless_dollars"]), str(len(m["unitless_dollars"])))
    count("Net margin said above or below operating margin against the gap's sign (probe gap_direction)", "—",
          len(m["gap_direction"]), str(len(m["gap_direction"])))
    debt = m["broken_net_cash"]
    checks = "; ".join(f"{kind.replace('_', ' ')} {stated} of {of}" for kind, (stated, of) in debt["by_check"].items() if of)
    count("Broken net cash stated as fact: analyses of a company whose packs-v2 pack names a debt or liquidity break, "
          "its breaks read for every arm", "0 stated as fact", debt["stated_as_fact"],
          f"{debt['stated_as_fact']} of {debt['analyses']} ({debt['disclosed']} disclosed; {checks})" if debt["analyses"] else "— (none)")
    count("Sentences stating a broken figure without disclosing the break in that sentence", "0", debt["stated_sentences"],
          str(debt["stated_sentences"]) if debt["analyses"] else "— (none)")
    count("Version-1 net-cash peer ranks and medians built on a peer's broken year (peer_break; informational: only an "
          "arm reading packs/ can cite one)", "—", debt["peer_sentences"],
          f"{debt['peer_sentences']} sentences in {debt['peer_analyses']} analyses")
    c = m["cause_support"]
    total = c["supported"] + c["partial"] + c["unsupported"]
    ratio("Cause support, Opus: supported / partial / unsupported", "at least 72% supported, at most 2% unsupported (guard)",
          c["supported"], total, 100, lambda v: f"{v:.0f}% / {c['partial'] / total * 100:.0f}% / {c['unsupported'] / total * 100:.0f}% "
                                                f"of {total} (Opus read {c['audited']} of {n})", _percent)
    ratio("Cause sentences per analysis", "at least 6 (guard)", (m["causes_per_analysis"] or 0) * n, n, 1,
          lambda v: f"{v:.1f} (in {n} outputs)", _one)
    form = m["form"]
    level("Words per analysis, mean (max)", "700 or fewer", form["words_max"], _count,
          f"{form['words_mean']:.0f} ({form['words_max']}) in {n} outputs" if n else None)
    level("Sentences per analysis, mean (max)", "30 or fewer", form["sentences_max"], _count,
          f"{form['sentences_mean']:.1f} ({form['sentences_max']}) in {n} outputs" if n else None)
    ratio("Analyses with all 7 sections", "all", form["all_sections"], n, 100, lambda v: f"{form['all_sections']} of {n}", _percent)
    warm, firsts = m.get("warm_first_attempts") or (0, 0)
    prefix = ", ".join(f"{tokens:,}" for tokens in sorted(set((m.get("shared_prefix_tokens") or {}).values())))
    level("API list cost per analysis", "at most $0.0075 off-peak", m["cost_mean"], _dollars,
          f"{_dollars(m['cost_mean'])} over {m.get('cost_n')} generations, failed ones included"
          + (f" (first requests read a {prefix}-token shared prefix; {warm} of {firsts} read more, priced at it)" if prefix else "")
          if m["cost_mean"] is not None else None)
    for name, target, value in (("Latency p50 (s)", "at most 10.5", m["latency_p50"]), ("Latency p90 (s)", "at most 13", m["latency_p90"])):
        level(f"{name}, {QUANTILE}", target, value, _one, f"{value:.1f} (of {n} outputs)" if value is not None else None)
    old = m.get("old_gate")
    first_of = old["first_try_of"] if old else 0
    ratio(f"Gate at {old['commit'] if old else OLD_GATE}: passes first try (continuity with eval-v1)", "—",
          old["first_try"] if old else 0, first_of, 100,
          lambda v: f"{old['first_try']} of {first_of} (final {old['final']} of {n})", _percent)
    count("Logic slips (probe measures, read by hand)", "—", len(m["logic_slips"]), str(len(m["logic_slips"])))
    return rows


def _pooled(parts: list[tuple[float, Optional[float], float]], fmt: Callable[[float], str]) -> str:
    if any(den is None for _, den, _ in parts):
        return f"{sum(num for num, _, _ in parts):g} in all"
    den = sum(d for _, d, _ in parts if d)
    return fmt(sum(num for num, _, _ in parts) / den * parts[0][2]) if den else "—"


def render_runs(labels: list[str], systems: list[str], summaries: dict[str, dict[str, Any]]) -> str:
    """Several runs of the same arms: each §3 measure per run, its range and the runs pooled, beside the target."""
    lines = [f"# §3 measures across runs: {', '.join(f'`{label}`' for label in labels)}", "",
             "Generated by `python -m evals.trend_depth.report --labels`. Every run is shown, with the range across them and "
             "the runs pooled (a share over all their analyses, a count summed); none is picked. Counts are before hand "
             "reading: each run's items are listed in its own `runs/<label>/REPORT.md` (`report --label`).", "",
             *build_warnings({label: summaries[label] for label in labels}, systems),
             *pending_warnings({label: summaries[label] for label in labels}, systems)]
    for split in ("dev", "holdout", "all"):
        companies = summaries[labels[0]]["splits"][split]["companies"]
        lines += [f"## {split}: {companies} companies", ""]
        for system in systems:
            per_run = {label: (summaries[label]["splits"][split].get("measures") or {}).get(system) for label in labels}
            present = [label for label in labels if per_run[label]]
            if not present:
                continue
            rows = {label: measure_rows(per_run[label]) for label in present}
            lines += [f"### {system}", "", "| Measure | Target for C | " + " | ".join(labels) + " | Range | Pooled |",
                      "|---|---|" + "---|" * (len(labels) + 2)]
            for i, (name, target, _, _, _, fmt) in enumerate(rows[present[0]]):
                cells = [rows[label][i][2] if label in rows else "—" for label in labels]
                values = [rows[label][i][3] for label in present if rows[label][i][3] is not None]
                spread = f"{fmt(min(values))}–{fmt(max(values))}" if len(values) > 1 else "—"
                parts = [rows[label][i][4] for label in present]
                pooled = _pooled([p for p in parts if p], fmt) if len(present) > 1 and all(parts) else "—"
                lines.append(f"| {name} | {target} | " + " | ".join(cells) + f" | {spread} | {pooled} |")
            lines.append("")
        lines += judge_runs([summaries[label]["splits"][split]["judge"] for label in labels], labels)
    return "\n".join(lines)


def judge_runs(matrices: list[dict[str, Any]], labels: list[str]) -> list[str]:
    """One split's judge verdicts per criterion across runs (``matrices``, one per label): each run's and their sum,
    the 20 pairs per split §3's judge target counts."""
    pairs = sorted({pair for matrix in matrices for pair in matrix["criteria"]})
    if not pairs:
        return []
    lines = ["### Judge, per criterion", "",
             f"The panel's verdicts, both orders agreeing, as x wins · y wins · ties or splits; for \"{JOINT}\", the pairs "
             f"in which x, then y, won or tied both, of the pairs judged. DEEPSEEK-ERRORS.md §3's target: {JUDGE_TARGET}.", "",
             "| Pair (x vs y) | Criterion | " + " | ".join(labels) + " | Pooled |", "|---|---|" + "---|" * (len(labels) + 1)]
    for pair in pairs:
        x, y = pair.split("|")
        per_run = [dict(judge_criteria(matrix, pair)) if pair in matrix["criteria"] else None for matrix in matrices]
        for name in (*CRITERIA, JOINT):
            cells = [run[name] for run in per_run if run]
            summed = (sum(c[0] for c in cells), sum(c[1] for c in cells), sum(c[2] for c in cells))
            lines.append(f"| {x} vs {y} | {name} | " + " | ".join(_judge_cell(name, run[name]) if run else "—" for run in per_run)
                         + f" | {_judge_cell(name, summed)} |")
    return lines + [""]


def _judge_cell(name: str, counts: tuple[int, int, int]) -> str:
    a, b, c = counts
    return f"{a} · {b} of {c}" if name == JOINT else f"{a} · {b} · {c}"


def _quote(text: str) -> str:
    return _plain(text).replace("|", "/")


def hand_reading(system: str, m: dict[str, Any]) -> list[str]:
    """Every item one arm's §3 measures count, for reading by hand, and the Opus flags they leave out."""
    lines = [f"### {system}", ""]
    as_run = m.get("first_try_as_run") or []
    if as_run:
        bases = ", ".join(f"{n} {basis}" for basis, n in sorted(Counter(a["basis"] for a in as_run).items()))
        lines += [f"First-try failures as run, the cross-check (the gate of each record's day, as recorded: {bases}; a "
                  f"version-2 record's with its backstops, each a string per kind): "
                  f"{sum(a['failures'] for a in as_run)} in {len(as_run)} analyses"
                  + "".join(f"; {a['ticker']} {a['failures']}" for a in as_run if a["failures"]) + ".", ""]
    groups: list[tuple[str, list[str]]] = [
        ("First-try gate failures (the model's own first output, gate now)",
         [f"{f['ticker']} [{f.get('section', '')}] {f['failure']}: {_quote(f.get('sentence', ''))}" for f in m["first_try_failures"]]),
        ("Repairs sent for broken net cash alone (the gate's broken_debt backstop; an arm reading packs-v2 only)",
         [f"{d['ticker']} [{f.get('section', '')}] {f['failure']}: {_quote(f.get('sentence', ''))}"
          for d in m.get("repairs_for_broken_debt_alone", []) for f in d["failures"]]),
        ("First-try backstop hits (beyond the gate's failures; broken net cash apart)",
         [f"{h['ticker']} [{h.get('section', '')}] {' + '.join(h['kinds'])} '{h['claim']}': {_quote(h['sentence'])} "
          f"({'; '.join(h['detail'])})" for h in m["first_try_backstop_hits"]]),
        ("Sentences the code retyped", [f"{r['ticker']} [{r.get('section', '')}] {r.get('from', '')} -> {r.get('to', '')}: "
                                        f"{_quote(r.get('sentence', ''))}" for r in m["retyped"]]),
        ("Mislabels, each claim (probes R1, R2a, R2c, R3 and Opus substantive flags; a sentence counts once)",
         [f"{h['ticker']} {h['source']} '{h['claim']}': {_quote(h['sentence'])} ({h['detail']})"
          + (f" [{h['also']}]" if h.get("also") else "") for h in m["mislabel_list"]]),
        ("Opus flags not counted (a bound the value satisfies, under view 1; a number several cited values match)",
         [f"{h['ticker']} {h['source']} {h['class']} '{h['claim']}': {_quote(h['sentence'])} ({h['detail']})"
          for h in m["opus_other"]]),
        *[(f"Probe {kind}", [f"{h['ticker']} '{h['claim']}': {_quote(h['sentence'])} ({h['detail']})" for h in m[kind]])
          for kind in OWN_ROW_KINDS],
        ("Logic slips (probe measures)", [f"{h['ticker']} {h['kind']} '{h['claim']}': {_quote(h['sentence'])} ({h['detail']})"
                                          for h in m["logic_slips"]]),
        ("Evaluative words in data sentences", [f"{h['ticker']} [{h['section']}] {', '.join(h['words'])}: {_quote(h['sentence'])}"
                                                for h in m["evaluative_list"]]),
        ("Watch items with forecast wording", [f"{h['ticker']} '{h['wording']}': {_quote(h['sentence'])}" for h in m["watch_forecast_list"]]),
        ("Broken net cash (the breaks packs-v2 records)", [
            f"{d['ticker']} {d['state']} ({', '.join(d['checks']).replace('_', ' ')})" + "".join(
                f"\n  - states ({', '.join(s['breaks'])}) {'; '.join(s['claims'])}: {_quote(s['sentence'])}" for s in d["stated"])
            + "".join(f"\n  - discloses: {_quote(s['sentence'])}" for s in d["disclosed"])
            for d in m["broken_net_cash"]["list"] if d["state"] is not None]),
        ("Version-1 peer ranks and medians on a peer's broken year (peer_break)", [
            f"{d['ticker']} {'; '.join(s['claims'])}: {_quote(s['sentence'])}" for d in m["broken_net_cash"]["list"] for s in d["peer"]]),
    ]
    for title, items in groups:
        if items:
            lines += [f"{title}:", "", *(f"- {item}" for item in items), ""]
    return lines


def summarise(label: str, systems: list[str], old_gate: Optional[tuple[str, ModuleType]],
              prefixes: Optional[dict[str, int]] = None) -> dict[str, Any]:
    summary: dict[str, Any] = {"label": label, "systems": systems, "splits": {}}
    prefixes = recorded_prefixes() if prefixes is None else prefixes
    for split in ("dev", "holdout", "all"):
        tickers = [c.ticker for c in eval_companies(None if split == "all" else split)]
        records = {system: load(label, system, tickers) for system in systems}
        arms = {system: arm_stats(records[system], prefixes) for system in systems}
        summary["splits"][split] = {
            "companies": len(tickers),
            "arms": arms,
            "judge": judge_matrix(label, systems, tickers),
            "causes": {folder: cause_support(label, [*systems, "gold"], tickers, folder)
                       for folder in audit_folders(label, "causes")},
            "semantics": {folder: semantic_support(label, systems, tickers, folder)
                          for folder in audit_folders(label, "semantics")},
            "measures": {system: arm_measures(label, system, records[system], arms[system], old_gate) for system in systems},
        }
    return summary


def old_gate_at(commit: str) -> Optional[tuple[str, ModuleType]]:
    """(commit, the gate as committed there), or None for ``none``."""
    if commit == "none":
        return None
    from evals.trend_depth.replay import base_gate  # reads git; only the report's continuity score needs it

    return commit, base_gate(commit)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--label", help="one run: writes runs/<label>/REPORT.md and summary.json")
    which.add_argument("--labels", help="several runs of the same arms, comma-separated: the §3 measures side by side")
    parser.add_argument("--systems", required=True)
    parser.add_argument("--old-gate", default=OLD_GATE, help="the commit whose gate scores outputs for continuity, or none")
    parser.add_argument("--out", default="", help="write REPORT.md and summary.json here instead of under runs/")
    args = parser.parse_args()
    systems = args.systems.split(",")
    old_gate = old_gate_at(args.old_gate)
    prefixes = recorded_prefixes()
    if args.label:
        summary = summarise(args.label, systems, old_gate, prefixes)
        out = RUNS / args.label
        text = render(args.label, systems, summary)
    else:
        labels = args.labels.split(",")
        summary = {"labels": labels, "systems": systems,
                   "runs": {label: summarise(label, systems, old_gate, prefixes) for label in labels}}
        out = RUNS / "+".join(labels)
        text = render_runs(labels, systems, summary["runs"])
    out = Path(args.out) if args.out else out
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    (out / "REPORT.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
