"""DEEPSEEK-ERRORS.md §3 step 1: version 2's repair on its own, over DeepSeek's recorded failing first passes.

    cd backend && python -m evals.trend_depth.repair_replay --label step1-r1 --dry-run   # the cases; no call
    cd backend && python -m evals.trend_depth.repair_replay --label step1-r1              # two repairs a case

A case is a ``deepseek-flash`` first pass recorded under ``--sources`` (eval-v1, dev-v4 and dev-v3 by default): the
model's own output (a repaired record's ``first_pass_output``, else its ``output``) that version 2 would still send
to a repair after its code fixes (``generate.fix_first_pass``: retyping and auto-citation, then the gate with its
backstops, on the pack the arm reads). Each case goes ``--repeats`` times (default 2) through generate's own
version-2 repair (``generate.repair_or_mark``: the patch request, then the full repair if the patches are
unusable), through the real provider call, as the control arm ``deepseek-flash`` (the frozen prompt on packs/).
The user message is the one the first pass was sent, with no nonce, as the recorded first passes had none. dev-v3's
first passes ran an earlier prompt that no record keeps; they are repaired under the frozen one.

For each case and repeat it reports the repair's kind, calls, latency, tokens and cost, both as billed and warm (as
a repair sent seconds after its first pass bills: that first pass's whole prompt read from cache, the frozen
prompt's first attempt on the same pack giving its length), the gate's verdict on the repaired analysis, and how
many of the sentences that did not fail stayed byte for byte. A replay's own cache state differs from that: DeepSeek
may or may not still hold the recorded prompt, and a case's repeats may run at once (``--concurrency``), so neither
reads the other's, while a later case of the same company may read an earlier one's system prompt and pack. Each
row's cached tokens show which.

The dry run lists the cases and the most one run can send and bill (``ceiling``): two calls a repeat (the patch and
the full repair), each prompt read cold at one token per byte and each reply at the arm's ``max_tokens``, off-peak
and at DeepSeek's peak price (``PEAK``). A repeat interrupted between the two (a kill, a provider error) is resumed
with the full repair alone (``generate._repair_v2``), so a re-run adds no patch call.

Each repeat is written to ``runs/<label>/repair-replay/repeats/<source>__<TICKER>__<n>.json`` as soon as it
returns, and the paid patch call before any full repair is sent; the folder is a level deeper than any stage reads
a label's systems, so none takes a repeat for a generation. A repeat already written is kept; one holding a
provider error has its repair retried. The table and its summary go to ``runs/<label>/repair-replay/summary.json``.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import difflib
import hashlib
import json
import statistics
from typing import Any, Optional

from evals.trend_depth import generate
from evals.trend_depth.providers import ARMS, list_cost, max_tokens_for
from evals.trend_depth.records import quantile, unsettled, write_json

ARM = "deepseek-flash"
PEAK = 2.0  # DeepSeek's peak hours double every price (providers' price note for deepseek-flash)
SOURCES = ("eval-v1", "dev-v4", "dev-v3")
FOLDER = "repair-replay"
USAGE = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")


def _warm_prefixes(sources: list[str], prompt_sha: str) -> dict[str, int]:
    """Per ticker, the prompt tokens of a recorded first attempt on this prompt and pack: what a repair seconds after
    it would read from cache."""
    out: dict[str, int] = {}
    for source in sources:
        for path in sorted((generate.RUNS / source / ARM).glob("*.json")):
            record = json.loads(path.read_text())
            first = next((a for a in record.get("attempts", []) if a.get("attempt") == 0), None)
            if record.get("prompt_sha256") == prompt_sha and first and record.get("ticker") not in out:
                out[record["ticker"]] = int(first["input_tokens"])
    return out


def cases(sources: list[str], tickers: Optional[set[str]] = None) -> tuple[list[dict[str, Any]], list[str]]:
    """The recorded first passes version 2 would send to a repair, each as the record its repair starts from, and a
    line for each first pass it would not repair."""
    prompt_sha = hashlib.sha256(generate.system_prompt(ARM).encode()).hexdigest()
    warm = _warm_prefixes(sources, prompt_sha)
    found, notes = [], []
    for source in sources:
        for path in sorted((generate.RUNS / source / ARM).glob("*.json")):
            recorded = json.loads(path.read_text())
            ticker = recorded.get("ticker", path.stem)
            if not isinstance(recorded.get("output"), dict) or (tickers and ticker not in tickers):
                continue
            pack = generate.load_pack(ticker, ARM)
            record = {"ticker": ticker, "arm": ARM, "pipeline": "v2", "source": f"{source}/{ARM}/{ticker}",
                      "first_pass_prompt_sha256": recorded.get("prompt_sha256"), "prompt_sha256": prompt_sha,
                      "output": recorded.get("first_pass_output") or recorded["output"], "attempts": [],
                      "usage": {key: 0 for key in USAGE}, "latency_s": 0.0, "cost_usd": 0.0}
            generate.fix_first_pass(record, pack)
            if record["gate"]["passed"]:
                raw = "passes the gate as written" if record["raw_first_pass_gate"]["passed"] else "passes after the code fixes"
                notes.append(f"{source}/{ticker}: {raw}")
                continue
            found.append({"name": f"{source}__{ticker}", "record": record, "pack": pack, "warm_prefix": warm.get(ticker)})
    return found, notes


def untouched(first: dict[str, Any], repaired: dict[str, Any], failures: list[dict[str, Any]]) -> tuple[int, int]:
    """(kept, all): the sentences of ``first`` that did not fail, and how many of them ``repaired`` holds byte for
    byte, in their section and order."""
    failed = {(f["section"], f["sentence"].strip()) for f in failures}
    after = {s.get("key"): s.get("sentences", []) for s in repaired.get("sections", []) if isinstance(s, dict)}
    kept = total = 0
    for section in first.get("sections", []):
        old = [json.dumps(s, sort_keys=True) for s in section.get("sentences", [])]
        new = [json.dumps(s, sort_keys=True) for s in after.get(section.get("key"), [])]
        same = {i for tag, i1, i2, _, _ in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
                if tag == "equal" for i in range(i1, i2)}
        for i, sentence in enumerate(section.get("sentences", [])):
            if (section.get("key"), sentence["text"].strip()) not in failed:
                total += 1
                kept += i in same
    return kept, total


def measures(case: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """One repeat's repair: its kind, calls, latency, tokens, cost (billed, and warm when the prefix is known), the
    gate's verdict and the untouched sentences kept."""
    arm, prefix = ARMS[ARM], case["warm_prefix"]
    warm = None if prefix is None else round(sum(
        list_cost(arm, a["input_tokens"], min(a["input_tokens"], prefix), a["output_tokens"]) for a in record["attempts"]), 6)
    done = "repair_error" not in record and "repair_failed" not in record
    kept, total = untouched(case["record"]["output"], record["output"], case["record"]["gate"]["failures"]) if done else (0, 0)
    return {"repair_kind": record.get("repair_kind"), "calls": len(record["attempts"]), "latency_s": record["latency_s"],
            **{key: record["usage"][key] for key in USAGE}, "cost_usd": record["cost_usd"], "cost_warm_usd": warm,
            "gate_passed": done and record["gate"]["passed"], "failures_after": len(record["gate"]["failures"]) if done else None,
            "untouched_kept": [kept, total], "repair_failed": record.get("repair_failed"), "repair_error": record.get("repair_error")}


