"""Production/eval parity and honest-pin invariants; no SEC or model network calls."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from app.config import settings
from app.services.openai_service import openai_service
from evals import runner
from evals.schema import GoldenFiling
from evals.scorers import score_bank_revenue_integrity
from scripts import pin_baseline

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
async def test_runner_uses_production_stream_flag_and_scores_final_result(monkeypatch):
    filing = GoldenFiling('FIX', '1', 'a', '10-K', 'https://example.test', 'Fixture')
    grounding = {'filing_text': 'raw', 'excerpt': 'excerpt', 'xbrl_metrics': {'revenue': 100}}
    final = {'business_overview': 'authoritative final', 'financial_highlights': {}, 'risk_factors': []}
    scored = []
    real_score = runner.score_summary

    def score(payload, *args, **kwargs):
        scored.append(payload)
        return real_score(payload, *args, **kwargs)

    async def summarize(*args, **kwargs):
        if kwargs['stream_cb']:
            await kwargs['stream_cb']('incomplete preview must not be scored')
        return deepcopy(final)

    monkeypatch.setattr(runner, 'score_summary', score)
    mock = AsyncMock(side_effect=summarize)
    monkeypatch.setattr(openai_service, 'summarize_filing', mock)
    for enabled in [True, False]:
        monkeypatch.setattr(settings, 'STREAM_SECTION_REVEAL', enabled)
        result = await runner._run_one('baseline', filing, grounding)
        assert result['error'] is None
        assert result['stream_requested'] is enabled
        assert result['preview_count'] == int(enabled)
        assert scored[-1]['executive_summary'] == 'authoritative final'
        assert result['payload'] == scored[-1]
        assert result['xbrl_grounding'] == grounding['xbrl_metrics']
        assert bool(mock.call_args.kwargs['stream_cb']) is enabled
        assert mock.call_args.kwargs['filing_excerpt'] == 'excerpt'


@pytest.mark.asyncio
async def test_real_summary_assembly_matches_streamed_and_complete_provider_json(monkeypatch):
    # Exercise real request construction, stream collection, JSON assembly and final render.
    # Only the provider and optional extra recovery requests are replaced.
    payload = json.dumps({'metadata': {}, 'sections': {
        'the_print': 'A filing-grounded operating overview. ' * 65,
        'results_that_matter': {'table': [], 'takeaways': ['Demand stayed steady.']},
        'risks': [{'title': 'Demand', 'summary': 'Customer orders may decline.'}],
        'forward_signals': {'quotes': []},
        'notable_footnotes': [],
    }})
    requests = []

    async def create(**kwargs):
        requests.append(kwargs)
        if kwargs.get('stream'):
            async def chunks():
                yield SimpleNamespace(choices=[])
                for start in range(0, len(payload), 800):
                    yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=payload[start:start+800]))])
            return chunks()
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload))])

    monkeypatch.setattr(openai_service.client.chat.completions, 'create', create)
    monkeypatch.setattr(openai_service, '_recover_missing_sections', AsyncMock(return_value={}))
    previews = []

    async def preview(text):
        previews.append(text)

    args = ('Filing text.', 'Fixture', '10-K')
    complete = await openai_service.summarize_filing(*args, filing_excerpt='Filing excerpt.')
    streamed = await openai_service.summarize_filing(*args, filing_excerpt='Filing excerpt.', stream_cb=preview)
    assert complete.get('status') != 'error' and streamed.get('status') != 'error'
    assert complete == streamed
    assert previews
    assert requests[1].pop('stream') is True
    assert requests[1].pop('stream_options', None) == {'include_usage': True}
    assert requests[0] == requests[1]
    assert 'filing-grounded operating overview' in complete['business_overview']


@pytest.mark.asyncio
async def test_report_records_actual_harness_not_pinning_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, 'REPORTS_DIR', tmp_path)
    monkeypatch.setattr(settings, 'USE_STATEMENT_FINANCIALS', True)
    monkeypatch.setattr(settings, 'STREAM_SECTION_REVEAL', True)
    monkeypatch.setattr(settings, 'AI_DEFAULT_MODEL', 'measured-model')
    monkeypatch.setattr(settings, 'AI_FALLBACK_MODEL', 'measured-fallback')
    monkeypatch.setattr(settings, 'AI_FALLBACK_BASE_URL', 'https://fallback.example/v1')
    monkeypatch.setenv('GITHUB_SHA', 'measured-source')
    monkeypatch.setattr(runner, '_process_filing', AsyncMock(return_value=[]))
    await runner.main(['baseline'], 1, False, runs=3)
    report = json.loads(next(tmp_path.glob('eval_*.json')).read_text())
    assert report['harness']['model'] == 'measured-model'
    assert report['harness'].get('fallback_model') == 'measured-fallback'
    assert report['harness'].get('fallback_base_url') == 'https://fallback.example/v1'
    assert report['harness']['use_statement_financials'] is True
    assert report['harness']['stream_section_reveal'] is True
    assert report['harness']['source_sha'] == 'measured-source'
    assert report['harness']['golden_set_sha256'] == hashlib.sha256(runner.GOLDEN_PATH.read_bytes()).hexdigest()


@pytest.fixture
def pin_report():
    filings = json.loads(runner.GOLDEN_PATH.read_text())['filings']
    results = [{'candidate': 'baseline', 'ticker': f['ticker'], 'filing_type': f['filing_type'],
                'run': run, 'score': {'schema_valid': True, 'gate_failures': []},
                'passed_gates': True, 'error': None}
               for f in filings if f['verified'] and f['document_url'] for run in range(3)]
    return {'harness': {'model': 'measured-model', 'judge': False, 'use_statement_financials': True,
                        'stream_section_reveal': True, 'fallback_model': '', 'fallback_base_url': '',
                        'ai_evidence_snap': False, 'ai_figure_trace_gate': False,
                        'ai_forward_quote_gate': False, 'use_structured_output': False,
                        'golden_set_sha256': hashlib.sha256(runner.GOLDEN_PATH.read_bytes()).hexdigest()},
            'summary': {'baseline': {'n': len(results), 'errors': 0, 'gate_fail_rate': 0.0, 'pass_rate': 1.0}}, 'results': results}


def test_pin_cli_preserves_note_and_measured_configuration(monkeypatch, tmp_path, pin_report):
    report = tmp_path/'eval_20260905T100000Z.json'
    report.write_text(json.dumps(pin_report))
    output = tmp_path/'baseline.json'
    output.write_text(json.dumps({'note': 'Keep this measured-history note.'}))
    monkeypatch.setenv('AI_DEFAULT_MODEL', 'unrelated-local-model')
    assert pin_baseline.main([str(report), '--out', str(output)]) == 0
    baseline = json.loads(output.read_text())
    assert baseline['note'] == 'Keep this measured-history note.'
    assert baseline['harness'] == pin_report['harness']
    assert baseline['runs_per_candidate'] == 3
    assert baseline['golden_set_size'] == 26
    assert baseline['source_report'] == report.name


@pytest.mark.parametrize('defect', ['two-runs', 'missing-filing', 'error', 'duplicate', 'provenance', 'counts'])
def test_pin_rejects_unrepresentative_or_incomplete_measurement(pin_report, defect):
    if defect == 'two-runs':
        pin_report['results'] = [r for r in pin_report['results'] if r['run'] < 2]
    elif defect == 'missing-filing':
        pin_report['results'] = pin_report['results'][3:]
    elif defect == 'error':
        pin_report['results'][0]['error'] = 'provider timed out'
    elif defect == 'duplicate':
        pin_report['results'][0] = pin_report['results'][1]
    elif defect == 'provenance':
        pin_report['harness']['golden_set_sha256'] = 'different-golden-set'
    elif defect == 'counts':
        pin_report['summary']['baseline']['n'] -= 1
    if defect != 'counts':
        pin_report['summary']['baseline']['n'] = len(pin_report['results'])
    with pytest.raises(ValueError):
        pin_baseline.build_baseline(pin_report, Path('eval_20260905T100000Z.json'))


def test_committed_jpm_components_rearm_g5():
    data = json.loads(runner.GOLDEN_PATH.read_text())
    filing = GoldenFiling.from_dict(next(f for f in data['filings'] if f['ticker'] == 'JPM'))
    components = {f.metric: f.value for f in filing.ground_truth if f.metric in {'net_interest_income', 'noninterest_income'}}
    assert components == {'net_interest_income': 95_443_000_000, 'noninterest_income': 87_004_000_000}
    assert score_bank_revenue_integrity('Net interest income $95.443B; noninterest revenue $87.004B', filing.ground_truth) == (1.0, [])
    score, failures = score_bank_revenue_integrity('Total revenue $182.447B', filing.ground_truth)
    assert score == 0.0 and len(failures) == 2


def test_ci_parity_and_bounded_repeat_measurement():
    # BaseLoader preserves the YAML key "on" instead of interpreting it as boolean.
    workflow = yaml.load((ROOT/'.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['on']['workflow_dispatch']['inputs']['eval_runs']['options'] == ['2', '3']
    steps = workflow['jobs']['eval-baseline']['steps']
    run = next(s for s in steps if s.get('name', '').startswith('Run baseline eval'))
    production = pin_baseline.production_env()
    for key in pin_baseline.AI_GUARD_ENV:
        assert run['env'].get(key) == production[key]
    for key in ('AI_FALLBACK_MODEL', 'AI_FALLBACK_BASE_URL'):
        assert run['env'].get(key) == ''
    copilot = yaml.load((ROOT/'.github/workflows/copilot-eval.yml').read_text(), Loader=yaml.BaseLoader)
    job = copilot['jobs']['copilot-eval']
    generation = next(s for s in job['steps'] if s.get('name') == 'Run every verified question three times')
    effective_env = {**copilot.get('env', {}), **job.get('env', {}), **generation.get('env', {})}
    for key in ('AI_FALLBACK_MODEL', 'AI_FALLBACK_BASE_URL'):
        assert effective_env.get(key) == ''
    assert run['env']['STREAM_SECTION_REVEAL'] == 'true'
    assert run['env']['EVAL_RUNS'] == "${{ github.event.inputs.eval_runs || '2' }}"
    assert 'case "$EVAL_RUNS" in 2|3)' in run['run']
    assert 'ARGS=(--candidates baseline --runs "$EVAL_RUNS")' in run['run']
    assert 'python -m evals.runner "${ARGS[@]}"' in run['run']


@pytest.mark.parametrize('defect', ['failed-gate', 'missing-gate', 'veto-list', 'missing-veto-list', 'veto-rate', 'missing-rate', 'pass-rate',
                                          'fallback-model', 'fallback-url', 'fallback-missing',
                                          'guard-ai_evidence_snap', 'guard-ai_figure_trace_gate',
                                          'guard-ai_forward_quote_gate', 'guard-use_structured_output',
                                          'guard-use_statement_financials', 'guard-missing', 'guard-type'])
def test_pin_cli_refuses_hard_veto_evidence_without_overwriting(tmp_path, pin_report, defect):
    first = pin_report['results'][0]
    stats = pin_report['summary']['baseline']
    if defect == 'failed-gate':
        first['passed_gates'] = False
    elif defect == 'missing-gate':
        del first['passed_gates']
    elif defect == 'veto-list':
        first['score']['gate_failures'] = ['G5 bank component missing']
    elif defect == 'missing-veto-list':
        del first['score']['gate_failures']
    elif defect == 'veto-rate':
        stats['gate_fail_rate'] = 1 / len(pin_report['results'])
    elif defect == 'missing-rate':
        del stats['gate_fail_rate']
    elif defect == 'pass-rate':
        stats['pass_rate'] = 1 - 1 / len(pin_report['results'])
    elif defect == 'fallback-model':
        pin_report['harness']['fallback_model'] = 'other-model'
    elif defect == 'fallback-url':
        pin_report['harness']['fallback_base_url'] = 'https://other.example/v1'
    elif defect == 'fallback-missing':
        del pin_report['harness']['fallback_model']
    elif defect.startswith('guard-') and defect not in {'guard-missing', 'guard-type'}:
        key = defect.removeprefix('guard-')
        pin_report['harness'][key] = not pin_report['harness'][key]
    elif defect == 'guard-missing':
        del pin_report['harness']['ai_figure_trace_gate']
    elif defect == 'guard-type':
        pin_report['harness']['ai_figure_trace_gate'] = 0
    report = tmp_path / 'eval_20260905T100000Z.json'
    report.write_text(json.dumps(pin_report))
    output = tmp_path / 'baseline.json'
    previous = b'{"note": "Existing honest baseline must survive rejection."}\n'
    output.write_bytes(previous)
    with pytest.raises(ValueError, match='Cannot pin'):
        pin_baseline.main([str(report), '--out', str(output)])
    assert output.read_bytes() == previous
