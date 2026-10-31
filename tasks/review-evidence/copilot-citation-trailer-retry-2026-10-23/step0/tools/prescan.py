"""Pre-scan each artifact directory: does it hold a usable copilot-eval report? (offline, read only)

Writes TSV rows: run_id, status (usable|excluded), detail. A report is excluded when the artifact held no
copilot-eval.json, the JSON does not parse, it has no result rows (e.g. a credential-less preflight stub),
or it duplicates an earlier report's (timestamp, source_sha, summary) identity.

Usage: python -I prescan.py <run-artifacts.tsv> <artifacts_dir> <out.tsv> <usable-paths.txt>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

art_tsv, art_dir, out_tsv, usable_txt = sys.argv[1:5]
seen: dict[str, str] = {}
rows, usable = [], []
for line in open(art_tsv):
    run = line.split("\t", 1)[0]
    d = os.path.join(art_dir, run)
    path = os.path.join(d, "x", "copilot-eval.json")
    if os.path.exists(os.path.join(d, ".excluded")):
        rows.append((run, "excluded", "artifact " + open(os.path.join(d, ".excluded")).read().strip()))
        continue
    if not os.path.exists(path):
        listing = open(os.path.join(d, "zip-listing.txt")).read().split() if os.path.exists(os.path.join(d, "zip-listing.txt")) else []
        top = sorted({name.split("/", 1)[0] for name in listing})
        rows.append((run, "excluded", f"artifact holds no copilot-eval.json (top-level entries: {top})"))
        continue
    try:
        report = json.load(open(path))
    except ValueError as exc:
        rows.append((run, "excluded", f"copilot-eval.json does not parse: {exc}"))
        continue
    results = report.get("results") or []
    if not results:
        rows.append((run, "excluded", "copilot-eval.json has no result rows; failures: "
                     + "; ".join(report.get("failures") or ["none recorded"])))
        continue
    ident = hashlib.sha256(json.dumps([report.get("timestamp"), report.get("source_sha"), report.get("summary")],
                                      sort_keys=True).encode()).hexdigest()
    if ident in seen:
        rows.append((run, "excluded", f"duplicate of run {seen[ident]}'s report"))
        continue
    seen[ident] = run
    rows.append((run, "usable", f"{len(results)} rows; timestamp {report.get('timestamp')}; source_sha {report.get('source_sha')}"))
    usable.append(path)
with open(out_tsv, "w") as fh:
    for row in rows:
        fh.write("\t".join(row) + "\n")
with open(usable_txt, "w") as fh:
    fh.write("\n".join(usable) + "\n")
print(f"usable={len(usable)} excluded={sum(r[1] == 'excluded' for r in rows)}")
