"""Regression gate: diff an eval report against the pinned baseline (B1).

`baseline_scores.json` pins the current production-pipeline quality as the bar to protect.
This gate reads a fresh `evals/reports/eval_*.json`, compares each candidate's summary stats
against the pinned baseline per-dimension, and **exits non-zero on any HARD regression** so CI
can block a quality-eroding change. WARN findings print but never fail the build.

It is deliberately deterministic and dependency-free (stdlib only): the same inputs always
produce the same verdict, so it is unit-testable offline with no network/AI and safe to run in
CI. The LLM judge is intentionally NOT part of the gate (flaky, costly) — see RUNBOOK.

    python -m evals.regression_gate --latest          # gate the newest report
    python -m evals.regression_gate path/to/eval.json # gate a specific report

Tolerances are absolute deltas (not configurable from the report, on purpose: a candidate must
not be able to relax its own gate). They are sized against the baseline's measured run-to-run
variance — see the calibration note on HARD_FAIL below.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASELINE_PATH = Path(__file__).with_name("baseline_scores.json")
REPORTS_DIR = Path(__file__).with_name("reports")

# --- HARD-fail thresholds (absolute deltas; a breach exits non-zero) -----------------------
# Direction is encoded per metric in `_HARD_GATES`. Calibration basis: the pinned baseline is
# run over the full verified golden set with multiple runs/filing; its `aggregate_stdev` is the
# measured noise floor. Hard tolerances are set comfortably above that floor so ordinary
# run-to-run jitter never trips the gate, while a genuine quality drop does:
#   - gate_fail_rate: a hard-gate veto (fabricated number / leaked notice) must NEVER regress;
#     epsilon-only tolerance for float safety.
#   - numeric_precision / coverage: production sits at ~1.0 with ~0 variance, so a 0.05 drop is
#     unambiguously a regression, not noise.
#   - numeric_accuracy (recall): the highest-weighted but noisiest dimension on a small per-PR
#     subset (one missing fact on one filing moves the mean a lot) → a looser 0.10 band.
_HARD_GATES = (
    # (metric, direction, tolerance, human label)
    ("gate_fail_rate", "increase", 0.005, "hard-gate vetoes (fabricated number / hygiene)"),
    ("mean_numeric_precision", "decrease", 0.05, "numeric precision (labeled-field fidelity)"),
    ("mean_coverage", "decrease", 0.05, "section coverage"),
    ("mean_numeric_accuracy", "decrease", 0.10, "numeric recall"),
)

# --- WARN thresholds (advisory; print but do not fail) -------------------------------------
_WARN_GATES = (
    ("pass_rate", "decrease", 0.05, "pass rate (gate-passing runs clearing the threshold)"),
    ("aggregate_stdev", "increase", 0.05, "consistency (run-to-run variance)"),
    ("schema_valid_rate", "decrease", 0.05, "schema validity"),
    ("mean_financial_depth", "decrease", 0.10, "financial depth"),
    ("mean_specificity", "decrease", 0.10, "narrative specificity (anti-boilerplate)"),
    ("mean_currency_consistency", "decrease", 0.05, "currency labeling for foreign filers (FPI $-mislabel guard)"),
    # T3.0 content-quality WARN gates. They only bind once the baseline is re-pinned on a v2 run to
    # record these dimensions (the gate skips any metric absent from the pinned baseline), so they
    # ship advisory — a signal for the Tier-3 content rewrite, not a blocker on today's pipeline.
    ("mean_redundancy", "decrease", 0.05, "one-home redundancy (figures restated across sections)"),
    ("mean_delta_consistency", "decrease", 0.05, "prose/table delta consistency"),
    # T5.4: ships advisory like the T3.0 dims above — binds only once a re-pin records it.
    ("mean_forward_quote_fidelity", "decrease", 0.05, "forward-quote verbatim fidelity (§5 quotes located in filing text)"),
    ("mean_citation_fidelity", "decrease", 0.05, "supporting-evidence verbatim fidelity (P&L-takeaway + footnote excerpts)"),
    # Companion VOLUME floor for the citation dim (staff review on #626): the fidelity ratio is
    # one-sided — an evidence-EMISSION collapse (the model stops producing verifiable excerpts)
    # would read as IMPROVED fidelity. checked/filing sits ~6.4 on the pinned behavior; a 2.0
    # absolute drop (~30%) is deliberately generous — this is a volume signal, not a quality bar,
    # so ordinary evidence-mix shift never trips it while a collapse self-announces.
    ("mean_citation_checked", "decrease", 2.0, "citation evidence volume (emission-collapse guard for the fidelity ratio)"),
)


@dataclass
class Finding:
    severity: str  # "HARD" | "WARN"
    candidate: str
    metric: str
    baseline: Optional[float]
    candidate_value: float
    delta: Optional[float]
    label: str

    def __str__(self) -> str:
        if self.baseline is None:
            return f"[{self.severity}] {self.candidate}: {self.metric} = {self.candidate_value:.4g} — {self.label}"
        arrow = "↑" if self.delta > 0 else "↓"
        return (
            f"[{self.severity}] {self.candidate}: {self.metric} {arrow} "
            f"{self.candidate_value:.4g} vs baseline {self.baseline:.4g} "
            f"(Δ{self.delta:+.4g}) — {self.label}"
        )


def load_baseline(path: Path = BASELINE_PATH) -> Dict[str, Any]:
    """Load the pinned baseline. Candidate stats live under the `candidates` map."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_latest_report(reports_dir: Path = REPORTS_DIR) -> Optional[Path]:
    reports = sorted(reports_dir.glob("eval_*.json"))
    return reports[-1] if reports else None


