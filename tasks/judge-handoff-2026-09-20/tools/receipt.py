import json,sys,hashlib,re,statistics,collections
label,run_id,artifact,in_path,out_dir,note=sys.argv[1:7]
exec_note=sys.argv[7] if len(sys.argv)>7 else 'one unchanged-harness evals.judge_report command per original-row singleton packet, concurrency 1, consolidated without re-judging'

d=json.load(open(out_dir+'/judged.json')); r=d['results']; h=d['harness']; js=d['judged_summary']; cons=d.get('consolidation') or {}
G=re.compile(r"^\s*(G\d)\b")
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
comp=[x for x in r if isinstance(x.get('judge'),dict) and not x['judge'].get('error') and x['judge'].get('input_complete') is True and x['judge'].get('verdict') in ('PASS','FAIL')]
neg=sum(x['judge']['verdict']=='FAIL' for x in comp)
gc=collections.Counter(c for x in comp for c in {m.group(1) for g in x['judge']['gate_failures'] for m in [G.match(g)] if m})
dims={k: round(statistics.mean(x['judge']['dimensions'][k] for x in comp),3) for k in ('faithfulness','insight','clarity','specificity')}
errs=[(x['ticker'],x['filing_type'],x['run'],x['judge'].get('error')) for x in r if isinstance(x.get('judge'),dict) and x['judge'].get('error')]
inc=[(x['ticker'],x['filing_type'],x['run']) for x in r if isinstance(x.get('judge'),dict) and x['judge'].get('input_complete') is not True]
key=lambda x:(x['ticker'],x['filing_type'],x['run'])
g4={key(x) for x in comp if 'G4' in {m.group(1) for g in x['judge']['gate_failures'] for m in [G.match(g)] if m}}
fl={key(x) for x in comp if (x.get('attribution_audit') or {}).get('unverified')}
lines=[f"# Judge receipt — {label}","",
f"- Generation run: https://github.com/neilmac91/EarningsNerd/actions/runs/{run_id}",
f"- Artifact: `{artifact}`; report `{in_path.split('/')[-1]}`",
f"- Report source_sha: `{h['source_sha']}` ({note})",
f"- Golden set sha256 (report and checkout): `{h['golden_set_sha256']}`",
f"- Generator: `{h['model']}`; AI_ATTRIBUTION_VERIFY={h.get('ai_attribution_verify')}; AI_ATTRIBUTION_GATE={h.get('ai_attribution_gate')}",
f"- Input JSON sha256: `{sha(in_path)}`",
f"- Output judged.json sha256: `{sha(out_dir+'/judged.json')}`",
f"- Output judged.md sha256: `{sha(out_dir+'/judged.md')}`",
f"- Judge: `{h['judge']}`; contract version {h['judge_contract_version']}; per-verdict contract versions: {dict(collections.Counter(x['judge'].get('contract_version') for x in r if isinstance(x.get('judge'),dict)))}",
f"- Judged at: {d['judged_at']}; harness: unmodified `evals.judge_report` at checkout 73cc31162c3dfe7ec497c8c88c43cf397afce4a7, concurrency 2, claude CLI 2.1.278, auth oauth_token/firstParty (subscription)",
"",
f"- Planned attempts: 70 (35 filings × 2 repeats); attempts in report: {js['attempts']}; judgeable: {js['judgeable']}; completely judged: {js['judged']}; judge errors/missing: {js['errors']} (missing identities: {cons.get('missing_identities','n/a')}; error identities: {cons.get('error_identities','n/a')})",
f"- Negative verdicts (complete only): {neg}/{len(comp)} = {100*neg/len(comp):.1f}%",
f"- Gate attempt counts: G2={gc.get('G2',0)} G3={gc.get('G3',0)} G4={gc.get('G4',0)} G5={gc.get('G5',0)}",
f"- Dimension means: faithfulness={dims['faithfulness']} insight={dims['insight']} clarity={dims['clarity']} specificity={dims['specificity']}",
f"- Errors: {errs if errs else 'none'}",
f"- Incomplete/truncated judge input: {inc if inc else 'none'} (max excerpt chars {max(x['judge']['input_lengths']['excerpt_chars'] for x in comp)}, cap 400000; max summary chars {max(x['judge']['input_lengths']['summary_chars'] for x in comp)}, cap 100000; max xbrl chars {max(x['judge']['input_lengths']['xbrl_chars'] for x in comp)}, cap 40000)",
f"- Attempt-level overlap (not clause recall): Fable G4={len(g4)}, nonempty attribution_audit.unverified={len(fl)}, both={len(g4&fl)}, G4 without flag={len(g4-fl)}, flag without G4={len(fl-g4)}",
"- Full per-attempt reasons: analysis.txt; side-by-side flagged clauses vs G4 reasons: overlap-detail.txt"]
open(out_dir+'/receipt.md','w').write("\n".join(lines)+"\n"); print("\n".join(lines))
