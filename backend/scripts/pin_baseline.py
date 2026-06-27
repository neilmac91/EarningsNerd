"""Pin (or re-pin) evals/baseline_scores.json from an eval report (B1).

The regression gate (`evals/regression_gate.py`) diffs fresh runs against the stats this script
freezes. Re-run it whenever you intentionally move the bar (flip USE_STRUCTURED_OUTPUT, change the
default model/prompt, adopt a quality improvement), and commit the new baseline alongside the
change it protects.

    cd backend
    python -m evals.runner --candidates baseline --runs 3
    python scripts/pin_baseline.py evals/reports/eval_<stamp>.json
    python scripts/pin_baseline.py --latest          # or just take the newest report

Stdlib only — no app imports, so it runs without the full Settings env.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"
REPORTS_DIR = EVALS_DIR / "reports"
BASELINE_PATH = EVALS_DIR / "baseline_scores.json"

_STAMP_RE = re.compile(r"eval_(\d{8}T\d{6}Z)\.json$")


def _snapshot_date(report_path: Path) -> str:
    """Derive an ISO-ish stamp from the report filename (eval_YYYYMMDDTHHMMSSZ.json)."""
    m = _STAMP_RE.search(report_path.name)
    if not m:
        return ""
    s = m.group(1)  # 20260627T174446Z
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z"


def build_baseline(report: Dict[str, Any], report_path: Path) -> Dict[str, Any]:
    summary = report.get("summary") or {}
    results: List[Dict[str, Any]] = report.get("results") or []
    distinct = {(r.get("ticker"), r.get("filing_type")) for r in results if r.get("score")}
    runs = max((r.get("run", 0) for r in results), default=0) + 1 if results else 0
    return {
        "snapshot_date": _snapshot_date(report_path),
        "source_report": report_path.name,
        "golden_set_size": len(distinct),
        "runs_per_candidate": runs,
        "harness": {
            "model": os.environ.get("AI_DEFAULT_MODEL", "deepseek-v4-pro"),
            "use_structured_output": os.environ.get("USE_STRUCTURED_OUTPUT", "false").lower() == "true",
            "judge": False,
        },
        "candidates": summary,
    }


def _resolve_report(arg: Optional[str], latest: bool) -> Path:
    if arg:
        return Path(arg)
    if latest:
        reports = sorted(REPORTS_DIR.glob("eval_*.json"))
        if not reports:
            raise SystemExit(f"no eval_*.json found in {REPORTS_DIR}")
        return reports[-1]
    raise SystemExit("pass a report path or --latest")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pin baseline_scores.json from an eval report.")
    parser.add_argument("report", nargs="?", help="path to evals/reports/eval_*.json")
    parser.add_argument("--latest", action="store_true", help="use the newest report in evals/reports/")
    parser.add_argument("--out", default=str(BASELINE_PATH), help="output path (default: evals/baseline_scores.json)")
    args = parser.parse_args(argv)

    report_path = _resolve_report(args.report, args.latest)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    baseline = build_baseline(report, report_path)
    if "baseline" not in baseline["candidates"]:
        raise SystemExit(f"report {report_path.name} has no 'baseline' candidate to pin")

    Path(args.out).write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    b = baseline["candidates"]["baseline"]
    print(f"Pinned {args.out} from {report_path.name}: "
          f"{baseline['golden_set_size']} filings × {baseline['runs_per_candidate']} runs")
    print(f"  pass_rate={b.get('pass_rate')} gate_fail_rate={b.get('gate_fail_rate')} "
          f"precision={b.get('mean_numeric_precision')} coverage={b.get('mean_coverage')} "
          f"recall={b.get('mean_numeric_accuracy')} stdev={b.get('aggregate_stdev')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
