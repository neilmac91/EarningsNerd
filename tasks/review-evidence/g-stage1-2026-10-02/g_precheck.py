"""G stage-1 validity precondition, checked offline on a retained copilot-eval artifact.
Hashes per #1036 design: sha256 hex prefixes of UTF-8 text; JSON via json.dumps(..., sort_keys=True)."""
import hashlib, json, sys
from collections import defaultdict
def h(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def hj(o): return h(json.dumps(o, sort_keys=True))
for path in sys.argv[1:]:
    d = json.load(open(path))
    sysp, ctx, tools, gen, fps = defaultdict(int), defaultdict(set), defaultdict(int), defaultdict(int), defaultdict(int)
    for r in d['results']:
        tt = r.get('tool_trace') or {}
        im = tt.get('initial_messages') or []
        if not im: sysp['<missing>'] += 1; continue
        sysp[h(im[0]['content'])[:8]] += 1
        ctx[(r['ticker'], r['question_id'])].add(hj(im[1:])[:12])
        tools[hj(tt.get('tool_schema'))[:8] if tt.get('tool_schema') is not None else '<missing>'] += 1
        gen[json.dumps(tt.get('generation_options'), sort_keys=True)] += 1
        for ev in tt.get('service_events') or []:
            if isinstance(ev, dict):
                fp = ev.get('system_fingerprint') or (ev.get('usage') or {}).get('system_fingerprint')
                if fp: fps[fp[:8]] += 1
    print(path.split('/')[-2])
    print('  system_prompt', dict(sysp))
    print('  context', {f'{k[0]} {k[1]}': sorted(v) for k, v in ctx.items()})
    print('  tool_schema', dict(tools))
    print('  generation_options', dict(gen))
    print('  fingerprints', dict(fps))
