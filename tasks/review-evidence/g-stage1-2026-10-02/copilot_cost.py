"""Off-peak cost of a copilot-eval run from its retained per-call usage (tokens x llm_pricing deepseek-flash)."""
import json, sys
H, M, O = 0.003, 0.15, 0.60
for path in sys.argv[1:]:
    d = json.load(open(path))
    calls = unknown = 0; cost = 0.0
    for r in d["results"]:
        for ev in (r.get("tool_trace") or {}).get("service_events") or []:
            u = ev.get("usage") if isinstance(ev, dict) else None
            if not u: continue
            calls += 1
            if u.get("cache_hit_tokens") is None or u.get("completion_tokens") is None: unknown += 1; continue
            cost += (u["cache_hit_tokens"] * H + u["cache_miss_tokens"] * M + u["completion_tokens"] * O) / 1e6
    print(path.split("/")[-2], "calls", calls, "unknown", unknown, "usd", round(cost, 6))
