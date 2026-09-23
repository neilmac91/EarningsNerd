"""Offline binding of immutable Fable packets and contract-2 verdicts; no app imports."""
import ast
import hashlib
import json
import re
from pathlib import Path

JUDGE = 'cli:claude-fable-5-1'
FROZEN = {
    'judge_report.py': '11a79f1e8288d4f91b6ae0051f31a93d08a113b7541e540f733cee20c8c0e780',
    'judge.py': '7522f977e1f1a6704508c587c525a1d213cd460ff68af229530ec414bc308857',
    'runner.py': '63b010b7968c3f4bdbcfd62114af82dcfcd8c5eb56e892b0c0da77f4943c0029',
    'weekly_readout.py': '8b171455199aacd135acda99ce8641af8b5e8a1cea8fe029276c6e1cd944070d',
    'golden_set.json': 'e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b',
}
DIMENSIONS = {'faithfulness', 'insight', 'clarity', 'specificity'}
IDENTITY = {'candidate', 'ticker', 'filing_type', 'accession_number', 'run'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def boundary(fn):
    """Present data, path and shape failures through the one public ValueError boundary."""
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError:
            raise
        except (OSError, KeyError, TypeError, AttributeError, IndexError, SyntaxError) as exc:
            raise ValueError(f'{fn.__name__}: {type(exc).__name__}: {exc}') from exc
    return wrapped


class Validator:
    @boundary
    def __init__(self, repo: Path):
        self.repo = Path(repo)
        self._verify_frozen()
        self.filings = json.loads((self.repo / 'backend/evals/golden_set.json').read_bytes())['filings']
        tree = ast.parse((self.repo / 'backend/evals/judge.py').read_text())
        names = {'_JUDGE_SYSTEM', '_JUDGE_INSTRUCTIONS', '_JUDGE_SUMMARY_CHAR_CAP',
                 '_JUDGE_EXCERPT_CHAR_CAP', '_JUDGE_XBRL_CHAR_CAP'}
        ctx = {'json': json}
        funcs = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
                ctx[node.targets[0].id] = ast.literal_eval(node.value)
            if isinstance(node, ast.FunctionDef) and node.name == 'build_judge_messages':
                funcs.append(node)
        require(len(funcs) == 1 and names <= ctx.keys(), 'Frozen message builder unavailable')
        module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), funcs[0]], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), '<frozen-pure-judge-builder>', 'exec'), ctx)
        self._build = ctx['build_judge_messages']

    def _verify_frozen(self):
        for name, expected in FROZEN.items():
            require(sha((self.repo / 'backend/evals' / name).read_bytes()) == expected,
                    f'Frozen file mismatch: {name}')

    def _context(self, row):
        matches = [f for f in self.filings if f['ticker'] == row.get('ticker')
                   and f['filing_type'] == row.get('filing_type')
                   and row.get('accession_number') in (None, f['accession_number'])]
        require(len(matches) == 1, 'Foreign or ambiguous filing identity')
        require(not row.get('error') and isinstance(row.get('payload'), dict), 'Unjudgeable original row')
        require('grounding_excerpt' in row and isinstance(row['grounding_excerpt'], (str, type(None))), 'Missing/invalid retained excerpt')
        metrics = row.get('xbrl_grounding')
        require(metrics is None or isinstance(metrics, dict), 'Invalid XBRL grounding')
        filtered = {k: v for k, v in metrics.items() if k != 'financial_classification'} if metrics else metrics
        xbrl = json.dumps(filtered, default=str) if metrics else ''
        excerpt = row.get('grounding_excerpt') or ''
        statement = row.get('statement_source')
        if statement:
            excerpt += ('\n\n[APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE; independent of the generator excerpt]\n'
                        + json.dumps(statement, ensure_ascii=False, sort_keys=True)
                        + '\n[END APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE]')
        lengths = {'summary_chars': len(json.dumps(row['payload'], indent=2)),
                   'excerpt_chars': len(excerpt), 'xbrl_chars': len(xbrl)}
        system, user = self._build(row['payload'], matches[0]['company_name'], row['filing_type'], excerpt, xbrl)
        return matches[0], lengths, sha(canonical({'system': system, 'user': user}))

    @boundary
    def validate_packet(self, entry: dict) -> dict:
        self._verify_frozen()
        require(isinstance(entry, dict), 'Invalid entry')
        raw = Path(entry['packet_path']).read_bytes()
        require(sha(raw) == entry['packet_sha256'], 'Packet bytes mismatch')
        packet = json.loads(raw)
        require(isinstance(packet, dict) and set(packet) == {'harness', 'results'}, 'Packet must be original singleton shape')
        require(isinstance(packet['results'], list) and len(packet['results']) == 1 and isinstance(packet['results'][0], dict), 'Packet must have one row')
        row = packet['results'][0]
        require(sha(canonical(row)) == entry['row_sha256'], 'Original row hash mismatch')
        ident = entry['identity']
        require(isinstance(ident, dict) and set(ident) == IDENTITY, 'Incomplete indexed identity')
        require(type(row.get('run')) is int and row['run'] >= 0 and type(ident['run']) is int, 'Invalid draw')
        for key in IDENTITY - {'accession_number'}:
            require(row.get(key) == ident[key], f'Identity mismatch: {key}')
        filing, lengths, request_hash = self._context(row)
        require(ident['accession_number'] == row.get('accession_number') or
                (row.get('accession_number') is None and ident['accession_number'] == filing['accession_number']), 'Accession identity mismatch')
        harness = packet['harness']
        require(isinstance(harness, dict) and harness.get('golden_set_sha256') == FROZEN['golden_set.json'], 'Golden provenance mismatch')
        require(isinstance(harness.get('source_sha'), str) and re.fullmatch(r'[0-9a-f]{40}', harness['source_sha']), 'Invalid source provenance')
        if 'source_sha' in entry:
            require(entry['source_sha'] == harness['source_sha'], 'Source commit mismatch')
        require(isinstance(entry.get('source_report_sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', entry['source_report_sha256']), 'Missing original report provenance')
        require(request_hash == entry['request_sha256'], 'Assembled request hash mismatch')
        if 'input_lengths' in entry:
            require(entry['input_lengths'] == lengths, 'Indexed input lengths mismatch')
        return packet

    @boundary
    def validate_output(self, entry: dict, data: dict) -> dict:
        packet = self.validate_packet(entry)
        require(isinstance(data, dict) and isinstance(data.get('results'), list) and len(data['results']) == 1, 'Output must have exactly one row')
        row = data['results'][0]
        require(isinstance(row, dict), 'Invalid output row')
        original = packet['results'][0]
        require(canonical({k: v for k, v in row.items() if k != 'judge'}) ==
                canonical({k: v for k, v in original.items() if k != 'judge'}), 'Output row differs from immutable original')
        expected_harness = {**packet['harness'], 'judge': JUDGE, 'judge_contract_version': 2}
        require(canonical(data.get('harness')) == canonical(expected_harness), 'Output harness differs from frozen input/contract')
        judge = row.get('judge')
        require(isinstance(judge, dict) and judge.get('error') is None and judge.get('input_complete') is True,
                'Incomplete/error verdict')
        require(type(judge.get('contract_version')) is int and judge['contract_version'] == 2, 'Wrong verdict contract')
        require(judge.get('verdict') in ('PASS', 'FAIL'), 'Invalid verdict')
        dims = judge.get('dimensions')
        require(isinstance(dims, dict) and set(dims) == DIMENSIONS and all(type(v) is int and 1 <= v <= 5 for v in dims.values()), 'Invalid dimensions')
        mean = judge.get('mean_dimension')
        require(type(mean) in (int, float) and mean == round(sum(dims.values()) / 4, 4), 'Invalid mean dimension')
        gates = judge.get('gate_failures')
        require(isinstance(gates, list) and all(isinstance(g, str) and bool(g.strip()) for g in gates), 'Invalid gate reasons')
        require(not gates or judge['verdict'] == 'FAIL', 'Hard gate must veto')
        require(type(judge.get('passed')) is bool and judge['passed'] == (judge['verdict'] == 'PASS'), 'Passed/verdict mismatch')
        # Frozen explicit PASS may be below the fallback dimension threshold; preserve it.
        _, lengths, _ = self._context(original)
        require(judge.get('input_lengths') == lengths and all(type(v) is int for v in judge['input_lengths'].values()), 'Verdict input lengths mismatch')
        return judge
