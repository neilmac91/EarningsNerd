"""Re-derive the posted custody, telemetry and outcome figures from preserved archive zips.

Offline: reads the zips with zipfile (nothing is extracted or executed), needs no repository
checkout, no network and no model calls. Run it on the folder preserve_artifacts.py filled:

    python3 -I recompute_archives.py /path/to/evidence-dir

For every manifest.json entry it finds as `<artifact_name>-<artifact_id>.zip`, it checks the zip's
SHA-256 against the manifest and the member hashes in members.tsv (when listed there). For the four
prompt-candidate archives it then recomputes the figures posted on #1029 (comments 5965022094,
5965051343, 5965077411, 5965107573; handback 5965113700) and compares them with EXPECTED:
- eval-report: summary.baseline counts, incurred provider usage (summary and the per-result sum),
  cost from tokens, and ci-execution.txt source_sha;
- copilot-fidelity: summary counts, accepted, withheld reasons, the system prompt hash on every row,
  per-question tool-use strings, and the runner.log `ai_call` tally (calls, unknown usage, peak,
  tokens, fingerprints, cost).

Cost uses the deepseek-flash rates pinned at the run's merge ref 3a5c5894
(backend/app/services/llm_pricing.py: 0.003 cache hit, 0.15 cache miss, 0.60 output, USD per 1M
tokens; peak calls x2.0), summed over tokens and rounded once to 6 decimals, as the posted figures
were. Archives missing from the folder are listed, not failed. Exit 0 when every present archive
matches, 1 otherwise.
"""
import hashlib
import json
import sys
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATES = (Decimal("0.003"), Decimal("0.15"), Decimal("0.60"))  # cache hit, cache miss, output; USD per 1M
PEAK = Decimal("2.0")
PROMPT_SHA256 = "a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5"
QUESTIONS = [("AAPL", "sales-gross-profit-2025"), ("TSLA", "sales-operating-income-2024"),
             ("MSFT", "sales-diluted-eps-2025"), ("BABA", "native-revenue-2026"),
             ("BABA", "viewed-native-revenue-2025"), ("ASML", "us-gaap-sales-net-income-2025")]
