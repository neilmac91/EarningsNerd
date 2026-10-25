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
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from typing import Any, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, load_pack, sentences_of
from evals.trend_depth.judge import CRITERIA, _family
from evals.trend_depth.providers import ARMS
from evals.trend_depth.records import api_cost, first_request_cache, output_sha256, read_same_output, text_sha256, unsettled
from evals.trend_depth.semantics import classify_flag

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
                           "left_out": dict(left_out), "flagged": flagged}
    return out


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
                      "substantive ones (`semantics.classify_flag`):", "",
                      "| System | Analyses | Claims consistent | Flagged | of which substantive | bound | ambiguous | Not labelled | Auditor |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for system, data in semantics.items():
                c = data["counts"]
                lines.append(f"| {system} | {data['analyses']} | {c.get('consistent', 0)} | {c.get('mismatch', 0)} | "
                             f"{c.get('mismatch_substantive', 0)} | {c.get('mismatch_bound', 0)} | {c.get('mismatch_ambiguous', 0)} | "
                             f"{c.get('missing', 0)} | {', '.join(data['auditors'])} |")
            lines.append("")
            lines += _left_out_lines(semantics)
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
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--systems", required=True)
    args = parser.parse_args()
    systems = args.systems.split(",")
    summary: dict[str, Any] = {"label": args.label, "systems": systems, "splits": {}}
    for split in ("dev", "holdout", "all"):
        tickers = [c.ticker for c in eval_companies(None if split == "all" else split)]
        summary["splits"][split] = {
            "companies": len(tickers),
            "arms": {system: arm_stats(load(args.label, system, tickers)) for system in systems},
            "judge": judge_matrix(args.label, systems, tickers),
            "causes": {folder: cause_support(args.label, [*systems, "gold"], tickers, folder)
                       for folder in audit_folders(args.label, "causes")},
            "semantics": {folder: semantic_support(args.label, systems, tickers, folder)
                          for folder in audit_folders(args.label, "semantics")},
        }
    out = RUNS / args.label
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    (out / "REPORT.md").write_text(render(args.label, systems, summary))
    print((out / "REPORT.md").read_text())


if __name__ == "__main__":
    main()
