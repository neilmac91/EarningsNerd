"""Validity precondition for each qualification run (declared method): every row of a retained copilot-eval.json
matches the pre-registered identity table. Offline; no app import, no provider call, no network.

Per row: sha256 of tool_trace.initial_messages[0].content (FULL hex) and its length; sha256 of
json.dumps(initial_messages[1:], sort_keys=True) (the context, as g_precheck.py hashes it, compared in full);
sha256 of json.dumps(tool_schema, sort_keys=True); generation_options. Per report: golden_sha256, requested_model,
requested_flags, runs, planned_attempts (18 identities, each question x run_index 0-2) and one row per planned
identity. Prints source_sha (for the head-anchored `git diff --quiet <frozen head> <source_sha> -- backend .github`
validity rule) and, when runner.log sits next to the report, the system_fingerprint counts (reported, never a
validity condition).
Exit 0 = valid; exit 1 = any mismatch (the run is invalid: stop, record, apply no rule).

Usage: python run_validity.py LABEL=path/copilot-eval.json [...]
       python run_validity.py --control-prompt SHA256:CHARS LABEL=path [...]   (controls on retained runs only:
       swaps the expected system prompt so a run on another prompt can show every other identity row matching;
       never used for a qualification run)
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter

SYSTEM_PROMPT_SHA256 = "a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5"
SYSTEM_PROMPT_CHARS = 5289
CONTEXTS = {
    ("AAPL", "sales-gross-profit-2025"): "db033e5a13d4f0e5e88ba76137ea4f9a55fa9eb4535c248999c4e28dbae47509",
    ("TSLA", "sales-operating-income-2024"): "3babd16a34cf8c3d6492f6547e185943d4040e53bb9eccc8b25690e204ed16ec",
    ("MSFT", "sales-diluted-eps-2025"): "b552352b2af3c70f02a7f8773a06aa8df08e088e25a532af012f19879efc3023",
    ("BABA", "native-revenue-2026"): "6db10712e7803711a27ba122943566469a84e81efe71d97070df6f0496314004",
    ("BABA", "viewed-native-revenue-2025"): "be263a712053cf3687629b3c60816a79166a0062983ab1723d6a3c3d0ca72da3",
    ("ASML", "us-gaap-sales-net-income-2025"): "09e857dbd1b95645189b4f6aafe5befd89f475f0506c190958e3150cda5ca019",
}
TOOL_SCHEMA_SHA256 = "b69589739c353f6c2e6ec884028ebbfd3b130582f48200c8e821ca960dd6e638"
GENERATION_OPTIONS = {"max_tokens": 2400, "model": "deepseek-flash", "temperature": 0.2}
GOLDEN_SHA256 = "15f8e7f92f934a5b040d905e8f684896cb11b2309d41737bbb58d59d0127b3c0"
REQUESTED_MODEL = "deepseek-flash"
REQUESTED_FLAGS = {"COPILOT_MAX_TOKENS": 2400, "USE_STATEMENT_FINANCIALS": True}
RUNS = 3


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check(path):
    report = json.load(open(path, encoding="utf-8"))
    bad = []
    expected = {(t, q, i) for (t, q) in CONTEXTS for i in range(RUNS)}
    planned = {(p.get("ticker"), p.get("question_id"), p.get("run_index")) for p in report.get("planned_attempts") or []}
    for field, got, want in (("golden_sha256", report.get("golden_sha256"), GOLDEN_SHA256),
                             ("requested_model", report.get("requested_model"), REQUESTED_MODEL),
                             ("requested_flags", report.get("requested_flags"), REQUESTED_FLAGS),
                             ("runs", report.get("runs"), RUNS),
                             ("planned_attempts", (len(report.get("planned_attempts") or []), planned), (18, expected))):
        if got != want:
            bad.append(f"report {field}: {json.dumps(got, default=sorted)[:200]} != expected")
    seen = Counter()
    prompts = Counter()
    for row in report.get("results") or []:
        key = (row.get("ticker"), row.get("question_id"))
        seen[key + (row.get("run_index"),)] += 1
        where = f"{key[0]} {key[1]} d{row.get('run_index')}"
        trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), dict) else {}
        messages = trace.get("initial_messages") or []
        if not messages:
            bad.append(f"{where}: initial_messages missing")
            continue
        content = messages[0].get("content") if isinstance(messages[0], dict) else None
        prompts[(sha(content or ""), len(content or ""))] += 1
        if messages[0].get("role") != "system" or sha(content or "") != SYSTEM_PROMPT_SHA256 \
                or len(content or "") != SYSTEM_PROMPT_CHARS:
            bad.append(f"{where}: system prompt {sha(content or '')[:16]} / {len(content or '')} chars")
        if sha(json.dumps(messages[1:], sort_keys=True)) != CONTEXTS.get(key):
            bad.append(f"{where}: context {sha(json.dumps(messages[1:], sort_keys=True))[:16]}")
        schema = trace.get("tool_schema")
        if schema is None or sha(json.dumps(schema, sort_keys=True)) != TOOL_SCHEMA_SHA256:
            bad.append(f"{where}: tool schema")
        if trace.get("generation_options") != GENERATION_OPTIONS:
            bad.append(f"{where}: generation options {trace.get('generation_options')}")
    if set(seen) != expected or any(n != 1 for n in seen.values()):
        bad.append(f"rows: {sum(seen.values())} rows, identities {len(seen)}; expected one row per planned identity (18)")
    log = os.path.join(os.path.dirname(path), "runner.log")
    fingerprints = Counter(re.findall(r'"system_fingerprint": *"([^"]*)"', open(log, encoding="utf-8").read())) \
        if os.path.exists(log) else None
    return report, bad, prompts, fingerprints


if __name__ == "__main__":
    invalid = False
    args = sys.argv[1:]
    if args[:1] == ["--control-prompt"]:
        digest, chars = args[1].split(":")
        SYSTEM_PROMPT_SHA256, SYSTEM_PROMPT_CHARS = digest, int(chars)
        print(f"CONTROL: expected system prompt replaced by {digest[:16]}/{chars} chars (not a qualification check)")
        args = args[2:]
    for arg in args:
        label, path = arg.split("=", 1)
        report, bad, prompts, fingerprints = check(path)
        invalid |= bool(bad)
        print(f"{label}: {'VALID' if not bad else 'INVALID'}; rows {len(report.get('results') or [])}; "
              f"source_sha {report.get('source_sha')}; runtime {json.dumps((report.get('preparation') or {}).get('runtime'))}")
        print(f"  system prompts seen: {', '.join(f'{h[:16]}/{n} chars x{c}' for (h, n), c in prompts.items())}")
        print(f"  fingerprints (reported, not validity): {dict(fingerprints) if fingerprints is not None else 'no runner.log'}")
        for line in bad[:40]:
            print(f"  MISMATCH {line}")
        if len(bad) > 40:
            print(f"  ... {len(bad) - 40} more")
    sys.exit(1 if invalid else 0)