def _breaches(direction: str, base: float, cand: float, tol: float) -> bool:
    """True when the candidate moved the wrong way by more than `tol`."""
    if direction == "increase":  # higher is worse (gate_fail_rate, stdev)
        return cand > base + tol
    return cand < base - tol  # "decrease": lower is worse


def _check(
    gates: Tuple[Tuple[str, str, float, str], ...], severity: str, candidate: str,
    base_stats: Dict[str, Any], cand_stats: Dict[str, Any],
) -> List[Finding]:
    out: List[Finding] = []
    for metric, direction, tol, label in gates:
        if metric not in base_stats or metric not in cand_stats:
            continue  # a stat the baseline never recorded can't regress
        base, cand = float(base_stats[metric]), float(cand_stats[metric])
        if _breaches(direction, base, cand, tol):
            out.append(Finding(severity, candidate, metric, base, cand, cand - base, label))
    return out


def compare_candidate(
    base_stats: Dict[str, Any], cand_stats: Dict[str, Any], candidate: str = "baseline"
) -> List[Finding]:
    """All HARD + WARN findings for one candidate's summary vs its pinned baseline stats."""
    figure_findings = []
    measured = cand_stats.get("mean_untraceable_dollar_figures")
    if measured is not None and measured > 0:
        figure_findings.append(Finding("WARN", candidate, "mean_untraceable_dollar_figures", None, measured, None,
                                       "absolute advisory: untraceable dollar figures in measured raw prose"))
    return (
        figure_findings + _check(_HARD_GATES, "HARD", candidate, base_stats, cand_stats)
        + _check(_WARN_GATES, "WARN", candidate, base_stats, cand_stats)
    )


def evaluate_report(
    report: Dict[str, Any], baseline: Dict[str, Any],
    only: Optional[str] = None,
) -> tuple[List[Finding], List[str]]:
    """Gate a full report. Returns (findings, notes).

    `notes` records candidates present in the report but absent from the pinned baseline (they
    can't be regression-checked — informational, not a failure)."""
    base_candidates = baseline.get("candidates", {})
    report_summary = report.get("summary") or {}
    findings, notes = _check_completeness(report, only)
    if not isinstance(report_summary, dict):
        return findings, notes
    for candidate, cand_stats in report_summary.items():
        if only and candidate != only:
            continue
        if not isinstance(cand_stats, dict):
            continue
        base_stats = base_candidates.get(candidate)
        if not base_stats:
            notes.append(f"no pinned baseline for candidate '{candidate}' — skipped")
            continue
        findings.extend(compare_candidate(base_stats, cand_stats, candidate))
        if "mean_untraceable_dollar_figures" in cand_stats:
            if base_stats.get("mean_untraceable_dollar_figures") is None:
                notes.append(f"{candidate}: figure trace has no pinned reference measurement; absolute advisory only")
            notes.append(f"{candidate}: figure trace measured={cand_stats.get('figure_trace_measured', 0)} "
                         f"unavailable={cand_stats.get('figure_trace_unavailable', 0)} errors={cand_stats.get('figure_trace_errors', 0)}; "
                         "unavailable is not measured zero")
    return findings, notes


