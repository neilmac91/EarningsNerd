"""Consolidate per-slot judged outputs into one judged.json/judged.md in the harness's own shape.

Uses the pinned checkout's own evals.judge_report functions (summarize, render_markdown, JUDGE_ID) and
JUDGE_CONTRACT_VERSION; never judges. Every original identity is preserved in original order. A prior
judged.json (E1) supplies first valid verdicts; missing/error slots are listed explicitly.
usage (cwd = pinned backend): consolidate.py <original report> <packets-index.json> <slots_root> <out_dir> [prior judged.json]
"""
import hashlib, json, sys
from pathlib import Path
from evals.judge_report import JUDGE_ID, complete_verdict, render_markdown, summarize
from evals.judge import JUDGE_CONTRACT_VERSION
from app.utils.datetimes import iso_z, utcnow

def sha(b): return hashlib.sha256(b).hexdigest()
report_path, index_path, slots_root, out_dir = map(Path, sys.argv[1:5]); prior = Path(sys.argv[5]) if len(sys.argv) > 5 else None
raw = report_path.read_bytes(); report = json.loads(raw); index = json.loads(index_path.read_text())
assert index['source_report_sha256'] == sha(raw), 'index does not belong to this report'
by_ident = {(p['identity']['ticker'], p['identity']['filing_type'], p['identity']['run']): p for p in index['packets']}
prior_rows, prior_meta = {}, None
if prior:
    pj = json.loads(prior.read_text()); ph = pj['harness']
    assert ph.get('judge') == JUDGE_ID and ph.get('judge_contract_version') == JUDGE_CONTRACT_VERSION and ph.get('source_sha') == report['harness']['source_sha']
    prior_rows = {(r['ticker'], r['filing_type'], r['run']): r for r in pj['results'] if complete_verdict(r.get('judge'))}
    prior_meta = {'path': str(prior), 'sha256': sha(prior.read_bytes()), 'judged_at': pj.get('judged_at'), 'complete_verdicts_reused': len(prior_rows)}
results, slots, missing, errors = [], [], [], []
for row in report['results']:
    k = (row['ticker'], row['filing_type'], row['run']); judge, src = None, None
    if k in prior_rows:
        pr = prior_rows[k]; assert {a: pr[a] for a in row if a != 'judge'} == {a: row[a] for a in row if a != 'judge'}, f'prior row differs from original {k}'
        judge, src = pr['judge'], {'source': 'prior_run', 'path': str(prior), 'judged_at': pj.get('judged_at')}
    p = by_ident.get(k)
    if judge is None and p:
        jf = slots_root / p['slot'] / 'judged.json'
        if jf.exists():
            d = json.loads(jf.read_text()); r0 = d['results'][0]
            assert (r0['ticker'], r0['filing_type'], r0['run']) == k and {a: r0[a] for a in row if a != 'judge'} == {a: row[a] for a in row if a != 'judge'}, f'slot row differs from original {k}'
            assert d['harness'].get('judge') == JUDGE_ID and d['harness'].get('judge_contract_version') == JUDGE_CONTRACT_VERSION
            judge, src = r0.get('judge'), {'source': 'slot', 'slot': p['slot'], 'path': str(jf), 'judged_json_sha256': sha(jf.read_bytes()), 'judged_at': d.get('judged_at'), 'request_sha256': p.get('request_sha256'), 'row_sha256': p.get('row_sha256')}
    if judge is None: missing.append(list(k))
    elif not complete_verdict(judge): errors.append({'identity': list(k), 'error': judge.get('error'), 'verdict': judge.get('verdict')})
    results.append({**row, 'judge': judge}); slots.append({'identity': list(k), **(src or {'source': 'missing'})})
harness = {**report['harness'], 'judge': JUDGE_ID, 'judge_contract_version': JUDGE_CONTRACT_VERSION}
judged = {**report, 'phase': 'judged', 'results': results, 'harness': harness, 'judged_at': iso_z(utcnow()), 'judged_summary': summarize(results),
          'consolidation': {'method': 'one unchanged-harness evals.judge_report command per original-row singleton packet (concurrency 1); consolidated here without any re-judging',
                            'source_report': str(report_path), 'source_report_sha256': sha(raw), 'prior_judged': prior_meta, 'slots': slots, 'missing_identities': missing, 'error_identities': errors}}
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / 'judged.json').write_text(json.dumps(judged, indent=2) + '\n'); (out_dir / 'judged.md').write_text(render_markdown(judged))
print('judged_summary:', json.dumps(judged['judged_summary']), '| missing:', missing, '| errors:', errors)
