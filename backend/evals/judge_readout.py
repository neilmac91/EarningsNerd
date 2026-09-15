"""Judge a retained weekly generation report through the subscription strong judge; build the readout.

The Monday workflow (``data-quality-weekly.yml``) generates the fixed eight-filing × three-repeat
cohort in CI, where the generator credential lives, and retains every attempt's judge inputs in
its ``report.json`` (``python -m evals.weekly_readout --generate-only``). This command replays
exactly those retained inputs through the harness's own judge path (``runner._maybe_judge``: the
same excerpt, application-owned statement evidence, XBRL serialization and full-coverage bounds)
on the local machine, where ``claude -p`` authenticates through the logged-in Claude subscription
instead of API credits, and then builds the bounded readout the ordinary report validates.

    cd backend && python -m evals.judge_readout <artifact>/report.json [--output-dir DIR] [--concurrency 2]

Nothing is generated here and no generator credential is read. A golden set or cohort that differs
from the generation run, or a foreign or duplicate attempt identity, is refused before the first
judge call (no spend, unavailable readout). A judge other than the readout contract's (``--judge``
exists for agreement checks) still judges every attempt and retains the verdicts in the judged
``report.json``, but yields an unavailable readout, never a fabricated one. Any ``judge`` a
generation report already carried is discarded: every verdict comes from this run. Exit status is
0 only for a complete readout, so a documented partial readout (e.g. attempts over the judge's
excerpt bound) exits 1 by design; re-running does not change that.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.ai_readout import EXPECTED, unavailable_readout
from app.utils.datetimes import iso_z, utcnow
from evals.weekly_readout import JUDGE_ID, build_readout, load_cohort, write_outputs

DEFAULT_CONCURRENCY = 2  # a subscription session, not a metered API: keep the parallel verdicts small
REPORTS_DIR = Path(__file__).with_name("reports") / "weekly-judged"


def retained_grounding(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The judge inputs a generation attempt retained, in the shape ``runner._maybe_judge`` reads.

    A failed or legacy attempt (no payload, no retained excerpt) has nothing to judge and stays an
    error in the readout; it is never judged against a re-fetched or different source."""
    if row.get("error") or not isinstance(row.get("payload"), dict) or "grounding_excerpt" not in row:
        return None
    return {"excerpt": row.get("grounding_excerpt") or "", "xbrl_metrics": row.get("xbrl_grounding"),
            "statement_source": row.get("statement_source")}


def check_provenance(report: Dict[str, Any], filings: List[Dict[str, Any]]) -> None:
    """Refuse, before any subscription call, a report this checkout cannot turn into a readout.

    The same golden-set and attempt-identity rules ``build_readout`` applies afterwards; failing
    them here costs nothing instead of twenty-four judged verdicts."""
    results = [{**row, "judge": None} for row in report.get("results", [])]
    build_readout(results, filings, {**report.get("harness", {}), "judge": JUDGE_ID})


async def judge_report(report: Dict[str, Any], judge_id: str = JUDGE_ID,
                       concurrency: int = DEFAULT_CONCURRENCY) -> Dict[str, Any]:
    """Return the judged report: every judgeable attempt carries a verdict, plus the readout."""
    from evals import runner
    from evals.schema import GoldenFiling

    filings = load_cohort()
    # Every verdict below is produced now, by this judge, from the retained inputs; nothing a
    # generation report already carried under `judge` survives into the readout.
    results: List[Dict[str, Any]] = [{**row, "judge": None} for row in report.get("results", [])]
    harness = {**report.get("harness", {}), "judge": judge_id}
    try:
        check_provenance(report, filings)
    except (ValueError, TypeError, KeyError) as exc:
        print(f"Refusing to judge: {exc}")
        readout = unavailable_readout(
            f"Measurement provenance refused before judging ({type(exc).__name__}); no judge calls made")
        return {**report, "phase": "judged", "results": results, "summary": runner._summarize(results),
                "harness": harness, "judged_at": iso_z(utcnow()), "readout": readout}
    cohort = {(f["ticker"], f["filing_type"], f["accession_number"]): GoldenFiling.from_dict(f) for f in filings}
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(row: Dict[str, Any]) -> None:
        filing = cohort.get((row.get("ticker"), row.get("filing_type"), row.get("accession_number")))
        grounding = retained_grounding(row)
        if filing is None or grounding is None:
            return
        async with semaphore:
            row["judge"] = await runner._maybe_judge(judge_id, row["payload"], filing, grounding)
        judge = row["judge"] or {}
        print(f"  {row['ticker']} {row['filing_type']} run {row.get('run')}: {judge.get('verdict')} "
              f"dims={judge.get('dimensions')} lengths={judge.get('input_lengths')}"
              f"{' error=' + str(judge.get('error')) if judge.get('error') else ''}")

    await asyncio.gather(*(one(row) for row in results))
    try:
        readout = build_readout(results, filings, harness, run_url=report.get("run_url"))
    except (ValueError, TypeError, KeyError) as exc:
        readout = unavailable_readout(
            f"Measurement validation failed ({type(exc).__name__}); judged attempt evidence retained")
    return {**report, "phase": "judged", "results": results, "summary": runner._summarize(results),
            "harness": harness, "judged_at": iso_z(utcnow()), "readout": readout}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", type=Path,
                        help="report.json from the Monday run's weekly-judged-readout-<run_id> artifact")
    parser.add_argument("--judge", default=JUDGE_ID,
                        help=f"judge model id (default {JUDGE_ID}, the readout contract). Another id, e.g. for "
                             "an agreement check, retains its verdicts but cannot produce a valid readout.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="default evals/reports/weekly-judged/<UTC stamp>/")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text())
    output_dir = args.output_dir or REPORTS_DIR / utcnow().strftime("%Y%m%dT%H%M%SZ")
    harness = report.get("harness", {})
    print(f"Judging {len(report.get('results', []))} retained attempts from {args.report} with {args.judge} "
          f"(source {harness.get('source_sha')}, generator {harness.get('model')}, run {report.get('run_url')})")
    judged = asyncio.run(judge_report(report, judge_id=args.judge, concurrency=args.concurrency))
    readout = judged["readout"]
    write_outputs(output_dir, readout, judged)
    print(f"Weekly readout: {readout['status']}; judged={readout['scored']}/{EXPECTED}; {readout['reason']}")
    print(f"Outputs: {output_dir}")
    return 0 if readout["status"] == "complete" else 1


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    from app.services import ai_metrics

    ai_metrics.set_trigger("eval")
    raise SystemExit(main())
