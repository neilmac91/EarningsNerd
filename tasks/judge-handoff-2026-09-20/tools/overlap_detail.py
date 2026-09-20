import json,re,sys
d=json.load(open(sys.argv[1])); r=[x for x in d['results'] if isinstance(x.get('judge'),dict) and not x['judge'].get('error') and x['judge'].get('input_complete') is True and x['judge'].get('verdict') in ('PASS','FAIL')]; G=re.compile(r"^\s*(G\d)\b"); N=len(r)
def codes(j): return {m.group(1) for g in (j.get('gate_failures') or []) for m in [G.match(str(g))] if m}
key=lambda x:(x['ticker'],x['filing_type'],x['run'])
g4={key(x) for x in r if 'G4' in codes(x['judge'])}
flag={key(x) for x in r if (x.get('attribution_audit') or {}).get('unverified')}
ns={key(x) for x in r if any(v=='not_stated' for v in ((x.get('attribution_audit') or {}).get('verdicts') or {}).values())}
print("PRIMARY (as specified): nonempty attribution_audit.unverified vs Fable G4 (attempt level, complete verdicts, n=%d)"%N)
print("  G4=%d flagged=%d both=%d G4-only=%d flagged-only=%d neither=%d" % (len(g4),len(flag),len(g4&flag),len(g4-flag),len(flag-g4),N-len(g4|flag)))
print("SECONDARY (labelled): verifier model verdict 'not_stated' on >=1 clause vs Fable G4")
print("  G4=%d not_stated=%d both=%d G4-only=%d not_stated-only=%d" % (len(g4),len(ns),len(g4&ns),len(g4-ns),len(ns-g4)))
print("  not_stated attempts:", sorted(ns)); print("  not_stated & G4:", sorted(ns&g4)); print("  not_stated without G4:", sorted(ns-g4))
print("\n== Attempts in BOTH sets: flagged clauses (verifier) and the judge's G4 reasons, side by side. No claim that they are the same clause.")
for x in sorted([x for x in r if key(x) in (g4&flag)], key=key):
    print("\n* %s %s run%s verdict=%s" % (key(x)+(x['judge']['verdict'],)))
    for u in x['attribution_audit']['unverified']:
        print("   VERIFIER flagged: slot=%s | %s | %s | model verdict=%s" % (u.get('slot'),u.get('connective'),(u.get('clause') or '')[:220], (x['attribution_audit'].get('verdicts') or {}).get(u.get('slot'))))
    for g in x['judge']['gate_failures']:
        if G.match(g).group(1)=='G4': print("   JUDGE G4:", g)
print("\n== Flagged-but-no-G4: flagged clauses and the judge's full verdict")
for x in sorted([x for x in r if key(x) in (flag-g4)], key=key):
    print("\n* %s %s run%s verdict=%s gates=%s" % (key(x)+(x['judge']['verdict'], sorted(codes(x['judge'])))))
    for u in x['attribution_audit']['unverified']:
        print("   VERIFIER flagged: slot=%s | %s | %s | model verdict=%s" % (u.get('slot'),u.get('connective'),(u.get('clause') or '')[:220], (x['attribution_audit'].get('verdicts') or {}).get(u.get('slot'))))
    for g in x['judge']['gate_failures']: print("   JUDGE:", g)