def _check_completeness(report: Dict[str, Any], only: Optional[str]) -> tuple[List[Finding], List[str]]:
    """Validate the requested attempt population before considering scored-only quality means.

    The manifest is recorded before execution: inferring a cohort/repeat count from surviving
    results would silently accept a missing final repeat or a wholly missing filing. Historical
    summary-only reports cannot establish completeness; compare_candidate remains stats-only.
    """
    findings: List[Finding] = []
    notes: List[str] = []

    def fail(candidate: str, metric: str, value: int, label: str) -> None:
        findings.append(Finding("HARD", candidate, metric, None, value, None, label))

    harness = report.get("harness")
    harness = harness if isinstance(harness, dict) else {}
    candidates, runs, filings = (harness.get(k) for k in ("candidates", "runs_per_candidate", "filings"))
    valid_candidates = (isinstance(candidates, list) and bool(candidates)
                        and all(isinstance(c, str) and c.strip() for c in candidates)
                        and len(set(candidates)) == len(candidates))
    valid_filings = (isinstance(filings, list) and bool(filings)
                     and all(isinstance(f, dict) and all(isinstance(f.get(k), str) and f[k].strip()
                             for k in ("ticker", "filing_type")) for f in filings))
    cohort = [(f["ticker"], f["filing_type"]) for f in filings] if valid_filings else []
    valid_manifest = (valid_candidates and type(runs) is int and runs > 0
                      and valid_filings and len(set(cohort)) == len(cohort))
    if not valid_manifest:
        fail(only or "report", "attempt_manifest", 1,
             "missing/invalid requested candidates, filing cohort or repeat count; completeness unverified")

    summary = report.get("summary")
    if not isinstance(summary, dict) or not summary:
        fail(only or "report", "attempt_summary", 1, "missing candidate summary")
        summary = {}
    raw_results = report.get("results")
    if not isinstance(raw_results, list) or any(not isinstance(r, dict) for r in raw_results):
        fail(only or "report", "attempt_results", 1, "missing/malformed attempt records")
        raw_results = []
    if valid_candidates:
        unexpected = set(summary) - set(candidates)
        unexpected_rows = sum(r.get("candidate") not in candidates for r in raw_results)
        if unexpected or unexpected_rows:
            fail("report", "unexpected_candidates", len(unexpected) + unexpected_rows,
                 "summary or results contain candidates outside the requested manifest")
        if only and only not in candidates:
            fail(only, "selected_candidate", 1, "selected candidate was not requested")
    selected = [only] if only else (candidates if valid_candidates else list(summary))
    for candidate in selected:
        rows = [r for r in raw_results if r.get("candidate") == candidate]
        scored = sum(isinstance(r.get("score"), dict) and bool(r["score"]) for r in rows)
        errors = sum(bool(r.get("error")) for r in rows)
        stats = summary.get(candidate)
        if not isinstance(stats, dict):
            fail(candidate, "attempt_summary", 1, "requested candidate has no summary")
            stats = {}
        if errors or stats.get("errors", 0):
            fail(candidate, "execution_errors", errors or 1, "evaluation execution errors block the gate")
        if scored != len(rows) or not rows:
            fail(candidate, "missing_scores", len(rows) - scored or 1, "attempts lack usable scores")
        for key, actual in (("n", len(rows)), ("scored", scored), ("errors", errors)):
            if type(stats.get(key)) is not int or stats[key] != actual:
                fail(candidate, "attempt_counts", 1, f"summary {key} does not match observed attempts")
        expected = len(cohort) * runs if valid_manifest else None
        notes.append(f"{candidate}: expected={expected if expected is not None else 'unverified'} "
                     f"attempted={len(rows)} scored={scored} errors={errors}; quality means use scored outputs only")
        if valid_manifest:
            identities = []
            for row in rows:
                if (type(row.get("run")) is not int
                        or not all(isinstance(row.get(k), str) for k in ("ticker", "filing_type"))):
                    fail(candidate, "attempt_identity", 1, "malformed filing/run identity")
                    continue
                identities.append((row["ticker"], row["filing_type"], row["run"]))
            wanted = {(ticker, form, run) for ticker, form in cohort for run in range(runs)}
            observed = set(identities)
            missing, extra, duplicates = len(wanted - observed), len(observed - wanted), len(identities) - len(observed)
            if missing or extra or duplicates:
                fail(candidate, "incomplete_attempts", missing + extra + duplicates,
                     f"requested attempt population differs: missing={missing} extra={extra} duplicates={duplicates}")
    return findings, notes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Diff an eval report against the pinned baseline.")
    parser.add_argument("report", nargs="?", help="path to evals/reports/eval_*.json")
    parser.add_argument("--latest", action="store_true", help="gate the newest report in evals/reports/")
    parser.add_argument("--candidate", default=None, help="only gate this candidate (default: all)")
    parser.add_argument("--baseline", default=str(BASELINE_PATH), help="path to baseline_scores.json")
    args = parser.parse_args(argv)

    report_path = Path(args.report) if args.report else (find_latest_report() if args.latest else None)
    if not report_path:
        print("error: pass a report path or --latest (no eval_*.json found in reports/)", file=sys.stderr)
        return 2
    if not report_path.exists():
        print(f"error: report not found: {report_path}", file=sys.stderr)
        return 2

    baseline = load_baseline(Path(args.baseline))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    findings, notes = evaluate_report(report, baseline, only=args.candidate)

    print(f"Regression gate: {report_path.name} vs {Path(args.baseline).name} "
          f"(baseline: {baseline.get('golden_set_size', '?')} filings × "
          f"{baseline.get('runs_per_candidate', '?')} runs)")
    for note in notes:
        print(f"  note: {note}")

    hard = [f for f in findings if f.severity == "HARD"]
    warn = [f for f in findings if f.severity == "WARN"]
    for f in warn:
        print(f"  {f}")
    for f in hard:
        print(f"  {f}")

    if hard:
        print(f"\nFAIL — {len(hard)} hard regression(s).")
        return 1
    print(f"\nPASS — no hard regressions ({len(warn)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
