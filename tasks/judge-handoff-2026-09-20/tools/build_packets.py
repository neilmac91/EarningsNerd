"""Build unchanged original-row singleton packets from a retained eval report (KO / E3 / E1 stages).

Packet shape mirrors the E8 packager: {"harness": <original harness header>, "results": [<original row>]}.
Records per identity: packet sha256, canonical row sha256, request sha256 (the unchanged pure
build_judge_messages, extracted by AST exactly as the E8 packager does, with the frozen runner's
pre-builder XBRL/statement serialization), source report sha256. No model call, no provider import.

usage: build_packets.py <report.json> <out_dir> <repo_root> [TICKER|FORM|RUN ...]
"""
import ast, hashlib, json, sys
from pathlib import Path

def canonical(x): return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
def sha(b): return hashlib.sha256(b).hexdigest()

report_path, out_dir, repo = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
only = set(sys.argv[4:])
raw = report_path.read_bytes(); report = json.loads(raw)
golden_raw = (repo / 'backend/evals/golden_set.json').read_bytes()
golden = {(x['ticker'], x['filing_type']): x for x in json.loads(golden_raw)['filings']}
assert report['harness']['golden_set_sha256'] == sha(golden_raw), 'golden set provenance differs from checkout'
tree = ast.parse((repo / 'backend/evals/judge.py').read_text()); ctx = {'json': json}
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id in ('_JUDGE_SYSTEM', '_JUDGE_INSTRUCTIONS', '_JUDGE_SUMMARY_CHAR_CAP', '_JUDGE_EXCERPT_CHAR_CAP', '_JUDGE_XBRL_CHAR_CAP'):
            ctx[node.targets[0].id] = ast.literal_eval(node.value)
    if isinstance(node, ast.FunctionDef) and node.name == 'build_judge_messages':
        module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), 'unchanged_pure_build_judge_messages', 'exec'), ctx)
(out_dir / 'packets').mkdir(parents=True, exist_ok=True)
index = []
for i, row in enumerate(report['results'], start=1):
    ident = f"{row['ticker']}|{row['filing_type']}|{row['run']}"
    if only and ident not in only: continue
    assert not row.get('error') and isinstance(row.get('payload'), dict) and 'grounding_excerpt' in row, ident
    packet = {'harness': report['harness'], 'results': [row]}
    slot = f"{i:03d}-{row['ticker'].replace('.', '_')}-{row['filing_type']}-run{row['run']}"
    path = out_dir / 'packets' / f'{slot}.json'
    rawp = (json.dumps(packet, ensure_ascii=False, indent=2) + '\n').encode(); path.write_bytes(rawp)
    reread = json.loads(rawp); assert reread['harness'] == report['harness'] and reread['results'][0] == row
    filing = golden[row['ticker'], row['filing_type']]
    metrics = row.get('xbrl_grounding'); metrics = {a: b for a, b in metrics.items() if a != 'financial_classification'} if metrics else metrics
    xbrl = json.dumps(metrics, default=str) if metrics else ''
    excerpt = row.get('grounding_excerpt') or ''
    statement = row.get('statement_source')
    if statement: excerpt += '\n\n[APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE; independent of the generator excerpt]\n' + json.dumps(statement, ensure_ascii=False, sort_keys=True) + '\n[END APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE]'
    system, user = ctx['build_judge_messages'](row['payload'], filing['company_name'], row['filing_type'], excerpt, xbrl)
    index.append({'order': i, 'slot': slot,
                  'identity': {'candidate': row['candidate'], 'ticker': row['ticker'], 'filing_type': row['filing_type'], 'accession_number': row.get('accession_number'), 'run': row['run']},
                  'packet_path': str(path), 'packet_sha256': sha(rawp), 'row_sha256': sha(canonical(row)),
                  'request_sha256': sha(canonical({'system': system, 'user': user})),
                  'source_report_sha256': sha(raw), 'source_sha': report['harness']['source_sha'],
                  'input_lengths': {'summary_chars': len(json.dumps(row['payload'], indent=2)), 'excerpt_chars': len(excerpt), 'xbrl_chars': len(xbrl)}})
(out_dir / 'packets-index.json').write_text(json.dumps({'source_report': str(report_path), 'source_report_sha256': sha(raw), 'source_sha': report['harness']['source_sha'], 'packets': index}, indent=2) + '\n')
print(f"built {len(index)} packets from {report_path.name} (sha256 {sha(raw)}) -> {out_dir}")