SOURCE_SHA = "3a5c5894360ece236b65261ae1d97bcf944b59d4"
EXPECTED = {
    "eval-report-37092291865": {
        "source_sha": SOURCE_SHA, "n": 70, "scored": 70, "errors": 0, "retried": 0, "pass_rate": 1.0,
        "calls": 70, "unknown_calls": 0, "prompt": 2755570, "hit": 2741494, "miss": 14076,
        "completion": 275109, "per_result_sum_equals_summary": True, "cost_usd": "0.175401"},
    "copilot-fidelity-37092951315": {
        "source_sha": SOURCE_SHA, "expected": 18, "completed": 18, "scored": 17, "errors": 1, "accepted": False,
        "withheld": ["AAPL sales-gross-profit-2025 d0: Unsupported prose quotation: quotation_not_in_source"],
        "prompt_rows": 18, "tools": "TTT TTT TTT --- --T TTT", "calls": 31, "unknown": 0, "peak": 0,
        "hit": 782976, "miss": 184141, "completion": 4008, "fingerprints": {"aeb56401ca74e127821c4f9126dcb669": 31},
        "cost_usd": "0.032375"},
    "copilot-fidelity-37093200860": {
        "source_sha": SOURCE_SHA, "expected": 18, "completed": 18, "scored": 18, "errors": 0, "accepted": True,
        "withheld": [], "prompt_rows": 18, "tools": "TTT TTT TTT -T- T-T TTT", "calls": 33, "unknown": 0, "peak": 0,
        "hit": 1028224, "miss": 6599, "completion": 4286, "fingerprints": {"aeb56401ca74e127821c4f9126dcb669": 33},
        "cost_usd": "0.006646"},
    "copilot-fidelity-37093395884": {
        "source_sha": SOURCE_SHA, "expected": 18, "completed": 18, "scored": 18, "errors": 0, "accepted": True,
        "withheld": [], "prompt_rows": 18, "tools": "TTT TTT TTT --- TTT TTT", "calls": 33, "unknown": 0, "peak": 0,
        "hit": 1034880, "miss": 6549, "completion": 4444, "fingerprints": {"aeb56401ca74e127821c4f9126dcb669": 33},
        "cost_usd": "0.006753"},
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cost(hit: int, miss: int, out: int, peak: bool = False) -> Decimal:
    total = (Decimal(hit) * RATES[0] + Decimal(miss) * RATES[1] + Decimal(out) * RATES[2]) / Decimal(1_000_000)
    return total * (PEAK if peak else 1)


def eval_report(z: zipfile.ZipFile) -> dict:
    name = next(n for n in z.namelist() if n.startswith("eval_") and n.endswith(".json"))
    data = json.loads(z.read(name))
    base = data["summary"]["baseline"]
    usage = base["incurred_provider_usage"]
    per = Counter()
    for row in data["results"]:
        u = row.get("incurred_provider_usage") or {}
        per["calls"] += u.get("calls") or 0
        per["unknown_calls"] += u.get("unknown_calls") or 0
        for key in ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens"):
            per[key] += u.get(key) or 0
    summary = {"calls": usage["calls"], "unknown_calls": usage["unknown_calls"], "prompt_tokens": usage["prompt_tokens"],
               "cache_hit_tokens": usage["cache_hit_tokens"], "cache_miss_tokens": usage["cache_miss_tokens"],
               "completion_tokens": usage["completion_tokens"]}
    source = dict(line.split("=", 1) for line in z.read("ci-execution.txt").decode().splitlines() if "=" in line)
    return {"source_sha": source.get("source_sha"), "n": base["n"], "scored": base["scored"], "errors": base["errors"],
            "retried": base["retried"], "pass_rate": base["pass_rate"], "calls": usage["calls"],
            "unknown_calls": usage["unknown_calls"], "prompt": usage["prompt_tokens"], "hit": usage["cache_hit_tokens"],
            "miss": usage["cache_miss_tokens"], "completion": usage["completion_tokens"],
            "per_result_sum_equals_summary": dict(per) == summary,
            "cost_usd": str(round(cost(usage["cache_hit_tokens"], usage["cache_miss_tokens"],
                                       usage["completion_tokens"]), 6))}


def copilot(z: zipfile.ZipFile) -> dict:
    data = json.loads(z.read("copilot-eval.json"))
    rows = data["results"]
    withheld = [f'{r["ticker"]} {r["question_id"]} d{r["run_index"]}: {(r.get("error") or {}).get("withheld_reason")}'
                for r in rows if r.get("error")]
    prompts = Counter(sha256_bytes(((r.get("tool_trace") or {}).get("initial_messages") or [{}])[0]
                                   .get("content", "").encode()) for r in rows)
    draws = {}
    for r in sorted(rows, key=lambda r: r["run_index"]):
        draws.setdefault((r["ticker"], r["question_id"]), []).append(
            "T" if (r.get("tool_trace") or {}).get("tool_results") else "-")
    tally, fingerprints, total = Counter(), Counter(), Decimal(0)
    for line in z.read("runner.log").decode().splitlines():
        if not line.startswith("ai_call "):
            continue
        call = json.loads(line[len("ai_call "):])
        tally["calls"] += 1
        tally["peak"] += call.get("peak") is True
        fingerprints[call.get("system_fingerprint")] += 1
        u = call.get("usage") or {}
        if all(u.get(k) is None for k in ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens")):
            tally["unknown"] += 1
            continue
        tally["hit"] += u.get("cache_hit_tokens") or 0
        tally["miss"] += u.get("cache_miss_tokens") or 0
        tally["completion"] += u.get("completion_tokens") or 0
        total += cost(u.get("cache_hit_tokens") or 0, u.get("cache_miss_tokens") or 0,
                      u.get("completion_tokens") or 0, call.get("peak") is True)
    s = data["summary"]
    return {"source_sha": data.get("source_sha"), "expected": s["expected"], "completed": s["completed"],
            "scored": s["scored"], "errors": s["errors"], "accepted": data.get("accepted"), "withheld": withheld,
            "prompt_rows": prompts.get(PROMPT_SHA256, 0),
            "tools": " ".join("".join(draws.get(q, [])) for q in QUESTIONS),
            "calls": tally["calls"], "unknown": tally["unknown"], "peak": tally["peak"], "hit": tally["hit"],
            "miss": tally["miss"], "completion": tally["completion"], "fingerprints": dict(fingerprints),
            "cost_usd": str(round(total, 6))}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    folder = Path(sys.argv[1]).expanduser().resolve()
    manifest = json.loads((HERE / "manifest.json").read_text())
    members = {}
    for line in (HERE / "members.tsv").read_text().splitlines()[1:]:
        artifact, member, size, digest = line.split("\t")
        members.setdefault(artifact, {})[member] = (int(size), digest)
    failures, missing = 0, []
    for item in manifest["artifacts"]:
        path = folder / f"{item['artifact_name']}-{item['artifact_id']}.zip"
        if not path.exists():
            missing.append(path.name)
            continue
        problems = []
        if sha256_bytes(path.read_bytes()) != item["sha256"]:
            problems.append("zip sha256 differs from manifest")
        with zipfile.ZipFile(path) as z:
            for member, (size, digest) in members.get(item["artifact_name"], {}).items():
                body = z.read(member)
                if len(body) != size or sha256_bytes(body) != digest:
                    problems.append(f"member {member} differs from members.tsv")
            expected = EXPECTED.get(item["artifact_name"])
            if expected:
                actual = eval_report(z) if item["artifact_name"].startswith("eval-report") else copilot(z)
                problems += [f"{k}: expected {expected[k]!r}, got {actual.get(k)!r}"
                             for k in expected if actual.get(k) != expected[k]]
        failures += bool(problems)
        scope = "figures and hashes" if expected else "hashes"
        print(f"{'OK ' if not problems else 'BAD'} {path.name} ({scope})")
        for problem in problems:
            print(f"    {problem}")
    for name in missing:
        print(f"--  {name} not in {folder}")
    present = len(manifest["artifacts"]) - len(missing)
    print(f"{present - failures}/{present} present archives match; {len(missing)} not present")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
