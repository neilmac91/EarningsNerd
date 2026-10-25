"""Aggregate a bake-off run: fact-check gate, sentence mix, cost and latency, pairwise judge matrix.

    cd backend && python -m evals.trend_depth.report --label eval-v1 --systems current,deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5

Writes ``runs/<label>/REPORT.md`` and ``runs/<label>/summary.json``. Development and held-out companies are
reported side by side; the held-out half is the result, the development half is where the prompt was tuned.

Cost is the list-price cost of the measured tokens (``providers.list_cost``: uncached input, cached input,
cache writes and output at each provider's published rate), including every attempt of every generation,
failed ones too, priced as a company's first analysis would bill (``records.api_cost``). A first request
reads from cache only the prefix every company shares, the system prompt. A repair re-sends its first pass's
prefix seconds later and keeps the hits DeepSeek recorded. The harness's Claude API request sets no cache
breakpoint, so a Claude call reads nothing from cache. The cost each provider recorded is in ``summary.json``
as ``cost_recorded_mean``. Extrapolation multiplies the mean cost of a fresh generation, including any repair
call, by the monthly run count.

A record still waiting on a provider error (``records.unsettled``) is counted apart, as is an audit or verdict
that failed, was refused, or read an output that has since changed: none of them is reported as a result.

Every arm is also scored on the measures of DEEPSEEK-ERRORS.md §3 (``arm_measures``, in ``summary.json`` under each
split's ``measures``), beside §3's target for the candidate, and every item they count is listed for hand reading.
A record made with ``generate --pipeline v2`` (``pipeline: "v2"``) adds the repair area's fields: the gate on the
model's own first output (``raw_first_pass_gate``), the IDs the code added (``autocite``), the sentences it retyped
(``retyped``) and the repair's kind (``repair_kind``). A record without them is version 1 (eval-v1 and earlier),
whose first output is its first pass, checked under the gate as it is now. The mislabels and the cause support read
the Opus audits (``OPUS``); the broken net cash reads the debt-break checks of ``packs-v2/`` whatever pack the arm
read, since version 1 has none. Several runs of the same arms:

    cd backend && python -m evals.trend_depth.report --labels dev-v5-r1,dev-v5-r2 --systems deepseek-flash,deepseek-flash-c

prints each measure per run, its range and the runs pooled, beside the targets, and writes them to
``runs/<label>+<label>/``; it never picks the better run.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import statistics
from collections import Counter, defaultdict
from types import ModuleType
from typing import Any, Callable, Optional

from evals.trend_depth import calibration, factcheck, probes
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, SECTION_KEYS, load_pack, sentences_of
from evals.trend_depth.judge import CRITERIA, _family
from evals.trend_depth.providers import ARMS, parse_json_object
from evals.trend_depth.records import api_cost, first_request_cache, output_sha256, read_same_output, text_sha256, unsettled
from evals.trend_depth.semantics import classify_flag

OPUS = "claude-opus-5-5"  # the auditor §3 counts mislabels and cause support with
OLD_GATE = "b3ed8ef"  # the gate before wave 1 narrowed it (DEEPSEEK-ERRORS.md was measured on it): continuity, as in replay.py
REFERENCE_PACKS = "packs-v2"  # its debt-break checks and withheld IDs say which figures rest on a broken debt line
DEBT_SERIES = ("total_debt", "net_cash", "net_cash_to_revenue")
MISLABEL_KINDS = probes.GATE_KINDS  # a verified number said about another ratio, basis, year or sign
_DEBT_WORDS = re.compile(r"\b(?:debt|net cash|borrowings?)\b", re.I)
_DISCLOSURE = re.compile(
    r"\b(?:unreliable|incomplete|overstat\w*|understat\w*|not reported|reported only|only through|no (?:long-term )?debt line|"
    r"missing|omit\w*|drops? out|data (?:gap|break|quality)|debt break|artefact|artifact|last year the pack reports|"
    r"cannot be (?:assessed|compared)|needs? restating|rests? on (?:the |an )?incomplete|(?:that|this|the) break)\b", re.I)

FAILURE_CLASSES = (
    ("unknown citation", "unknown_citation"), ("no citation", "uncited_number"), ("other way", "direction"),
    ("not in the period", "period"), ("matches nothing", "no_match"), ("cites no filing passage", "cause_without_passage"),
    ("generation failed", "generation_failed"),
)


def _class(failure: str) -> str:
    return next((name for needle, name in FAILURE_CLASSES if needle in failure), "other")


def _pct(n: float, d: float) -> str:
    return f"{n / d * 100:.0f}%" if d else "—"


def _quantile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def load(label: str, system: str, tickers: list[str]) -> list[dict[str, Any]]:
    out = []
    for ticker in tickers:
        path = RUNS / label / system / f"{ticker}.json"
        if path.exists():
            out.append(json.loads(path.read_text()))
    return out


def arm_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    pending = [r for r in records if "repair_error" in r]  # a first pass whose repair generate still owes
    errored = [r for r in records if "error" in r]  # a provider failure generate retries, not the model's own
    ok = [r for r in records if r.get("generation_ok") and not unsettled(r)]
    stats: dict[str, Any] = {"n": n, "generated": len(ok), "pending_repairs": len(pending), "provider_errors": len(errored)}
    if not ok:
        return stats
    if ok[0]["arm"] == "current":
        stats.update({
            "words_mean": statistics.mean(r["words"] for r in ok),
            "cost_mean": statistics.mean(r.get("cost_usd") or 0 for r in ok),
            "latency_p50": _quantile([r["latency_s"] for r in ok], 0.5),
            "latency_p90": _quantile([r["latency_s"] for r in ok], 0.9),
        })
        return stats
    gates = [r["gate"] for r in ok]
    first = [r.get("first_pass_gate", r["gate"]) for r in ok]
    # The same outputs under the gate as it is now: fixes made after the run (each a false positive, listed in
    # REPORT.md) change these counts but not the outputs, which were generated under the gate as it was then.
    now_final = [factcheck.check(sentences_of(r["output"]), load_pack(r["ticker"], r["arm"]))["passed"] for r in ok]
    now_first = [factcheck.check(sentences_of(r.get("first_pass_output", r["output"])), load_pack(r["ticker"], r["arm"]))["passed"]
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
    shared = first_request_cache(paid)
    costs = [c for c in (api_cost(r, shared) for r in paid) if c is not None]
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
        "cost_mean": statistics.mean(costs) if costs else None,
        "cost_recorded_mean": statistics.mean((r.get("cost_usd") or 0) + (r.get("prior_cost_usd") or 0) for r in paid) if paid else None,
        "first_request_cache_tokens": shared,
        "failed_generations": n - len(ok) - len(pending) - len(errored),  # the model's own failures
        # The calls of every failed generation, the model's or the provider's, and of those a record replaced.
        "failed_generation_cost": round(sum((api_cost(r, shared) or 0) if not r.get("generation_ok")
                                            else (api_cost({"arm": r["arm"], "attempts": r.get("prior_attempts", [])}, shared) or 0)
                                            for r in paid), 6),
        "backends": sorted({a.get("backend", "?") for r in paid for a in r.get("attempts", [])}),
        "input_tokens_mean": statistics.mean(r["usage"]["input_tokens"] for r in ok),
        "output_tokens_mean": statistics.mean(r["usage"]["output_tokens"] for r in ok),
        "latency_p50": _quantile([r["latency_s"] for r in ok], 0.5),
        "latency_p90": _quantile([r["latency_s"] for r in ok], 0.9),
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
                    kind = classify_flag(item, sentences_of(output), load_pack(ticker, system))
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


def first_output(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The model's first output, before any code fix or repair. A version-1 record's is its first pass (its output
    when no repair ran). A version-2 record's first pass carries the code's fixes, so its first valid reply is read
    from its attempts instead; None if none parses."""
    if record.get("pipeline") != "v2":
        first = record.get("first_pass_output")
        return first if isinstance(first, dict) else record["output"]
    replies = [a for a in record.get("attempts", []) if a.get("attempt") != "repair" and not a.get("problems")]
    parsed = parse_json_object(replies[-1].get("raw") or "") if replies else None
    return parsed if isinstance(parsed, dict) and isinstance(parsed.get("sections"), list) else None


