"""Aggregate a bake-off run: fact-check gate, sentence mix, cost and latency, pairwise judge matrix.

    cd backend && python -m evals.trend_depth.report --label eval-v1 --systems current,deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5

Writes ``runs/<label>/REPORT.md`` and ``runs/<label>/summary.json``. Development and held-out companies are
reported side by side; the held-out half is the result, the development half is where the prompt was tuned.

Cost is the list-price cost of the measured tokens (``providers.list_cost``: uncached input, cached input
and output at each provider's published rate), so a Claude arm run through the CLI is costed as the API
would bill the same tokens; the CLI's own billed figure is reported beside it. Extrapolation multiplies
the mean cost of a fresh generation, including any repair call, by the monthly run count.
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
from evals.trend_depth.providers import ARMS, list_cost
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


def _api_cost(record: dict[str, Any]) -> Optional[float]:
    arm = ARMS.get(record.get("arm", ""))
    if arm is None:
        return record.get("cost_usd")
    total = 0.0
    for attempt in record.get("attempts", []):
        total += list_cost(arm, attempt["input_tokens"], attempt["cached_input_tokens"], attempt["output_tokens"])
    return total


def load(label: str, system: str, tickers: list[str]) -> list[dict[str, Any]]:
    out = []
    for ticker in tickers:
        path = RUNS / label / system / f"{ticker}.json"
        if path.exists():
            out.append(json.loads(path.read_text()))
    return out


def arm_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    ok = [r for r in records if r.get("generation_ok")]
    stats: dict[str, Any] = {"n": n, "generated": len(ok)}
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
    now_final = [factcheck.check(sentences_of(r["output"]), load_pack(r["ticker"]))["passed"] for r in ok]
    now_first = [factcheck.check(sentences_of(r.get("first_pass_output", r["output"])), load_pack(r["ticker"]))["passed"] for r in ok]
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
    costs = [c for c in (_api_cost(r) for r in ok) if c is not None]
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
        "cost_billed_mean": statistics.mean(r.get("cost_usd") or 0 for r in ok),
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


def cause_support(label: str, systems: list[str], tickers: list[str], folder: str = "causes") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for system in systems:
        counts: Counter[str] = Counter()
        auditors: Counter[str] = Counter()
        for ticker in tickers:
            path = RUNS / label / folder / system / f"{ticker}.json"
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            auditors[record.get("auditor") or "none"] += 1
            counts.update(item["label"] for item in record.get("items", []))
        if counts:
            out[system] = {"counts": dict(counts), "auditors": dict(auditors)}
    return out


def semantic_support(label: str, systems: list[str], tickers: list[str], folder: str = "semantics") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for system in systems:
        counts: Counter[str] = Counter()
        auditors: Counter[str] = Counter()
        flagged: list[dict[str, str]] = []
        for ticker in tickers:
            path = RUNS / label / folder / system / f"{ticker}.json"
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            auditors[record.get("auditor") or "none"] += 1
            output = json.loads((RUNS / label / system / f"{ticker}.json").read_text())["output"]
            for item in record.get("items", []):
                counts[item["label"]] += 1
                if item["label"] == "mismatch":
                    kind = classify_flag(item, sentences_of(output), load_pack(ticker))
                    counts[f"mismatch_{kind}"] += 1
                    flagged.append({"ticker": ticker, "kind": kind, "claim": item["claim"], "sentence": item["sentence"],
                                    "reason": item["reason"]})
        if counts:
            out[system] = {"counts": dict(counts), "auditors": dict(auditors), "analyses": sum(auditors.values()), "flagged": flagged}
    return out


def _panel_verdict(results: list[dict[str, Any]], criterion: str) -> str:
    finals = {r["result"][criterion]["final"] for r in results}
    return finals.pop() if len(finals) == 1 else "tie"


def judge_matrix(label: str, systems: list[str], tickers: list[str]) -> dict[str, Any]:
    """One verdict per (company, pair). Each judge's own verdict needs both orders to agree. Where judges
    from neither output's family exist, the verdict is theirs (all of them agreeing); otherwise it is the
    consensus panel's (one judge from each family, both agreeing), counted only when the panel is complete.
    ``consensus`` keeps the consensus panel's verdicts separately wherever one ran, for comparison."""
    panels: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for path in (RUNS / label / "judge").glob("*/*.json"):
        record = json.loads(path.read_text())
        if record["ticker"] in tickers and record["x"] in systems and record["y"] in systems:
            panels[(record["ticker"], record["x"], record["y"])].append(record)
    wins: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    consensus: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    criteria: dict[tuple[str, str], dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    by_judge: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    agreement: dict[str, list[bool]] = defaultdict(list)
    between_judges: list[bool] = []
    panel_kinds: Counter[str] = Counter()
    judged_by: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    judged = incomplete = 0
    for (_, x, y), records in panels.items():
        key = (x, y)
        forfeit = next((r for r in records if "forfeit" in r), None)
        if forfeit:
            wins[key][y if forfeit["forfeit"] == x else x if forfeit["forfeit"] == y else "tie"] += 1
            continue
        results = [r for r in records if r.get("result")]
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
                  "| System | Generated | Gate pass, first try (as run · current gate) | Gate pass after one repair (as run · current gate) | Failed claims, first try | Claims per analysis | Causal sentences | Passages cited | Words | API list cost per run | Latency p50 / p90 (s) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for system in systems:
            s = block["arms"].get(system, {})
            if not s:
                continue
            if system == "current":
                lines.append(f"| current (production) | {s.get('generated')}/{s['n']} | by construction | — | — | — | 0 | 0 | "
                             f"{s.get('words_mean', 0):.0f} | ${s.get('cost_mean') or 0:.5f} | {s.get('latency_p50', 0):.1f} / {s.get('latency_p90', 0):.1f} |")
                continue
            lines.append(
                f"| {system} | {s.get('generated')}/{s['n']} | {s.get('first_pass_gate', 0)} · {s.get('first_pass_gate_now', 0)} of {s.get('generated', 0)} | "
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
