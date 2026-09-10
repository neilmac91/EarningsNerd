"""Pair two eval reports filing-by-filing and print the deltas (model bake-off aid).

The regression gate compares a report's AGGREGATE stats against the pinned baseline; it cannot say
which filings moved. This script pairs attempts across two reports by (candidate, ticker,
filing_type, run) and prints per-filing deltas for the gate dimensions, output tokens and latency,
plus per-candidate totals. Read-only; stdlib only.

    cd backend
    python -m evals.compare_reports evals/baselines/eval_20260905T111951Z.json evals/reports/eval_<stamp>.json
    python -m evals.compare_reports A.json B.json --json deltas.json   # machine-readable copy

Rows with an error on either side are listed separately, never averaged. Usage fields are absent
on reports produced before the runner recorded provider usage; those cells print as ``n/a``.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DIMENSIONS = (
    "aggregate", "numeric_precision", "numeric_accuracy", "coverage", "currency_consistency",
    "financial_depth", "specificity", "redundancy", "delta_consistency",
    "forward_quote_fidelity", "citation_fidelity",
)

Key = Tuple[str, str, str, int]


def _key(row: Dict[str, Any]) -> Key:
    return (str(row.get("candidate")), str(row.get("ticker")), str(row.get("filing_type")), int(row.get("run") or 0))


def _metric(row: Dict[str, Any], name: str) -> Optional[float]:
    if name == "aggregate":
        value = row.get("aggregate")
    else:
        value = (row.get("score") or {}).get(name)
    return float(value) if isinstance(value, (int, float)) else None


def _tokens(row: Dict[str, Any], name: str) -> Optional[int]:
    usage = row.get("provider_usage")
    if isinstance(usage, dict) and isinstance(usage.get(name), int):
        return usage[name]
    legacy = row.get("output_tokens" if name == "completion_tokens" else "input_tokens")
    return legacy if isinstance(legacy, int) else None


def _load(path: Path) -> Dict[str, Any]:
    report = json.loads(path.read_text())
    if "results" not in report:
        raise SystemExit(f"{path}: not an eval report (no 'results')")
    return report


def pair_reports(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Return paired rows, unpaired keys and per-candidate deltas for two reports."""
    rows_a = {_key(r): r for r in a["results"]}
    rows_b = {_key(r): r for r in b["results"]}
    paired: List[Dict[str, Any]] = []
    errored: List[Dict[str, Any]] = []
    for key in sorted(set(rows_a) & set(rows_b)):
        ra, rb = rows_a[key], rows_b[key]
        entry: Dict[str, Any] = {"candidate": key[0], "ticker": key[1], "filing_type": key[2], "run": key[3]}
        if ra.get("error") or rb.get("error"):
            entry.update(error_a=ra.get("error"), error_b=rb.get("error"))
            errored.append(entry)
            continue
        for dim in DIMENSIONS:
            va, vb = _metric(ra, dim), _metric(rb, dim)
            entry[dim] = {"a": va, "b": vb, "delta": round(vb - va, 4) if va is not None and vb is not None else None}
        for name in ("completion_tokens", "prompt_tokens"):
            ta, tb = _tokens(ra, name), _tokens(rb, name)
            entry[name] = {"a": ta, "b": tb, "delta": tb - ta if ta is not None and tb is not None else None}
        la, lb = ra.get("latency_seconds"), rb.get("latency_seconds")
        entry["latency_seconds"] = {"a": la, "b": lb,
                                    "delta": round(lb - la, 3) if isinstance(la, (int, float)) and isinstance(lb, (int, float)) else None}
        entry["gates"] = {"a": bool(ra.get("passed_gates")), "b": bool(rb.get("passed_gates"))}
        paired.append(entry)
    return {
        "paired": paired,
        "errored": errored,
        "only_in_a": sorted(set(rows_a) - set(rows_b)),
        "only_in_b": sorted(set(rows_b) - set(rows_a)),
        "candidates": _candidate_totals(paired),
    }