def _cited(text: str) -> set[str]:
    return {i for group in factcheck.CITATION_RE.findall(text) for i in factcheck.ID_RE.findall(group)}


def _plain(text: str) -> str:
    return " ".join(factcheck.CITATION_RE.sub("", text).split())


def broken_ids(pack: dict[str, Any]) -> set[str]:
    """IDs built on a broken debt year: those the pack withholds, and any total debt or net cash value (or a value of
    their series: growth, share of revenue, peer rank) in a year a ``debt_break`` check names, for a pack that
    withholds none (a bank's)."""
    years = {p.strip() for c in pack.get("data_checks", []) if c.get("kind") == "debt_break" for p in str(c.get("period", "")).split(",")}
    on_break = {vid for vid, series in probes.series_by_id(pack).items()
                if series.split(":")[-1] in DEBT_SERIES and pack["values"].get(vid, {}).get("period") in years}
    return set(pack.get("withheld") or {}) | on_break


def broken_net_cash(sentences: list[dict[str, Any]], pack: dict[str, Any]) -> Optional[dict[str, Any]]:
    """In a pack with a debt break (None otherwise): the sentences that cite a figure built on the break without saying
    so, those that disclose it (a debt or net-cash sentence, or one citing such a figure, that calls it unreliable,
    incomplete, not reported, ...), and the analysis's state: ``disclosed`` if any sentence discloses the break,
    else ``stated as fact`` if any cites a broken figure, else ``silent``."""
    if not any(c.get("kind") == "debt_break" for c in pack.get("data_checks", [])):
        return None
    broken = broken_ids(pack)
    stated, disclosed = [], []
    for sentence in sentences:
        hit = _cited(sentence["text"]) & broken
        plain = _plain(sentence["text"])
        if _DISCLOSURE.search(plain) and (hit or _DEBT_WORDS.search(plain)):
            disclosed.append({"section": sentence.get("section", ""), "sentence": sentence["text"]})
        elif hit:
            stated.append({"section": sentence.get("section", ""), "sentence": sentence["text"], "ids": sorted(hit)})
    state = "disclosed" if disclosed else "stated as fact" if stated else "silent"
    return {"state": state, "stated": stated, "disclosed": disclosed}


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
    """``auditor``'s finished audit of this output: from its same-auditor folder, else from the default folder when
    that auditor made it (deepseek-flash's default auditor is Opus), so one audit is never counted twice."""
    for folder in (f"{kind}-by-{auditor}", kind):
        path = RUNS / label / folder / system / f"{ticker}.json"
        if path.exists():
            record = json.loads(path.read_text())
            if record.get("auditor") == auditor and _audit_state(label, record, system, ticker) == "ok":
                return record
    return None