async def repair(case: dict[str, Any], n: int, label: str, semaphore: asyncio.Semaphore) -> dict[str, Any]:
    """Repeat ``n`` of a case: kept when already written, else its repair (retried when it holds a provider error)."""
    path = generate.RUNS / label / FOLDER / "repeats" / f"{case['name']}__{n}.json"
    existing = json.loads(path.read_text()) if path.exists() else None
    if existing and not unsettled(existing):
        return existing
    record = existing or {**copy.deepcopy(case["record"]), "repeat": n}
    pack, system = case["pack"], generate.system_prompt(ARM)
    async with semaphore:
        await generate.repair_or_mark(ARMS[ARM], system, generate.user_message(pack), record, pack,
                                      f"{label}/repair-replay/{case['name']}/{n}", checkpoint=lambda r: write_json(path, r))
    record["measures"] = measures(case, record)
    write_json(path, record)
    return record


def ceiling(found: list[dict[str, Any]], repeats: int) -> tuple[int, float]:
    """The most one run can send and bill, as (calls, USD off-peak): per repeat of each case, the patch request and the
    full repair, each prompt (the frozen system prompt and the repair message ``repair`` sends) read cold at one token
    per UTF-8 byte, the most a byte-level tokenizer makes, and each reply at the arm's ``max_tokens``. A re-run that
    retries a provider error sends more; a reply cut off at ``max_tokens`` is one."""
    arm = ARMS[ARM]
    system, cap = generate.system_prompt(ARM), max_tokens_for(arm)
    cost = 0.0
    for case in found:
        record, pack = case["record"], case["pack"]
        user = generate.user_message(pack)
        for patch in (True, False):
            message = generate.repair_message_v2(user, record["output"], record["gate"]["failures"], pack, patch=patch)
            cost += list_cost(arm, len(system.encode()) + len(message.encode()), 0, cap)
    return 2 * len(found) * repeats, round(cost * repeats, 6)


