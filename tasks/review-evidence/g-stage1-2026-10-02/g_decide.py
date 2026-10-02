"""G stage 1 (#1036) counter: tool-using draws per question, 2-of-3 question-run rule, 20-F vs 10-K.
A draw calls a tool when its tool_trace.tool_results is non-empty (model tool calls; the server
repair lookup is not recorded there). Usage: g_decide.py LABEL=path/copilot-eval.json ..."""
import json, sys
from collections import defaultdict
TWENTY_F = {('BABA', 'native-revenue-2026'), ('BABA', 'viewed-native-revenue-2025'), ('ASML', 'us-gaap-sales-net-income-2025')}
for arg in sys.argv[1:]:
    label, path = arg.split('=', 1)
    d = json.load(open(path))
    draws = defaultdict(list)
    for r in d['results']:
        draws[(r['ticker'], r['question_id'])].append(bool((r.get('tool_trace') or {}).get('tool_results')))
    f20 = [k for k in draws if k in TWENTY_F]; k10 = [k for k in draws if k not in TWENTY_F]
    qr = {k: sum(v) >= 2 for k, v in draws.items()}
    print(f"{label}: 20-F question-runs tool-using {sum(qr[k] for k in f20)}/{len(f20)}; 10-K {sum(qr[k] for k in k10)}/{len(k10)}; "
          f"draws with tools {sum(sum(v) for v in draws.values())}/{sum(len(v) for v in draws.values())}")
    for k in sorted(draws): print(f"   {k[0]:5} {k[1]:32} draws={''.join('T' if x else '-' for x in draws[k])} tool-using={qr[k]}")
