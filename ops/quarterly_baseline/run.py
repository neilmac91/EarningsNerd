"""Run E211's fixed, read-only historical-source baseline; never selects a production image.

The reviewed main workflow owns authentication and the SQL session readback. The
entire separate checkout supplies the old script, imports and requirements. Raw
process output and exception strings never enter the public log or artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".ops-quarterly-baseline"
SOURCE_SHA = "80fa90d48ed1546e7770d88fd3b1b0aa05b1f89d"
COHORT = ("BIIB", "BMRN", "CRM", "FTNT", "JPM", "META", "NVDA", "RDDT", "REGN")
PGOPTIONS = "-c lock_timeout=10s -c statement_timeout=120s -c default_transaction_read_only=on"
FILES = ("backend/requirements.txt", "backend/scripts/repair_quarterly_facts.py",
         "backend/app/database.py", "backend/app/services/quarterly_fact_repair.py")


def verified_source() -> dict:
    """Refuse a different or modified checkout before installing or running its code."""
    def git(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(SOURCE), *args], capture_output=True,
                                text=True, check=False)
        if result.returncode:
            raise ValueError("baseline source could not be verified")
        return result.stdout.strip()

    if git("rev-parse", "HEAD") != SOURCE_SHA:
        raise ValueError("baseline source commit does not match the fixed source")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("baseline source checkout has local changes")
    tree = git("rev-parse", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise ValueError("baseline source tree could not be verified")
    return {"source_commit": SOURCE_SHA, "source_tree": tree,
            "source_file_sha256": {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
                                   for name in FILES}}


def public_report(report: object) -> dict:
    """Keep the existing filing-data report, replacing the script's raw failure prose."""
    if not isinstance(report, dict) or report.get("dry_run") is not True:
        raise ValueError("baseline did not produce a dry-run report")
    companies = report.get("companies")
    if not isinstance(companies, list) or len(companies) != len(COHORT):
        raise ValueError("baseline report does not contain the fixed cohort")
    if sorted(item.get("ticker", "") for item in companies if isinstance(item, dict)) != sorted(COHORT):
        raise ValueError("baseline report cohort does not match")
    if type(report.get("failed")) is not int or report["failed"] != sum("error" in item for item in companies):
        raise ValueError("baseline failure count does not match its companies")

    def project(value):
        if isinstance(value, dict):
            return {key: "baseline company failed; details withheld" if key == "error" else project(item)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [project(item) for item in value]
        return value

    return project(report)


def run(output: Path) -> int:
    source = verified_source()
    workflow_sha = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", workflow_sha):
        raise ValueError("workflow commit is unavailable")
    if os.environ.get("PGOPTIONS") != PGOPTIONS or any(
        os.environ.get(name) != "1" for name in ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC")
    ):
        raise ValueError("baseline requires its fixed read-only SQL and SEC guards")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    receipt = {**source, "workflow_commit": workflow_sha, "cohort": list(COHORT),
               "execution": "github_actions_runner", "production_image_used": False,
               "observed_at": datetime.now(timezone.utc).isoformat(), "dry_run": True,
               "status": "started", "report_complete": False,
               "limit": "Historical source against current data, not a pre-merge snapshot or container reproduction."}
    receipt_path = output / "source-receipt.json"

    def save_receipt():
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    save_receipt()
    # The old CLI prints exception strings. Capture both streams outside the artifact
    # directory, and retain only the parsed report's closed error projection.
    with tempfile.TemporaryDirectory(prefix="quarterly-baseline-private-") as private:
        raw_report = Path(private) / "report.json"
        with (Path(private) / "stdout").open("wb") as stdout, (Path(private) / "stderr").open("wb") as stderr:
            result = subprocess.run(
                [sys.executable, "-I", str(SOURCE / "backend/scripts/repair_quarterly_facts.py"),
                 "--tickers", ",".join(COHORT), "--limit", "50", "--output", str(raw_report)],
                cwd=SOURCE / "backend", stdout=stdout, stderr=stderr, check=False,
            )
        try:
            report = public_report(json.loads(raw_report.read_text()))
        except (OSError, ValueError, TypeError):
            receipt["status"] = "failed_without_valid_report"
            save_receipt()
            print("::error::baseline failed without a complete dry-run report; raw diagnostics withheld")
            return 1
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (output / "report.json").write_text(encoded)
    complete = result.returncode == 0 and report["failed"] == 0
    receipt.update(status="complete" if complete else "failed", report_complete=True,
                   run_id=report.get("run_id"), failed_companies=report["failed"],
                   report_sha256=hashlib.sha256(encoded.encode()).hexdigest())
    save_receipt()
    print("Quarterly historical-source baseline: " + ("complete (9 companies)" if complete else "failed; see projected report"))
    return 0 if complete else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-source", action="store_true")
    mode.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.verify_source:
            verified_source()
            print(f"Quarterly baseline source verified: {SOURCE_SHA}")
            return 0
        return run(args.output)
    except (OSError, ValueError):
        print("::error::quarterly baseline refused: source, metadata or execution guards could not be verified")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
