"""Judge any retained eval report through the subscription strong judge; the prompt-candidate acceptance gate.

``evals.judge_readout`` judges the fixed weekly cohort and builds the bounded weekly readout. This
command judges any retained eval report — a pull request's ``eval-baseline`` artifact
(``backend/evals/reports/eval_*.json``) or a local run — through the same harness judge path
(``runner._maybe_judge``: the retained excerpt, application-owned statement evidence, XBRL
serialization and full-coverage bounds) on the local machine, where ``claude -p`` authenticates
through the logged-in Claude subscription instead of API credits. It writes ``judged.json`` (every
attempt with its fresh verdict) and ``judged.md`` (gate counts, a per-attempt verdict table and the
#805 negative-control section). It is the acceptance instrument the September 16 #805 assessment
prescribes for prompt candidates (``tasks/pr805-assessment-2026-09-16.md``).

    cd backend && python -m evals.judge_report <artifact>/eval_<stamp>.json [--output-dir DIR] [--concurrency 2]

Nothing is generated here and no generator credential is read. A report whose golden set differs
from this checkout, or that carries a foreign or duplicate attempt identity, is refused before the
first judge call (no spend). Any ``judge`` the report already carried is discarded: every verdict
comes from this run, under the judge contract this checkout defines. Attempts without retained judge
inputs (failed attempts, and the A-candidate route, which retains no payload) are reported as not
judgeable, never judged against a re-fetched source. Exit status is 0 only when every judgeable
attempt received a complete verdict; a documented partial result exits 1 by design.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from app.services.ai_readout import DIMENSIONS
from app.utils.datetimes import iso_z, utcnow
from evals.judge import JUDGE_CONTRACT_VERSION, JUDGE_GATES
from evals.weekly_readout import GOLDEN_PATH, JUDGE_ID

DEFAULT_CONCURRENCY = 2  # a subscription session, not a metered API: keep the parallel verdicts small
REPORTS_DIR = Path(__file__).with_name("reports") / "judged"
# The #805 first-assessment negative controls (tasks/quality-explanations-first-readout-2026-09-09.md):
# filings whose September 9 outputs carried a false explanation over correct figures. A candidate that
# grounds explanations must move these from a G4/G5 failure to abstention, not merely pass on average.
CONTROL_TICKERS = ("AAPL", "AMZN", "BA", "JPM", "MELI", "NVDA", "PFE", "PLTR", "RIVN")
_GATE_CODE = re.compile(r"^\s*(G\d)\b")

Identity = Tuple[Any, Any, Any, Any, Any]


def load_golden() -> List[Dict[str, Any]]:
    return json.loads(GOLDEN_PATH.read_text())["filings"]


def identity(row: Dict[str, Any]) -> Identity:
    return (row.get("candidate"), row.get("ticker"), row.get("filing_type"), row.get("accession_number"), row.get("run"))


def resolve_filing(row: Dict[str, Any], filings: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The one golden filing an attempt names, or None when none or several match.

    The runner's own rows carry ticker, filing_type and run but a None accession (only the weekly
    readout stamps the cohort accession onto its rows), so identity is ticker + form, and the accession
    must agree when the row carries one. Several golden entries for one ticker + form make the row
    ambiguous, which is refused rather than guessed."""
    matches = [f for f in filings
               if f["ticker"] == row.get("ticker") and f["filing_type"] == row.get("filing_type")
               and row.get("accession_number") in (None, f["accession_number"])]
    return matches[0] if len(matches) == 1 else None


