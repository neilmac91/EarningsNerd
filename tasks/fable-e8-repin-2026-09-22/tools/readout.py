"""Validated partial readout; no model calls and no causal or variance-effect estimate."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from binding import Validator, canonical, sha as byte_sha
from resume import (KNOWN, POLICY_ID, RECONCILIATION, inspect_stage, load_index,
                    verify_bundle, verify_supplement, reconciled_output,
                    read, write, sha, now)


def key(row): return tuple(row.get(k) for k in ('candidate','ticker','filing_type','run'))
def summary(judges, planned):
    gates=Counter(); unclassified=Counter(); affected=0
    for j in judges:
        codes=set(); has_unclassified=False
        for reason in j['gate_failures']:
            match=re.match(r'^\s*(G[2345])\b',reason)
            if match: codes.add(match.group(1))
            else: unclassified[reason]+=1; has_unclassified=True
        gates.update(codes)
        affected += has_unclassified
    return {'planned':planned,'complete':len(judges),'missing':planned-len(judges),'negative':sum(j['verdict']=='FAIL' for j in judges),'gate_attempt_counts':{g:gates[g] for g in ('G2','G3','G4','G5')},'unclassified_gate_reason_occurrences':sum(unclassified.values()),'unclassified_gate_affected_judgments':affected,'unclassified_gate_reasons':dict(unclassified)}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--stage',required=True,choices=['e3-candidate1','e3-candidate2']);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    root=args.bundle.resolve();verify_supplement();verify_bundle(root);v=Validator(args.repo.resolve());idx,status=inspect_stage(root,args.stage,v)
    if args.stage!='e8':
        original=read(root/idx['source_report']);rows=[];judges=[];missing=[]
        for entry in idx['packets']:
            packet=v.validate_packet(entry);row=packet['results'][0];jf=root/'stages'/args.stage/'slots'/entry['slot']/'judged.json';j=None
            recovered=reconciled_output(root,args.stage,entry['slot'],v,idx)
            if recovered:
                if jf.exists():raise ValueError('Known failed slot was promoted or rejudged')
                jf=recovered
            if jf.exists():j=v.validate_output(entry,read(jf));judges.append(j)
            else:missing.append(entry['identity'])
            rows.append({**row,'judge':j})
        if len(rows)!=len(original['results']) or any({k:x for k,x in a.items() if k!='judge'}!={k:x for k,x in b.items() if k!='judge'} for a,b in zip(rows,original['results'])):raise ValueError('Readout rows differ from original source')
        result={**original,'results':rows,'harness':{**original['harness'],'judge':'cli:claude-fable-5-1','judge_contract_version':2},'phase':'judged','judged_at':now(),'validated_partial_readout':summary(judges,70),'missing_identities':missing,'wrapper_policy':POLICY_ID,'supplement_manifest_sha256':sha(Path(__file__).resolve().parents[1]/'supplement-sha256.json'),'known_stop_reconciled':bool((root/'stages/e3-candidate1'/RECONCILIATION).exists()) if args.stage=='e3-candidate1' else False,'known_stop_original_failure':{'slot':KNOWN['slot'],'failure':'Invalid gate reasons','stop_sha256':KNOWN['stop_sha256'],'ledger_sha256':KNOWN['ledger_sha256']} if args.stage=='e3-candidate1' else None,'scope':'Only validated complete verdicts. The known AAPL017 original FAIL is virtually reused under the explicit wrapper policy; original failed output and STOP remain preserved. Missing judgments remain pending; no new judge calls in readout.'}
    else:
        mapping=read(root/'e8/e8-control-main-reuse-2026-09-19.json');reuse={(m['corpus'],tuple(m['identity'])):m for m in mapping['main_verdicts']};mains={};dups=[];cells=defaultdict(list)
        originals={1:root/'preserved/e2/judged.json',2:root/'preserved/e2-control2/judged.json'}
        control_data={c:read(p) for c,p in originals.items()};control_rows={c:{key(r):r for r in d['results']} for c,d in control_data.items()}
        for p in idx['reused_main_slots']:
            packet=v.validate_packet(p);k=key(p['identity']);m=reuse[(p['corpus'],k)];data=control_data[p['corpus']];row=control_rows[p['corpus']][k]
            if sha(originals[p['corpus']])!=m['judged_report_sha256'] or byte_sha(canonical(row['judge']))!=m['verdict_sha256'] or m['request_sha256']!=p['request_sha256'] or m['source_report_sha256']!=p['source_report_sha256']:raise ValueError('E2 reuse provenance mismatch')
            j=v.validate_output(p,{'harness':data['harness'],'results':[row]})
            if j!=m['verdict']:raise ValueError('E2 first verdict differs from reuse manifest')
            mains[p['output_id']]=(p,j);cells[(p['condition'],p['corpus'])].append(j)
        for p in idx['packets']:
            v.validate_packet(p);jf=root/'stages/e8/slots'/p['slot']/'judged.json';j=v.validate_output(p,read(jf)) if jf.exists() else None
            if p['slot_kind']=='main' and j is not None:mains[p['output_id']]=(p,j);cells[(p['condition'],p['corpus'])].append(j)
            elif p['slot_kind']=='duplicate':dups.append((p,j))
        duplicate_results=[]
        for p,j in dups:
            main=mains.get(p['output_id']);mj=main[1] if main else None
            duplicate_results.append({'slot':p['slot'],'condition':p['condition'],'corpus':p['corpus'],'identity':p['identity'],'complete':j is not None,'main_complete':mj is not None,'verdict_agrees':j['verdict']==mj['verdict'] if j and mj else None,'main':mj,'duplicate':j})
        result={'phase':'validated_partial_e8_readout','created_at':now(),'main_complete':len(mains),'main_planned':280,'duplicate_complete':sum(j is not None for _,j in dups),'duplicate_planned':20,'cells':{f'{c}{n}':summary(cells[(c,n)],70) for c in ('n','o') for n in (1,2)},'duplicates':duplicate_results,'scope':'Descriptive only. Earlier o judging and generation-time confounds persist. Not the complete planned variability analysis or a causal effect estimate.'}
    write(args.output,result);print(json.dumps(result.get('validated_partial_readout') or {k:result[k] for k in ('main_complete','main_planned','duplicate_complete','duplicate_planned','cells')},indent=2))
if __name__=='__main__':main()
