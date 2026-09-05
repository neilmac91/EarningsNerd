"""Failed eval attempts retain observations; CLI emits sanitized provider evidence offline."""
import logging
import json
import runpy
import sys
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import ai_metrics
from app.services.openai_service import openai_service
from evals import runner
from evals.schema import GoldenFiling


@pytest.mark.asyncio
async def test_planned_manifest_survives_missing_executor_results(monkeypatch, tmp_path):
    golden = tmp_path / 'golden.json'
    golden.write_text(json.dumps({'filings': [
        {'ticker': 'ONE', 'cik': '1', 'accession_number': 'a', 'filing_type': '20-F',
         'document_url': 'https://example.test/one', 'company_name': 'One', 'verified': True},
        {'ticker': 'TWO', 'cik': '2', 'accession_number': 'b', 'filing_type': '10-K',
         'document_url': 'https://example.test/two', 'company_name': 'Two', 'verified': True},
    ]}))
    monkeypatch.setattr(runner, 'GOLDEN_PATH', golden)
    emitted = []

    async def missing(*args, **kwargs):
        return []

    def write(summary, results, harness):
        emitted.append((summary, results, harness))
        return tmp_path / 'report.md'

    monkeypatch.setattr(runner, '_process_filing', missing)
    monkeypatch.setattr(runner, '_write_report', write)
    await runner.main(['baseline'], None, False, runs=2, forms=['20-F'])
    summary, results, harness = emitted[0]
    assert results == [] and summary == {}
    assert harness['candidates'] == ['baseline']
    assert harness['runs_per_candidate'] == 2
    assert harness['filings'] == [{'ticker': 'ONE', 'filing_type': '20-F'}]


def test_summary_distinguishes_attempts_from_scored_results():
    score = runner.score_summary({}, {})
    result = {'candidate': 'baseline', 'score': score.__dict__, 'aggregate': score.aggregate(),
              'passed_gates': score.passed_gates, 'judge': None, 'error': None}
    failed = {'candidate': 'baseline', 'score': None, 'aggregate': 0, 'passed_gates': False,
              'judge': None, 'error': 'TimeoutError: '}
    stats = runner._summarize([result, failed])['baseline']
    assert stats['n'] == 2 and stats['scored'] == 1 and stats['errors'] == 1
    assert stats['mean_aggregate'] == result['aggregate']


@pytest.mark.asyncio
async def test_weekly_report_declares_fixed_plan_even_when_all_results_are_missing(monkeypatch):
    from evals import weekly_readout

    monkeypatch.setenv('OPENAI_API_KEY', 'offline-fixture')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'offline-fixture')
    monkeypatch.setenv('GITHUB_SHA', 'a' * 40)
    monkeypatch.setattr(settings, 'USE_STATEMENT_FINANCIALS', True)
    monkeypatch.setattr(settings, 'STREAM_SECTION_REVEAL', True)
    monkeypatch.setattr(settings, 'USE_STRUCTURED_OUTPUT', False)

    async def missing(*args, **kwargs):
        return []

    monkeypatch.setattr(runner, '_process_filing', missing)
    readout, report = await weekly_readout.measure()
    expected = [{'ticker': f['ticker'], 'filing_type': f['filing_type']}
                for f in weekly_readout.load_cohort()]
    assert len(expected) == 8
    assert report['harness']['candidates'] == ['baseline']
    assert report['harness']['runs_per_candidate'] == 3
    assert report['harness']['filings'] == expected
    assert report['results'] == []
    assert readout['status'] != 'complete'


@pytest.mark.asyncio
@pytest.mark.parametrize('streaming', [True, False])
async def test_timeout_retains_elapsed_and_observed_previews_without_scoring(monkeypatch, streaming):
    clock = iter([100.0, 175.125])
    monkeypatch.setattr(runner, 'time', SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(settings, 'STREAM_SECTION_REVEAL', streaming)

    async def timeout(*args, **kwargs):
        if kwargs['stream_cb']:
            await kwargs['stream_cb']('partial one')
            await kwargs['stream_cb']('partial two')
        raise TimeoutError('provider deadline exhausted')

    monkeypatch.setattr(openai_service, 'summarize_filing', timeout)
    filing = GoldenFiling('BABA', '1', 'accession', '20-F', 'https://example.test', 'Fixture')
    result = await runner._run_one('baseline', filing,
                                 {'filing_text': 'raw', 'excerpt': 'chosen', 'xbrl_metrics': {}}, run_index=1)
    assert result['latency_seconds'] == 75.125
    assert result['stream_requested'] is streaming
    assert result['preview_count'] == (2 if streaming else 0)
    assert result['ticker'] == 'BABA' and result['filing_type'] == '20-F' and result['run'] == 1
    assert result['error'] == 'TimeoutError: provider deadline exhausted'
    assert result['score'] is None and result['passed_gates'] is False
    assert 'payload' not in result


def test_actual_cli_emits_sanitized_ai_records_once_without_enabling_request_logs(monkeypatch, capsys):
    logger = ai_metrics.logger
    monkeypatch.setattr(logger, 'handlers', [])
    monkeypatch.setattr(logger, 'level', logging.WARNING)
    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr(ai_metrics, '_calls', {})
    monkeypatch.setattr(ai_metrics, '_summaries', ai_metrics.Counter())
    monkeypatch.setattr(ai_metrics, '_model_labels', set())
    request_logger = logging.getLogger('httpx2')
    original_request_level = request_logger.level
    original_root_level = logging.getLogger().level
    secret = 'private-prompt-or-key-must-not-be-logged'

    def no_network(coroutine):
        coroutine.close()
        runner._configure_eval_telemetry()  # CLI's prior call must remain idempotent.
        record = ai_metrics.record_ai_call(operation='summary_primary', provider='primary',
                                           actual_model='deepseek-v4-pro', outcome='timeout',
                                           usage={'prompt_tokens': 4, 'prompt': secret, 'key': secret})
        ai_metrics.record_ai_summary([record], 'timeout')
        assert len(logger.handlers) == 1

    # Inspect configuration before the callback invokes the helper again, so missing CLI
    # wiring cannot be masked by the idempotence check above.
    def checked_run(coroutine):
        try:
            assert logger.level == logging.INFO and len(logger.handlers) == 1
            return no_network(coroutine)
        finally:
            coroutine.close()

    monkeypatch.setattr(sys, 'argv', ['evals.runner', '--candidates', 'baseline'])
    monkeypatch.setattr(runner.asyncio, 'run', checked_run)
    monkeypatch.delitem(sys.modules, 'evals.runner')
    runpy.run_module('evals.runner', run_name='__main__')
    text = capsys.readouterr().err
    assert text.count('ai_call ') == 1 and text.count('ai_summary ') == 1
    assert '"outcome":"timeout"' in text and '"prompt_tokens":4' in text
    assert secret not in text
    assert request_logger.level == original_request_level
    assert logging.getLogger().level == original_root_level
