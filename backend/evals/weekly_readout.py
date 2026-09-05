"""Fixed eight-filing × three-repeat strong-judge measurement; no credential means no calls."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import statistics

from app.services.ai_readout import DIMENSIONS, EXPECTED, JUDGE_MODEL, encode_readout, unavailable_readout, validate_readout

COHORT_PATH = Path(__file__).with_name("weekly_cohort.json")
GOLDEN_PATH = Path(__file__).with_name("golden_set.json")


def load_cohort() -> list[dict]:
    cohort = json.loads(COHORT_PATH.read_text())
    if cohort.get("runs") != 3 or len(cohort.get("filings", [])) != 8:
        raise ValueError("Weekly cohort must contain exactly eight filings with three repeats")
    golden = json.loads(GOLDEN_PATH.read_text())["filings"]
    selected = []
    identities = set()
    for wanted in cohort["filings"]:
        identity = (wanted["ticker"], wanted["filing_type"], wanted["accession_number"])
        matches = [f for f in golden if (f["ticker"], f["filing_type"], f["accession_number"]) == identity
                   and f.get("verified") and f.get("document_url")]
        if len(matches) != 1 or identity in identities:
            raise ValueError("Weekly cohort identity must resolve once to a verified accession")
        identities.add(identity)
        selected.append(matches[0])
    return selected


def build_readout(results: list[dict], filings: list[dict], harness: dict, *, run_url: str | None = None) -> dict:
    if filings != load_cohort() or harness.get("golden_set_sha256") != hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest():
        raise ValueError("Weekly cohort/golden provenance differs from the committed measurement")
    expected = {(f["ticker"], f["filing_type"], f["accession_number"], run) for f in filings for run in range(3)}
    if len(expected) != EXPECTED:
        raise ValueError("Readout requires the full fixed cohort")
    identities = [(r.get("ticker"), r.get("filing_type"), r.get("accession_number"), r.get("run")) for r in results]
    if len(set(identities)) != len(identities) or not set(identities) <= expected or any(r.get("candidate") != "baseline" for r in results):
        raise ValueError("Duplicate or foreign weekly measurement identity")
    if harness.get("judge") != JUDGE_MODEL:
        raise ValueError("Weekly measurement requires its strong judge")
    out = unavailable_readout()
    out.update(source_sha=harness.get("source_sha"), golden_set_sha256=harness.get("golden_set_sha256"),
               cohort_sha256=hashlib.sha256(COHORT_PATH.read_bytes()).hexdigest(),
               generator_model=harness.get("model"), run_url=run_url,
               artifact_url=f"{run_url}#artifacts" if run_url else None,
               missing=EXPECTED-len(results))
    valid = []
    for result in results:
        if result.get("error") or not result.get("score"):
            out["errors"] += 1
            continue
        out["completed"] += 1
        out["deterministic_vetoes"] += int(result.get("passed_gates") is not True)
        judge = result.get("judge")
        dims = judge.get("dimensions") if isinstance(judge, dict) else None
        if (not isinstance(judge, dict) or judge.get("error") or judge.get("input_complete") is not True or judge.get("verdict") not in ("PASS", "FAIL")
                or type(judge.get("passed")) is not bool or judge["passed"] != (judge["verdict"] == "PASS")
                or not isinstance(judge.get("gate_failures"), list)
                or not all(isinstance(x, str) for x in judge["gate_failures"])
                or not isinstance(dims, dict) or set(dims) != set(DIMENSIONS)
                or any(type(x) is not int or not 1 <= x <= 5 for x in dims.values())):
            out["errors"] += 1
            continue
        valid.append(judge)
    out["scored"] = len(valid)
    out["negative_judgments"] = sum(j["verdict"] == "FAIL" for j in valid)
    out["dimensions"] = {key: round(statistics.mean(j["dimensions"][key] for j in valid), 4) if valid else None for key in DIMENSIONS}
    out["status"] = "complete" if len(valid) == EXPECTED else "partial" if out["completed"] else "unavailable"
    out["reason"] = "All 24 attempts judged; negative judgments remain visible" if out["status"] == "complete" else "Incomplete generation or judge evidence; not a completed readout"
    return validate_readout(out)


async def measure() -> tuple[dict, dict]:
    # Keep this before importing the network-capable runner or reading any filings.
    if not os.environ.get("OPENAI_API_KEY", "").strip() or not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return unavailable_readout("Generator or strong-judge credential absent; no model calls made"), {"results": [], "harness": {}}
    from evals import runner
    from evals.schema import GoldenFiling

    filings = load_cohort()
    harness = runner._harness_metadata(JUDGE_MODEL)
    harness.update(candidates=["baseline"], runs_per_candidate=3,
                   filings=[{"ticker": f["ticker"], "filing_type": f["filing_type"]} for f in filings])
    if (not re.fullmatch(r"[0-9a-f]{40}", harness.get("source_sha", ""))
            or harness.get("use_statement_financials") is not True
            or harness.get("stream_section_reveal") is not True
            or harness.get("use_structured_output") is not False):
        return unavailable_readout("Measurement provenance or parity configuration missing; no model calls made"), {"results": [], "harness": harness}
    semaphore = asyncio.Semaphore(3)

    async def one(filing: dict) -> list[dict]:
        async with semaphore:
            try:
                rows = await runner._process_filing(GoldenFiling.from_dict(filing), ["baseline"], 3, JUDGE_MODEL)
            except Exception as exc:
                rows = [{"candidate": "baseline", "ticker": filing["ticker"], "filing_type": filing["filing_type"],
                         "run": run, "error": f"Filing measurement failed ({type(exc).__name__})", "score": None}
                        for run in range(3)]
            return [{**row, "accession_number": filing["accession_number"]} for row in rows]

    results = [r for group in await asyncio.gather(*(one(f) for f in filings)) for r in group]
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = f"https://github.com/neilmac91/EarningsNerd/actions/runs/{run_id}" if run_id else None
    report = {"results": results, "summary": runner._summarize(results), "harness": harness,
              "cohort": json.loads(COHORT_PATH.read_text())}
    try:
        readout = build_readout(results, filings, harness, run_url=run_url)
    except (ValueError, TypeError, KeyError) as exc:
        readout = unavailable_readout(f"Measurement validation failed ({type(exc).__name__}); raw attempt evidence retained")
    return readout, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("reports") / "weekly")
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        readout, report = asyncio.run(measure())
    except Exception as exc:  # Keep the report available, but visibly fail this measurement job.
        readout, report = unavailable_readout(f"Weekly measurement failed ({type(exc).__name__}); no completed readout"), {"results": [], "harness": {}}
    (args.output_dir / "readout.json").write_text(json.dumps(readout, indent=2) + "\n")
    (args.output_dir / "report.json").write_text(json.dumps({**report, "readout": readout}, indent=2) + "\n")
    (args.output_dir / "readout.b64").write_text(encode_readout(readout))
    (args.output_dir / "readout.md").write_text(
        f"# Weekly judged measurement: {readout['status']}\n\n{readout['reason']}\n\n"
        f"Expected {EXPECTED}; generated {readout['completed']}; judged {readout['scored']}; "
        f"errors {readout['errors']}; missing {readout['missing']}; negative judgments {readout['negative_judgments']}.\n\n"
        "This report never automatically arms an AI feature.\n")
    print(f"Weekly readout: {readout['status']}; judged={readout['scored']}/{EXPECTED}; {readout['reason']}")
    return 0 if readout["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
