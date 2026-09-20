"""Summarize a judged.json: counts, gate attempt counts, dimension means, every raw reason, G4/verifier overlap."""
import json, sys, re, statistics, collections
p = sys.argv[1]; d = json.load(open(p)); r = d['results']; h = d['harness']; js = d['judged_summary']
G = re.compile(r"^\s*(G\d)\b")
def codes(j): return {m.group(1) for g in (j.get('gate_failures') or []) for m in [G.match(str(g))] if m}
def complete(j): return isinstance(j, dict) and not j.get('error') and j.get('input_complete') is True and j.get('verdict') in ('PASS','FAIL')
print("== harness: judge=%s contract=%s source_sha=%s generator=%s golden=%s verify=%s gate=%s judged_at=%s" % (
    h.get('judge'), h.get('judge_contract_version'), h.get('source_sha'), h.get('model'), h.get('golden_set_sha256'),
    h.get('ai_attribution_verify'), h.get('ai_attribution_gate'), d.get('judged_at')))
print("== judged_summary:", json.dumps(js))
cv = collections.Counter(j.get('contract_version') for x in r if isinstance(j:=x.get('judge'), dict))
print("== per-verdict contract_version:", dict(cv))
comp = [x for x in r if complete(x.get('judge'))]
neg = [x for x in comp if x['judge']['verdict']=='FAIL']
print("== complete=%d negative=%d (%.1f%%)" % (len(comp), len(neg), 100*len(neg)/len(comp) if comp else 0))
gc = collections.Counter(c for x in comp for c in codes(x['judge']))
print("== gate attempt counts (complete only):", {g: gc.get(g,0) for g in ('G2','G3','G4','G5')})
for dim in ('faithfulness','insight','clarity','specificity'):
    vals = [x['judge']['dimensions'][dim] for x in comp if isinstance(x['judge'].get('dimensions'),dict) and dim in x['judge']['dimensions'] and isinstance(x['judge']['dimensions'][dim],(int,float))]
    print("   mean %s = %.3f (n=%d)" % (dim, statistics.mean(vals) if vals else float('nan'), len(vals)))
print("== errors / incomplete:")
errs = [x for x in r if isinstance(x.get('judge'), dict) and not complete(x['judge'])]
notj = [x for x in r if x.get('judge') is None]
print("   judge None (not judgeable / not judged):", [(x['ticker'],x['filing_type'],x['run']) for x in notj] or "none")
for x in errs: print("   ERROR", x['ticker'], x['filing_type'], x['run'], "verdict=", x['judge'].get('verdict'), "input_complete=", x['judge'].get('input_complete'), "lengths=", x['judge'].get('input_lengths'), "error=", repr(x['judge'].get('error')))
if not errs: print("   none")
print("== input lengths (complete): excerpt max=%s summary max=%s xbrl max=%s" % tuple(max((x['judge']['input_lengths'][k] for x in comp), default=None) for k in ('excerpt_chars','summary_chars','xbrl_chars')))
print("== EVERY complete verdict with raw gate_failures:")
for x in sorted(comp, key=lambda x:(x['ticker'],x['filing_type'],x['run'])):
    j = x['judge']; print("  %s %s run%s %s dims=%s mean=%s" % (x['ticker'], x['filing_type'], x['run'], j['verdict'], j.get('dimensions'), j.get('mean_dimension')))
    for g in j.get('gate_failures') or []: print("      -", g)
print("== G4 vs attribution_audit.unverified overlap (attempt-level; complete verdicts only):")
g4 = [x for x in comp if 'G4' in codes(x['judge'])]
flagged = [x for x in comp if isinstance(x.get('attribution_audit'), dict) and x['attribution_audit'].get('unverified')]
fid = {(x['ticker'],x['filing_type'],x['run']) for x in flagged}; gid = {(x['ticker'],x['filing_type'],x['run']) for x in g4}
print("   complete=%d  G4=%d  nonempty_unverified=%d  both=%d  G4_without_flag=%d  flag_without_G4=%d" % (len(comp), len(g4), len(flagged), len(gid&fid), len(gid-fid), len(fid-gid)))
print("   audit armed:", collections.Counter((x.get('attribution_audit') or {}).get('armed') for x in r), "decider:", collections.Counter((x.get('attribution_audit') or {}).get('decider') for x in r), "audit None:", sum(1 for x in r if x.get('attribution_audit') is None))
print("   G4 attempts WITH nonempty unverified:", sorted(gid&fid))
print("   G4 attempts WITHOUT any flagged clause (full reasons):")
for x in sorted(g4, key=lambda x:(x['ticker'],x['filing_type'],x['run'])):
    if (x['ticker'],x['filing_type'],x['run']) in fid: continue
    print("   * %s %s run%s audit=%s" % (x['ticker'], x['filing_type'], x['run'], json.dumps(x.get('attribution_audit'))[:200]))
    for g in x['judge']['gate_failures']: print("        -", g)
print("   flagged-but-no-G4 attempts:", sorted(fid-gid))