def arm_measures(label: str, system: str, records: list[dict[str, Any]], stats: dict[str, Any],
                 old_gate: Optional[tuple[str, ModuleType]] = None) -> dict[str, Any]:
    """DEEPSEEK-ERRORS.md §3's measures for one arm's settled analyses, with every counted item for hand reading.
    ``stats`` is the arm's ``arm_stats`` (cost and latency); ``old_gate``, (commit, the gate as committed there:
    ``replay.base_gate``), scores the first and final outputs for continuity with eval-v1."""
    ok = [r for r in records if r.get("generation_ok") and not unsettled(r)]
    if not ok or system == "current":
        return {}
    v2 = [r for r in ok if r.get("pipeline") == "v2"]
    packs: dict[str, dict[str, Any]] = {}
    first_failures: list[dict[str, Any]] = []
    first_basis: Counter[str] = Counter()
    probe_hits: list[dict[str, Any]] = []
    opus_flags: list[dict[str, Any]] = []
    opus_views: Counter[str] = Counter()
    causes: Counter[str] = Counter()
    causes_read = verified = 0
    judgement: Counter[str] = Counter()
    evaluative: list[dict[str, Any]] = []
    evaluative_scope = 0
    forecasts: list[dict[str, Any]] = []
    watch_items = 0
    forms: list[dict[str, Any]] = []
    debt: list[dict[str, Any]] = []
    old: Counter[str] = Counter()
    for r in ok:
        ticker = r["ticker"]
        pack = packs.setdefault(ticker, load_pack(ticker, system))
        final = sentences_of(r["output"])
        if r.get("pipeline") == "v2" and isinstance(r.get("raw_first_pass_gate"), dict):
            failures, basis = r["raw_first_pass_gate"].get("failures", []), "raw_first_pass_gate"
        else:  # version 1, or a version-2 record without its raw gate: the model's first output under the gate now
            first = first_output(r)
            failures, basis = (factcheck.check(sentences_of(first), pack)["failures"], "gate now") if first else ([], "unavailable")
        first_basis[basis] += 1
        first_failures += [{"ticker": ticker, **f} for f in failures]
        keys = probes.series_by_id(pack)
        for sentence in final:
            result, resolved = factcheck.analyse_sentence(sentence, pack)
            verified += sum(1 for c in result.claims if c["status"] == "verified")
            probe_hits += [{"ticker": ticker, **hit} for hit in probes.probe_sentence(sentence, pack, resolved, keys)]
        audit = _audit_by(label, "semantics", system, ticker, OPUS)
        if audit is not None:
            opus_views[str(audit.get("view", 1))] += 1
            opus_flags += [{"ticker": ticker, "source": f"{OPUS} (view {audit.get('view', 1)})", "sentence": item["sentence"],
                            "claim": item["claim"], "detail": item.get("reason", "")}
                           for item in audit.get("items", []) if item["label"] == "mismatch"
                           and classify_flag(item, final, pack) == "substantive"]
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
        state = broken_net_cash(final, reference) if reference else None
        if state is not None:
            debt.append({"ticker": ticker, **state})
        if old_gate is not None:
            first = first_output(r)
            old["first"] += bool(first and old_gate[1].check(sentences_of(first), pack)["passed"])
            old["final"] += bool(old_gate[1].check(final, pack)["passed"])
    mislabels: dict[tuple[str, str, str], dict[str, Any]] = {}
    for hit in [{"source": f"probe {h['kind']}", **h} for h in probe_hits if h["kind"] in MISLABEL_KINDS] + opus_flags:
        key = (hit["ticker"], _plain(hit["sentence"]), hit["claim"])
        if key in mislabels:  # a probe and the auditor on the same claim: one mislabel, both sources named
            mislabels[key]["source"] += f" + {hit['source']}"
        else:
            mislabels[key] = {k: hit[k] for k in ("ticker", "source", "sentence", "claim", "detail")}
    autocite = [r.get("autocite") or {} for r in v2]
    return {
        "analyses": len(ok), "pipeline_v2": len(v2),
        "passes_without_repair": sum(1 for r in ok if not repaired(r) and r["gate"].get("passed")),
        "repairs": dict(Counter(r.get("repair_kind") or ("version 1" if r.get("pipeline") != "v2" else "unknown")
                                for r in ok if repaired(r))),
        "code_fixed_passes": sum(1 for r in v2 if not repaired(r) and r["gate"].get("passed")
                                 and not (r.get("raw_first_pass_gate") or {}).get("passed", True)),
        "first_try_errors": len(first_failures), "first_try_basis": dict(first_basis), "first_try_failures": first_failures,
        "own_id_omissions": sum(len(a.get("added", [])) for a in autocite),
        "autocite_rejected": sum(int(a.get("rejected") or 0) for a in autocite),
        "autocite_added": [{"ticker": r["ticker"], **added} for r in v2 for added in (r.get("autocite") or {}).get("added", [])],
        "retyped": [{"ticker": r["ticker"], **change} for r in v2 for change in r.get("retyped") or []],
        "verified_claims": verified, "probe_mislabels": sum(1 for h in probe_hits if h["kind"] in MISLABEL_KINDS),
        "opus_substantive": len(opus_flags), "opus_audited": sum(opus_views.values()), "opus_views": dict(opus_views),
        "mislabels": len(mislabels), "mislabel_list": list(mislabels.values()),
        "unsigned_falls": [h for h in probe_hits if h["kind"] == "U1"],
        "logic_slips": [h for h in probe_hits if h["kind"] in probes.MEASURE_KINDS],
        "judgement_outside_watch": [judgement["judgements"], judgement["sentences"]],
        "evaluative": [len(evaluative), evaluative_scope], "evaluative_list": evaluative,
        "watch_forecasts": [len(forecasts), watch_items], "watch_forecast_list": forecasts,
        "broken_net_cash": {"analyses": len(debt), "stated_as_fact": sum(1 for d in debt if d["state"] == "stated as fact"),
                            "disclosed": sum(1 for d in debt if d["state"] == "disclosed"), "list": debt},
        "cause_support": {"audited": causes_read, **{k: causes.get(k, 0) for k in ("supported", "partial", "unsupported")}},
        "causes_per_analysis": sum(1 for r in ok for s in sentences_of(r["output"]) if s["type"] == "cause") / len(ok),
        "form": {"words_mean": statistics.mean(f["words"] for f in forms), "words_max": max(f["words"] for f in forms),
                 "sentences_mean": statistics.mean(f["sentences"] for f in forms), "sentences_max": max(f["sentences"] for f in forms),
                 "all_sections": sum(1 for f in forms if not f["missing"]),
                 "within_target": sum(1 for f in forms if f["words"] <= 700 and f["sentences"] <= 30 and not f["missing"])},
        "cost_mean": stats.get("cost_mean"), "latency_p50": stats.get("latency_p50"), "latency_p90": stats.get("latency_p90"),
        "old_gate": {"commit": old_gate[0], "first_try": old["first"], "final": old["final"]} if old_gate is not None else None,
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
        for criterion in CRITERIA:
            criteria[key][criterion][_panel_verdict(panel, criterion)] += 1
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
        "by_judge": {pair: {judge: dict(c) for judge, c in judges.items()} for pair, judges in by_judge.items()},
        "swap_agreement": {judge: (sum(v) / len(v) if v else None, len(v)) for judge, v in agreement.items()},
        "between_judges": (sum(between_judges) / len(between_judges) if between_judges else None, len(between_judges)),
    }


