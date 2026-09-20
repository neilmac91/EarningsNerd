"""Per-run readout for several judged.json files (same judge/contract), with per-configuration ranges.
usage: compare_runs.py LABEL=path [LABEL=path ...]   (labels like 'o1','o2','n1','n2', 'e3c1', 'e3c2')"""
import json,re,statistics,sys,collections
G=re.compile(r"^\s*(G\d)\b")
def complete(j): return isinstance(j,dict) and not j.get('error') and j.get('input_complete') is True and j.get('verdict') in ('PASS','FAIL') and j.get('contract_version')==2
rows=[]
for arg in sys.argv[1:]:
    label,path=arg.split('=',1); d=json.load(open(path)); r=d['results']; comp=[x for x in r if complete(x.get('judge'))]
    neg=sum(x['judge']['verdict']=='FAIL' for x in comp); gc=collections.Counter(c for x in comp for c in {m.group(1) for g in x['judge']['gate_failures'] for m in [G.match(g)] if m})
    dims={k:statistics.mean(x['judge']['dimensions'][k] for x in comp) for k in ('faithfulness','insight','clarity','specificity')}
    flagged=sum(1 for x in comp if (x.get('attribution_audit') or {}).get('unverified'))
    g4=[x for x in comp if 'G4' in {m.group(1) for g in x['judge']['gate_failures'] for m in [G.match(g)] if m}]
    both=sum(1 for x in g4 if (x.get('attribution_audit') or {}).get('unverified'))
    rows.append({'label':label,'judge':d['harness'].get('judge'),'contract':d['harness'].get('judge_contract_version'),'source':d['harness'].get('source_sha'),'verify':d['harness'].get('ai_attribution_verify'),'attempts':len(r),'complete':len(comp),'negative':neg,'neg_rate':100*neg/len(comp) if comp else float('nan'),'G2':gc.get('G2',0),'G3':gc.get('G3',0),'G4':gc.get('G4',0),'G5':gc.get('G5',0),**{k:round(v,3) for k,v in dims.items()},'flagged':flagged,'G4_and_flagged':both})
print("| run | judge | contract | source | verify | complete | negative | neg% | G2 | G3 | G4 | G5 | faith | insight | clarity | spec | flagged | G4∩flag |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for x in rows: print(f"| {x['label']} | {x['judge']} | {x['contract']} | {x['source'][:10]} | {x['verify']} | {x['complete']}/{x['attempts']} | {x['negative']} | {x['neg_rate']:.1f} | {x['G2']} | {x['G3']} | {x['G4']} | {x['G5']} | {x['faithfulness']} | {x['insight']} | {x['clarity']} | {x['specificity']} | {x['flagged']} | {x['G4_and_flagged']} |")
groups=collections.defaultdict(list)
for x in rows: groups[re.sub(r'\d+$','',x['label'])].append(x)
print("\nPer-configuration ranges (min–max across that configuration's independently generated runs; descriptive only):")
for g,xs in groups.items():
    if len(xs)<2: print(f"  {g}: single run ({xs[0]['label']}) — no range"); continue
    for k in ('neg_rate','G4','G5','G3','G2','faithfulness'):
        vals=[x[k] for x in xs]; print(f"  {g} {k}: {min(vals):.1f}–{max(vals):.1f} (span {max(vals)-min(vals):.1f}) over {[x['label'] for x in xs]}")
