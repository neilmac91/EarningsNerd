"""Calibrate the attribution gate offline against a judged eval report.

    cd backend && python scripts/calibrate_attribution_gate.py <judged.json> [--show N]

``judged.json`` is the output of ``python -m evals.judge_report`` (judge contract v2): every attempt
carries ``raw_sections`` (the structured sections the gate reads in production), the retained
``grounding_excerpt`` (the gate's source basis) and the judge's verdict with gate failures. The gate
runs UNARMED here — nothing is mutated or regenerated — and the script reports attempt-level recall
against the judge's G4 (unsupported cause) findings and the "extra" population (attempts the gate
flags that the judge did not fail for cause: a mix of judge misses and gate false positives that
only a hand read separates). ``--show N`` prints up to N flagged clauses per attempt for that read.
The arming bar is in tasks/attribution-guard-plan-2026-09-17.md.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

_G4 = re.compile(r"\s*G4\b")


def calibrate(report: dict) -> tuple[dict, list]:
    from app.services.ai.attribution_gate import gate_attributions  # after the offline env is set

    totals: Counter = Counter()
    rows = []
    for row in report.get("results", []):
        sections = row.get("raw_sections") or {}
        audit = gate_attributions(sections, row.get("grounding_excerpt") or "", armed=False) or {}
        flagged = audit.get("unverified") or []
        judge = row.get("judge") or {}
        g4 = any(_G4.match(str(g)) for g in judge.get("gate_failures") or [])
        totals["attempts"] += 1
        totals["clauses"] += audit.get("checked", 0)
        totals["flagged_clauses"] += len(flagged)
        totals["attempts_flagged"] += bool(flagged)
        totals["judge_g4"] += g4
        totals["caught"] += g4 and bool(flagged)
        totals["missed"] += g4 and not flagged
        totals["extra"] += bool(flagged) and not g4
        rows.append((row.get("ticker"), row.get("filing_type"), row.get("run"), g4, flagged))
    return dict(totals), rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", type=Path)
    parser.add_argument("--show", type=int, default=0)
    args = parser.parse_args(argv)
    totals, rows = calibrate(json.loads(args.report.read_text()))
    print(json.dumps(totals, sort_keys=True))
    for ticker, form, run, g4, flagged in rows:
        for item in flagged[: args.show]:
            print(f"{ticker} {form} r{run} judge_g4={g4} [{item['slot']}] {item['connective']} {item['clause'][:110]} | cov={item['coverage']}")
    return 0


if __name__ == "__main__":
    import os

    # Offline: no database, provider or Redis is touched; Settings still needs a secret to load.
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    os.environ.setdefault("SECRET_KEY", "offline-calibration-not-a-secret")
    raise SystemExit(main())