def _candidate_totals(paired: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    by_candidate: Dict[str, List[Dict[str, Any]]] = {}
    for entry in paired:
        by_candidate.setdefault(entry["candidate"], []).append(entry)
    for candidate, entries in by_candidate.items():
        stats: Dict[str, Any] = {"paired": len(entries)}
        for dim in DIMENSIONS + ("completion_tokens", "prompt_tokens", "latency_seconds"):
            deltas = [e[dim]["delta"] for e in entries if e[dim]["delta"] is not None]
            a_vals = [e[dim]["a"] for e in entries if e[dim]["a"] is not None]
            b_vals = [e[dim]["b"] for e in entries if e[dim]["b"] is not None]
            stats[dim] = {
                "n": len(deltas),
                "mean_a": round(statistics.mean(a_vals), 4) if a_vals else None,
                "mean_b": round(statistics.mean(b_vals), 4) if b_vals else None,
                "mean_delta": round(statistics.mean(deltas), 4) if deltas else None,
                "worsened": sum(1 for d in deltas if d < 0) if dim not in ("completion_tokens", "prompt_tokens", "latency_seconds") else sum(1 for d in deltas if d > 0),
            }
        stats["gates_lost"] = sum(1 for e in entries if e["gates"]["a"] and not e["gates"]["b"])
        stats["gates_gained"] = sum(1 for e in entries if not e["gates"]["a"] and e["gates"]["b"])
        out[candidate] = stats
    return out


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:+.{digits}f}" if digits else f"{value:.0f}"
    return str(value)


def render(comparison: Dict[str, Any], a_name: str, b_name: str) -> str:
    lines = [f"# Eval comparison: A = {a_name}  vs  B = {b_name}", ""]
    for candidate, stats in comparison["candidates"].items():
        lines += [f"## {candidate}: {stats['paired']} paired attempts, "
                  f"gates lost {stats['gates_lost']}, gained {stats['gates_gained']}", "",
                  "| dimension | n | mean A | mean B | mean delta (B-A) | worsened |",
                  "|---|---:|---:|---:|---:|---:|"]
        for dim in DIMENSIONS + ("completion_tokens", "prompt_tokens", "latency_seconds"):
            s = stats[dim]
            lines.append(f"| {dim} | {s['n']} | {_fmt(s['mean_a'], 0 if 'tokens' in dim else 4).lstrip('+')} | "
                         f"{_fmt(s['mean_b'], 0 if 'tokens' in dim else 4).lstrip('+')} | "
                         f"{_fmt(s['mean_delta'], 0 if 'tokens' in dim else 4)} | {s['worsened']} |")
        lines.append("")
    lines += ["## Per-filing (aggregate / citation_fidelity / completion_tokens / latency)", "",
              "| candidate | ticker | form | run | agg A→B | cite A→B | out tok A→B | latency A→B | gates A→B |",
              "|---|---|---|---:|---|---|---|---|---|"]
    for e in comparison["paired"]:
        def pair(name: str, digits: int = 3) -> str:
            cell = e[name]
            return f"{_fmt(cell['a'], digits).lstrip('+')}→{_fmt(cell['b'], digits).lstrip('+')}"
        lines.append(f"| {e['candidate']} | {e['ticker']} | {e['filing_type']} | {e['run']} | {pair('aggregate')} | "
                     f"{pair('citation_fidelity')} | {pair('completion_tokens', 0)} | {pair('latency_seconds', 1)} | "
                     f"{'✓' if e['gates']['a'] else '✗'}→{'✓' if e['gates']['b'] else '✗'} |")
    if comparison["errored"]:
        lines += ["", f"## Attempts with an error on either side ({len(comparison['errored'])}) — excluded from means", ""]
        for e in comparison["errored"]:
            lines.append(f"- {e['candidate']} {e['ticker']} {e['filing_type']} run {e['run']}: A={e['error_a']!r} B={e['error_b']!r}")
    if comparison["only_in_a"] or comparison["only_in_b"]:
        lines += ["", f"Unpaired: only in A {len(comparison['only_in_a'])}, only in B {len(comparison['only_in_b'])}"]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report_a", type=Path)
    parser.add_argument("report_b", type=Path)
    parser.add_argument("--json", type=Path, default=None, help="also write the paired deltas as JSON")
    args = parser.parse_args(argv)
    a, b = _load(args.report_a), _load(args.report_b)
    comparison = pair_reports(a, b)
    comparison["harness"] = {"a": a.get("harness"), "b": b.get("harness")}
    print(render(comparison, args.report_a.name, args.report_b.name))
    if args.json:
        args.json.write_text(json.dumps(comparison, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