def _percentile(values: list[float], share: float) -> Optional[float]:
    """The report's latency quantile (``records.quantile``: linear between the two nearest ranks), so a repair's p50 and
    p90 are on the basis of §3's latency rows and baselines; a nearest rank read 1.0 s as the median of 1.0 and 2.0."""
    value = quantile(values, share)
    return None if value is None else round(value, 3)


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The repeats pooled: how many passed, fell back, kept every untouched sentence; latency p50 and p90; mean cost."""
    done = [r for r in rows if not r["repair_error"]]
    latency = [r["latency_s"] for r in done]
    return {"repeats": len(rows), "provider_errors": len(rows) - len(done),
            "gate_passed": sum(1 for r in done if r["gate_passed"]),
            "repair_failed": sum(1 for r in done if r["repair_failed"]),
            "full_repairs": sum(1 for r in done if r["repair_kind"] == "full"),
            "untouched_all_kept": sum(1 for r in done if not r["repair_failed"] and r["untouched_kept"][0] == r["untouched_kept"][1]),
            "latency_p50_s": _percentile(latency, 0.5), "latency_p90_s": _percentile(latency, 0.9),
            "cost_mean_usd": round(statistics.fmean(r["cost_usd"] for r in done), 6) if done else None,
            "cost_warm_mean_usd": round(statistics.fmean(r["cost_warm_usd"] for r in done), 6)
            if done and all(r["cost_warm_usd"] is not None for r in done) else None}


def table(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["case                     n  kind   calls  latency  in/cached/out tokens     cost      warm     gate  untouched"]
    for r in rows:
        warm = "n/a" if r["cost_warm_usd"] is None else f"${r['cost_warm_usd']:.5f}"
        gate = "error" if r["repair_error"] else ("FAILED" if r["repair_failed"] else ("pass" if r["gate_passed"] else
                                                                                      f"fail {r['failures_after']}"))
        lines.append(f"{r['case']:24} {r['repeat']}  {str(r['repair_kind']):6} {r['calls']:5}  {r['latency_s']:6.2f}s  "
                     f"{r['input_tokens']:6}/{r['cached_input_tokens']:6}/{r['output_tokens']:5}  ${r['cost_usd']:.5f}  "
                     f"{warm:>8}  {gate:6}  {r['untouched_kept'][0]}/{r['untouched_kept'][1]}")
    return lines


async def replay(label: str, found: list[dict[str, Any]], repeats: int, concurrency: int) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(concurrency)
    jobs = [(case, n) for case in found for n in range(1, repeats + 1)]
    records = await asyncio.gather(*(repair(case, n, label, semaphore) for case, n in jobs))
    return [{"case": case["name"], "repeat": n, **record["measures"]} for (case, n), record in zip(jobs, records)]


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True, help="the run's label: results go under runs/<label>/repair-replay/")
    parser.add_argument("--sources", default=",".join(SOURCES), help="labels whose deepseek-flash first passes are replayed")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--tickers", default="", help="comma-separated: only these companies")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="list the cases and send nothing")
    args = parser.parse_args(argv)
    found, notes = cases(args.sources.split(","), set(args.tickers.split(",")) if args.tickers else None)
    print("\n".join(f"  not repaired: {note}" for note in notes))
    for case in found:
        failures = case["record"]["gate"]["failures"]
        print(f"  case {case['name']}: {len(failures)} failure(s): " + "; ".join(f["failure"] for f in failures)[:300])
    calls, most = ceiling(found, args.repeats)
    print(f"{len(found)} cases, {len(found) * args.repeats} repairs, at most {calls} calls and USD {most:.2f} off-peak "
          f"(USD {most * PEAK:.2f} at peak): every prompt read cold, every patch falling back, every reply at max_tokens")
    if args.dry_run:
        return
    rows = asyncio.run(replay(args.label, found, args.repeats, args.concurrency))
    result = {"label": args.label, "sources": args.sources.split(","), "repeats": args.repeats,
              "summary": summary(rows), "rows": rows, "not_repaired": notes}
    write_json(generate.RUNS / args.label / FOLDER / "summary.json", result)
    print("\n".join(table(rows)))
    print(json.dumps(result["summary"], indent=1))


if __name__ == "__main__":
    main()