def retained_grounding(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The judge inputs an attempt retained, in the shape ``runner._maybe_judge`` reads; None when absent."""
    if row.get("error") or not isinstance(row.get("payload"), dict) or "grounding_excerpt" not in row:
        return None
    return {"excerpt": row.get("grounding_excerpt") or "", "xbrl_metrics": row.get("xbrl_grounding"),
            "statement_source": row.get("statement_source")}


def check_provenance(report: Dict[str, Any], filings: List[Dict[str, Any]]) -> None:
    """Refuse, before any subscription call, a report this checkout cannot judge faithfully.

    The golden set (filing identities and ground truth) must be the one this checkout carries, every
    attempt must name a golden filing, and no attempt identity may repeat."""
    harness = report.get("harness") or {}
    if harness.get("golden_set_sha256") != hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest():
        raise ValueError("Golden-set provenance differs from this checkout")
    rows = report.get("results", [])
    identities = [identity(r) for r in rows]
    if not identities:
        raise ValueError("Report carries no attempts")
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate attempt identity")
    if any(resolve_filing(r, filings) is None for r in rows):
        raise ValueError("Foreign or ambiguous attempt identity")


async def judge_rows(results: List[Dict[str, Any]], filings: Iterable[Dict[str, Any]], judge_id: str,
                     concurrency: int, printer: Callable[[str], None] = print) -> None:
    """Judge every row with retained inputs in place (``row["judge"]``) through ``runner._maybe_judge``.

    Shared by the weekly readout and the general report judge so both produce verdicts the same way."""
    from evals import runner
    from evals.schema import GoldenFiling

    filings = list(filings)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(row: Dict[str, Any]) -> None:
        resolved = resolve_filing(row, filings)
        grounding = retained_grounding(row)
        if resolved is None or grounding is None:
            return
        filing = GoldenFiling.from_dict(resolved)
        async with semaphore:
            row["judge"] = await runner._maybe_judge(judge_id, row["payload"], filing, grounding)
        judge = row["judge"] or {}
        printer(f"  {row.get('candidate')} {row['ticker']} {row['filing_type']} run {row.get('run')}: "
                f"{judge.get('verdict')} dims={judge.get('dimensions')} lengths={judge.get('input_lengths')}"
                f"{' error=' + str(judge.get('error')) if judge.get('error') else ''}")

    await asyncio.gather(*(one(row) for row in results))


def complete_verdict(judge: Any) -> bool:
    return (isinstance(judge, dict) and not judge.get("error") and judge.get("input_complete") is True
            and judge.get("verdict") in ("PASS", "FAIL"))


def gate_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Attempts failing each gate code (an attempt counts once per code), keyed by the contract's gates."""
    counts: Counter = Counter()
    for row in results:
        judge = row.get("judge")
        if not isinstance(judge, dict):
            continue
        codes = {m.group(1) for g in judge.get("gate_failures") or [] for m in [_GATE_CODE.match(str(g))] if m}
        counts.update(codes)
    return {gate: counts.get(gate.split()[0], 0) for gate in JUDGE_GATES}


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    judgeable = [r for r in results if retained_grounding(r) is not None]
    complete = [r for r in judgeable if complete_verdict(r.get("judge"))]
    return {"attempts": len(results), "judgeable": len(judgeable), "judged": len(complete),
            "errors": len(judgeable) - len(complete),
            "negative": sum(r["judge"]["verdict"] == "FAIL" for r in complete),
            "gate_counts": gate_counts(results),
            "complete": bool(judgeable) and len(complete) == len(judgeable)}


async def judge_report(report: Dict[str, Any], judge_id: str = JUDGE_ID,
                       concurrency: int = DEFAULT_CONCURRENCY) -> Dict[str, Any]:
    """Return the judged report: every judgeable attempt carries a fresh verdict, plus the summary."""
    filings = load_golden()
    # Every verdict below is produced now, by this judge, under this contract; nothing the report
    # already carried under `judge` survives.
    results: List[Dict[str, Any]] = [{**row, "judge": None} for row in report.get("results", [])]
    harness = {**(report.get("harness") or {}), "judge": judge_id, "judge_contract_version": JUDGE_CONTRACT_VERSION}
    check_provenance(report, filings)
    await judge_rows(results, filings, judge_id, concurrency)
    return {**report, "phase": "judged", "results": results, "harness": harness,
            "judged_at": iso_z(utcnow()), "judged_summary": summarize(results)}


def _row_cell(row: Dict[str, Any]) -> str:
    judge = row.get("judge") or {}
    dims = judge.get("dimensions") or {}
    detail = judge.get("error") or "; ".join(judge.get("gate_failures") or [])
    return (f"| {row.get('candidate')} | {row.get('ticker')} | {row.get('filing_type')} | {row.get('run')} | "
            f"{judge.get('verdict')} | " + " | ".join(str(dims.get(key, "-")) for key in DIMENSIONS)
            + f" | {str(detail).replace('|', '/').replace(chr(10), ' ')[:300]} |")


def render_markdown(judged: Dict[str, Any]) -> str:
    harness = judged.get("harness") or {}
    summary = judged.get("judged_summary") or summarize(judged.get("results", []))
    results = judged.get("results", [])
    lines = [f"# Judged eval report: {'complete' if summary['complete'] else 'partial'}", "",
             f"Source `{harness.get('source_sha')}`; generator `{harness.get('model')}`; judge `{harness.get('judge')}` "
             f"(contract version {harness.get('judge_contract_version')}); run {judged.get('run_url') or 'local'}.",
             "",
             f"Attempts {summary['attempts']}; judgeable {summary['judgeable']}; judged {summary['judged']}; "
             f"errors {summary['errors']}; negative judgments {summary['negative']}.", "",
             "| gate | attempts failing |", "|---|---|"]
    lines += [f"| {gate} | {count} |" for gate, count in summary["gate_counts"].items()]
    header = ("| candidate | filing | form | run | verdict | " + " | ".join(DIMENSIONS) + " | gate failures / error |",
              "|---|---|---|---|---|" + "---|" * len(DIMENSIONS) + "---|")
    judged_rows = [r for r in results if isinstance(r.get("judge"), dict)]
    if judged_rows:
        lines += ["", "## Every judged attempt", "", *header, *(_row_cell(r) for r in judged_rows)]
    controls = [r for r in judged_rows if r.get("ticker") in CONTROL_TICKERS]
    lines += ["", "## #805 negative controls", "",
              "Filings whose September 9 outputs carried a false explanation over correct figures. The bar for a "
              "grounding candidate is abstention here (no G4/G5 failure), not a better average.", ""]
    if controls:
        lines += [*header, *(_row_cell(r) for r in sorted(controls, key=lambda r: (str(r.get("ticker")), str(r.get("run")))))]
    else:
        lines.append("No control filing was judged in this report.")
    lines += ["", "This report never automatically arms an AI feature or re-pins a baseline."]
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, judged: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "judged.json").write_text(json.dumps(judged, indent=2) + "\n")
    (output_dir / "judged.md").write_text(render_markdown(judged))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", type=Path, help="a retained eval report (eval_<stamp>.json) with judge inputs")
    parser.add_argument("--judge", default=JUDGE_ID, help=f"judge model id (default {JUDGE_ID})")
    parser.add_argument("--output-dir", type=Path, default=None, help="default evals/reports/judged/<UTC stamp>/")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text())
    output_dir = args.output_dir or REPORTS_DIR / utcnow().strftime("%Y%m%dT%H%M%SZ")
    harness = report.get("harness") or {}
    print(f"Judging {len(report.get('results', []))} attempts from {args.report} with {args.judge} "
          f"(contract version {JUDGE_CONTRACT_VERSION}; source {harness.get('source_sha')}, "
          f"generator {harness.get('model')}, run {report.get('run_url') or 'local'})")
    try:
        judged = asyncio.run(judge_report(report, judge_id=args.judge, concurrency=args.concurrency))
    except ValueError as exc:
        print(f"Refusing to judge: {exc}")
        return 2
    write_outputs(output_dir, judged)
    summary = judged["judged_summary"]
    print(f"Judged {summary['judged']}/{summary['judgeable']} judgeable attempts ({summary['attempts']} total); "
          f"negative {summary['negative']}; gates {summary['gate_counts']}")
    print(f"Outputs: {output_dir}")
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    from app.services import ai_metrics

    ai_metrics.set_trigger("eval")
    raise SystemExit(main())