def render(label: str, systems: list[str], summary: dict[str, Any]) -> str:
    lines = [f"# Bake-off report: `{label}`", "", "Generated by `python -m evals.trend_depth.report`.", ""]
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
                      "bound the value satisfies, or on a number several cited values match, is counted apart from the "
                      "substantive ones (`semantics.classify_flag`). View is the auditor's view of the matches "
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
            lines.append("")
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
    (numerator, denominator or None for a count, scale) to pool runs, or None, and the value's format)."""
    rows: list[Row] = []

    def ratio(name: str, target: str, num: float, den: float, scale: float, shown: Callable[[float], str],
              fmt: Callable[[float], str]) -> None:
        value = num / den * scale if den else None
        rows.append((name, target, shown(value) if value is not None else "—", value, (num, den, scale) if den else None, fmt))

    def count(name: str, target: str, num: float, shown: str) -> None:
        rows.append((name, target, shown, float(num), (num, None, 1.0), _count))

    def level(name: str, target: str, value: Optional[float], fmt: Callable[[float], str], shown: Optional[str] = None) -> None:
        rows.append((name, target, (shown or fmt(value)) if value is not None else "—", value, None, fmt))

    n, n2 = m["analyses"], m["pipeline_v2"]
    k = m["passes_without_repair"]
    ratio("Passes without a model repair", "at least 85% pooled; no run below 80%", k, n, 100,
          lambda v: f"{k} of {n} ({v:.0f}%)", _percent)
    ratio("of which passed after the code's fixes (version 2 records)", "—", m["code_fixed_passes"], n2, 100,
          lambda v: f"{m['code_fixed_passes']} of {n2}", _percent)
    e = m["first_try_errors"]
    ratio("Real first-try gate errors per analysis (subtract gate artefacts by hand)", "0.15 or less", e, n, 1,
          lambda v: f"{v:.2f} ({e} in {n})", _two)
    a = m["own_id_omissions"]
    ratio("Own-ID omissions per analysis (IDs the code added)", "— (counted before auto-citation)", a, n2, 1,
          lambda v: f"{v:.2f} ({a} in {n2}; {m['autocite_rejected']} rejected)", _two)
    hits, claims = m["mislabels"], m["verified_claims"]
    ratio("Mislabels per 1,000 verified claims: probes plus Opus substantive flags", "3.5 or less in each run, after hand reading",
          hits, claims, 1000, lambda v: f"{v:.1f} ({hits} in {claims:,}: probes {m['probe_mislabels']}, Opus {m['opus_substantive']}; "
                                        f"Opus read {m['opus_audited']} of {n})", _one)
    j, d = m["judgement_outside_watch"]
    ratio("Judgement share outside the watch list", "3–12%", j, d, 100, lambda v: f"{v:.1f}% ({j} of {d})", _percent1)
    w, d = m["evaluative"]
    ratio("Evaluative words in fact and comparison sentences, outside arc and watch", "3% or less", w, d, 100,
          lambda v: f"{v:.1f}% ({w} of {d})", _percent1)
    f, d = m["watch_forecasts"]
    ratio("Watch items with forecast wording, per 60 (read by hand)", "2 or fewer per 60", f, d, 60,
          lambda v: f"{v:.1f} ({f} of {d})", _one)
    count("Unsigned falls (probe U1)", "0 (guard)", len(m["unsigned_falls"]), str(len(m["unsigned_falls"])))
    debt = m["broken_net_cash"]
    count("Broken net cash stated as fact (debt-break analyses)", "0 stated as fact", debt["stated_as_fact"],
          f"{debt['stated_as_fact']} of {debt['analyses']} ({debt['disclosed']} disclosed)" if debt["analyses"] else "— (none)")
    c = m["cause_support"]
    total = c["supported"] + c["partial"] + c["unsupported"]
    ratio("Cause support, Opus: supported / partial / unsupported", "at least 72% supported, at most 2% unsupported (guard)",
          c["supported"], total, 100, lambda v: f"{v:.0f}% / {c['partial'] / total * 100:.0f}% / {c['unsupported'] / total * 100:.0f}% "
                                                f"of {total} (Opus read {c['audited']} of {n})", _percent)
    ratio("Cause sentences per analysis", "at least 6 (guard)", m["causes_per_analysis"] * n, n, 1, lambda v: f"{v:.1f}", _one)
    form = m["form"]
    level("Words per analysis, mean (max)", "700 or fewer", form["words_max"], _count, f"{form['words_mean']:.0f} ({form['words_max']})")
    level("Sentences per analysis, mean (max)", "30 or fewer", form["sentences_max"], _count,
          f"{form['sentences_mean']:.1f} ({form['sentences_max']})")
    ratio("Analyses with all 7 sections", "all", form["all_sections"], n, 100, lambda v: f"{form['all_sections']} of {n}", _percent)
    level("API list cost per analysis", "at most $0.0075 off-peak", m["cost_mean"], _dollars)
    level("Latency p50 (s)", "at most 10.5", m["latency_p50"], _one)
    level("Latency p90 (s)", "at most 13", m["latency_p90"], _one)
    old = m.get("old_gate")
    ratio(f"Gate at {old['commit'] if old else OLD_GATE}: passes first try (continuity with eval-v1)", "—",
          old["first_try"] if old else 0, n if old else 0, 100, lambda v: f"{old['first_try']} of {n} (final {old['final']})", _percent)
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
             "reading: each run's items are listed in its own `runs/<label>/REPORT.md` (`report --label`).", ""]
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
    return "\n".join(lines)


