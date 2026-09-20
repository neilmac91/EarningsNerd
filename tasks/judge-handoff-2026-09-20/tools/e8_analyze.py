"""E8 readout: per condition/corpus (n1, n2, o1, o2) main verdicts (reused o mains + new n slot verdicts),
duplicate agreement, completion counts, errors. Operator-only; reads slot outputs and the private map."""
import json,re,statistics,collections,sys
from pathlib import Path
E=Path(sys.argv[1]); G=re.compile(r"^\s*(G\d)\b")
def complete(j): return isinstance(j,dict) and not j.get('error') and j.get('input_complete') is True and j.get('verdict') in ('PASS','FAIL') and j.get('contract_version')==2
def codes(j): return {m.group(1) for g in (j.get('gate_failures') or []) for m in [G.match(str(g))] if m}
idx=json.loads((E/'e8-execution-index.json').read_text()); reuse={ (e['corpus'],tuple(e['identity'])):e for e in json.loads((E/'e8-control-main-reuse-2026-09-19.json').read_text())['main_verdicts']}
judgedE2={1:json.loads((E.parent/'judged-e2/judged.json').read_text()),2:json.loads((E.parent/'judged-e2c2/judged.json').read_text())}
o_rows={c:{(r['ticker'],r['filing_type'],r['run']):r['judge'] for r in judgedE2[c]['results']} for c in judgedE2}
def slot_verdict(p):
    jf=E/'slots'/p['slot']/'judged.json'
    if not jf.exists(): return None,'missing'
    d=json.loads(jf.read_text()); j=d['results'][0].get('judge'); return j,('complete' if complete(j) else 'error')
mains=collections.defaultdict(dict); status=collections.Counter(); errors=[]
for p in idx['reused_main_slots']:
    k=p['identity']; j=o_rows[p['corpus']][(k['ticker'],k['filing_type'],k['run'])]; mains[(p['condition'],p['corpus'])][(k['ticker'],k['filing_type'],k['run'])]=j; status['reused_o_main']+=1
dups=[]
for p in idx['packets']:
    k=p['identity']; j,st=slot_verdict(p)
    if p['slot_kind']=='main':
        status['n_main_'+st]+=1
        if st=='complete': mains[(p['condition'],p['corpus'])][(k['ticker'],k['filing_type'],k['run'])]=j
        elif st=='error': errors.append((p['slot'],k,j.get('error')))
    else:
        status['dup_'+st]+=1
        main_j=mains.get((p['condition'],p['corpus']),{}).get((k['ticker'],k['filing_type'],k['run']))
        dups.append({'slot':p['slot'],'cond':p['condition'],'corpus':p['corpus'],'identity':(k['ticker'],k['filing_type'],k['run']),'dup_status':st,'dup':j,'main':main_j})
        if st=='error': errors.append((p['slot'],k,j.get('error')))
print("== completion:",dict(status)); print("   mains complete:",sum(len(v) for v in mains.values()),"/ 280 | duplicates complete:",sum(1 for d in dups if d['dup_status']=='complete'),"/ 20")
print("== errors:",errors or 'none')
print("\n== per condition/corpus mains (complete verdicts only):")
print("| cell | complete | negative | neg% | G2 | G3 | G4 | G5 | faith | insight | clarity | spec |"); print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for cell in sorted(mains):
    vs=[j for j in mains[cell].values() if complete(j)]; n=len(vs); neg=sum(j['verdict']=='FAIL' for j in vs); gc=collections.Counter(c for j in vs for c in codes(j))
    dims={k:statistics.mean(j['dimensions'][k] for j in vs) if vs else float('nan') for k in ('faithfulness','insight','clarity','specificity')}
    print(f"| {cell[0]}{cell[1]} | {n}/70 | {neg} | {100*neg/n if n else float('nan'):.1f} | {gc.get('G2',0)} | {gc.get('G3',0)} | {gc.get('G4',0)} | {gc.get('G5',0)} | {dims['faithfulness']:.3f} | {dims['insight']:.3f} | {dims['clarity']:.3f} | {dims['specificity']:.3f} |")
print("\n== duplicate panel (second judgment vs main; repeatability only):")
agree=collections.Counter()
for d in dups:
    if d['dup_status']!='complete' or not complete(d['main']): print(f"  {d['slot']} {d['cond']}{d['corpus']} {d['identity']}: dup={d['dup_status']} main={'complete' if complete(d['main']) else 'missing/error'}"); continue
    same=d['dup']['verdict']==d['main']['verdict']; agree[(d['cond'],same)]+=1
    print(f"  {d['slot']} {d['cond']}{d['corpus']} {d['identity']}: main={d['main']['verdict']} {sorted(codes(d['main']))} mean={d['main']['mean_dimension']} | dup={d['dup']['verdict']} {sorted(codes(d['dup']))} mean={d['dup']['mean_dimension']} | {'AGREE' if same else 'DISAGREE'}")
print("  verdict agreement by condition:",{f"{c}: agree {agree[(c,True)]} / disagree {agree[(c,False)]}" for c in ('n','o')})
