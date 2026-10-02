"""Cost of a copilot-eval run from EVERY provider call logged in its runner.log (`ai_call {json}` lines).

Unlike copilot_cost.py (which sums usage attached to the eval's per-row service_events, and so misses the
provider calls behind withheld/errored rows), this counts all logged calls. Rates are llm_pricing's
deepseek-flash off-peak USD per 1M tokens (cache hit 0.003, cache miss 0.15, completion 0.60), doubled for
calls the log marks `"peak": true`. Also prints the sum of the log's own `estimated_cost_usd` as a cross-check.
Usage: python copilot_cost_runnerlog.py <runner.log> [...]
"""
import json
import sys

H, M, O = 0.003, 0.15, 0.60
for path in sys.argv[1:]:
    calls = peak = unknown = 0
    cost = est = 0.0
    hit = miss = comp = 0
    for line in open(path, encoding="utf-8"):
        if not line.startswith("ai_call "):
            continue
        ev = json.loads(line[len("ai_call "):])
        calls += 1
        u = ev.get("usage") or {}
        if u.get("cache_hit_tokens") is None or u.get("completion_tokens") is None:
            unknown += 1
            continue
        mult = 2 if ev.get("peak") else 1
        peak += 1 if ev.get("peak") else 0
        hit += u["cache_hit_tokens"]; miss += u["cache_miss_tokens"]; comp += u["completion_tokens"]
        cost += mult * (u["cache_hit_tokens"] * H + u["cache_miss_tokens"] * M + u["completion_tokens"] * O) / 1e6
        est += ev.get("estimated_cost_usd") or 0.0
    print(path.split("/")[-2], f"calls {calls} peak {peak} unknown {unknown} hit {hit} miss {miss} completion {comp}",
          f"usd {round(cost, 6)} log_estimate {round(est, 6)}")