def _quote(text: str) -> str:
    return _plain(text).replace("|", "/")


def hand_reading(system: str, m: dict[str, Any]) -> list[str]:
    """Every item one arm's §3 measures count, for reading by hand."""
    lines = [f"### {system}", ""]
    groups: list[tuple[str, list[str]]] = [
        ("First-try gate failures" + (f" ({', '.join(f'{n} {basis}' for basis, n in sorted(m['first_try_basis'].items()))})"),
         [f"{f['ticker']} [{f.get('section', '')}] {f['failure']}: {_quote(f.get('sentence', ''))}" for f in m["first_try_failures"]]),
        ("IDs the code added (own-ID omissions)", [f"{a['ticker']} [{a.get('section', '')}] {a.get('claim', '')} -> {a.get('id', '')}: "
                                                    f"{_quote(a.get('sentence', ''))}" for a in m["autocite_added"]]),
        ("Sentences the code retyped", [f"{r['ticker']} [{r.get('section', '')}] {r.get('from', '')} -> {r.get('to', '')}: "
                                        f"{_quote(r.get('sentence', ''))}" for r in m["retyped"]]),
        ("Mislabels (probes and Opus substantive flags)", [f"{h['ticker']} {h['source']} '{h['claim']}': {_quote(h['sentence'])} ({h['detail']})"
                                                         for h in m["mislabel_list"]]),
        ("Logic slips (probe measures)", [f"{h['ticker']} {h['kind']} '{h['claim']}': {_quote(h['sentence'])} ({h['detail']})"
                                          for h in m["logic_slips"]]),
        ("Evaluative words in data sentences", [f"{h['ticker']} [{h['section']}] {', '.join(h['words'])}: {_quote(h['sentence'])}"
                                                for h in m["evaluative_list"]]),
        ("Watch items with forecast wording", [f"{h['ticker']} '{h['wording']}': {_quote(h['sentence'])}" for h in m["watch_forecast_list"]]),
        ("Broken net cash (debt-break packs)", [f"{d['ticker']} {d['state']}" + "".join(
            f"\n  - {'discloses' if kind == 'disclosed' else 'states ' + ', '.join(s['ids'])}: {_quote(s['sentence'])}"
            for kind in ("stated", "disclosed") for s in d[kind]) for d in m["broken_net_cash"]["list"]]),
    ]
    for title, items in groups:
        if items:
            lines += [f"{title}:", "", *(f"- {item}" for item in items), ""]
    return lines


def summarise(label: str, systems: list[str], old_gate: Optional[tuple[str, ModuleType]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"label": label, "systems": systems, "splits": {}}
    for split in ("dev", "holdout", "all"):
        tickers = [c.ticker for c in eval_companies(None if split == "all" else split)]
        records = {system: load(label, system, tickers) for system in systems}
        arms = {system: arm_stats(records[system]) for system in systems}
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
    args = parser.parse_args()
    systems = args.systems.split(",")
    old_gate = old_gate_at(args.old_gate)
    if args.label:
        summary = summarise(args.label, systems, old_gate)
        out = RUNS / args.label
        text = render(args.label, systems, summary)
    else:
        labels = args.labels.split(",")
        summary = {"labels": labels, "systems": systems, "runs": {label: summarise(label, systems, old_gate) for label in labels}}
        out = RUNS / "+".join(labels)
        text = render_runs(labels, systems, summary["runs"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    (out / "REPORT.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
