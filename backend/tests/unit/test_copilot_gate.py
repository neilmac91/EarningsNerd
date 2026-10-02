"""Full-cohort, terminal and provenance acceptance boundaries for the real runner."""
from copy import deepcopy
import asyncio
import json
from pathlib import Path

import pytest

from evals import copilot_runner as runner
from evals.copilot_schema import CopilotQACase
from evals.copilot_scorers import score_copilot_answer
from evals.schema import GroundTruthFact
from tests.unit.test_copilot_provenance import ACC, OTHER, fact, filing


def citation(**changes):
    return {**fact(), 'n': 1, 'section_ref': 'XBRL · ifrs-full:Revenue', 'verified': True, **changes}


def qa(period='2025-03-31'):
    return CopilotQACase(question='Revenue for fiscal year 2025?', question_id='revenue-2025',
        expected_facts=[GroundTruthFact('revenue', 996347000000, 'CNY')],
        expected_periods={'revenue': period})


def score(cites, answer='Revenue for FY2025 was RMB996.347 billion [1].', question=None):
    return score_copilot_answer(question or qa(), answer=answer, citations=cites, kind='answer',
        accession_number=ACC, period_of_report='2025-03-31', reporting_currency='CNY')


@pytest.mark.parametrize('changes', [{'value': None}, {'value': True}, {'value': float('nan')},
    {'accession': OTHER}, {'unit': None}, {'unit': 'USD'}, {'raw_tag': ''}, {'raw_tag': 7}, {'concept': ''},
    {'period_end': '2026-03-31'}, {'period_end': '2024-03-31'}, {'period_end': 'bad'}])
def test_all_declared_xbrl_provenance_checked_before_numeric_filter(changes):
    result = score([citation(**changes)])
    assert not result.passed and result.invalid_provenance
    assert any(s.startswith('PROVENANCE:') for s in result.gate_failures)


def test_explicit_comparative_question_and_other_metric_remain_valid():
    past = citation(period_end='2024-03-31', fiscal_year=2024)
    assert score([past], answer='Revenue for FY2024 was RMB996.347 billion [1].',
                 question=qa('2024-03-31')).passed
    extra = citation(n=2, concept='gross_profit', value=10, period_end='2024-03-31')
    assert score([citation(), extra]).passed
    assert score([], answer='Revenue for FY2025 was RMB996.347 billion.').passed  # coverage remains advisory


@pytest.mark.parametrize('answer', ['Revenue USD996.347 billion.', 'Revenue USD **996.347 billion**.',
                                   'Revenue 996.347 billion **euros**.'])
def test_wrong_expected_currency_is_veto_even_without_citation(answer):
    result = score([], answer=answer)
    assert not result.passed and result.contradictory_currencies == ['revenue']


def test_every_derived_operand_requires_own_accession_and_known_basis():
    a = fact(concept='gross_profit', value=10, period_start='2024-04-01')
    b = fact(value=20, period_start='2024-04-01')
    derived = citation(concept='gross_profit', value=.5, unit='pure', value_kind='margin', source_facts=[a,b])
    question = CopilotQACase(question='Margin?')
    assert score([derived], answer='Gross margin 50% [1].', question=question).passed
    for parts in ([a], [a, {**b, 'accession': OTHER}], [a, {**b, 'period_start': None}]):
        result = score([{**derived, 'source_facts': parts}], answer='Gross margin 50% [1].', question=question)
        assert not result.passed and result.invalid_provenance


def completion(**changes):
    return {'type': 'complete', 'answer': 'Revenue is disclosed.', 'citations': [],
            'kind': 'answer', 'misplaced_fact_markers': 0, **changes}


@pytest.mark.asyncio
@pytest.mark.parametrize('events', [[], [{'type':'token','text':'partial'}], [{'type':'error'}], [{'type':'error'}, completion()],
    [completion(), completion()], [completion(), {'type':'error'}],
    [completion(answer='')], [completion(citations=[None])],
    [{k:v for k,v in completion().items() if k != 'misplaced_fact_markers'}],
    [completion(kind='error')], [completion(misplaced_fact_markers=True)]])
async def test_terminal_completeness_is_required(events, monkeypatch):
    from app.services import copilot_service
    async def stream(**kwargs):
        for e in events:
            yield e
    monkeypatch.setattr(copilot_service, 'answer_filing_question', stream)
    with pytest.raises(ValueError):
        await runner._answer(filing(), 'Revenue?')


@pytest.mark.asyncio
async def test_single_terminal_not_disclosed_and_guard_count_are_retained(monkeypatch):
    from app.services import copilot_service
    async def stream(**kwargs):
        yield {'type': 'not_disclosed', 'answer': 'Not disclosed.'}
        yield completion(answer='Not disclosed.', kind='not_disclosed', misplaced_fact_markers=2)
    monkeypatch.setattr(copilot_service, 'answer_filing_question', stream)
    assert await runner._answer(filing(), 'Future?') == ('Not disclosed.', [], 'not_disclosed', 2)


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['complete', 'rejected', 'no_envelope', 'provider_error', 'cancelled'])
async def test_attempt_trace_retains_candidate_and_closes_provider(outcome, monkeypatch):
    """Rejected candidates remain diagnosable without storing provider error payloads."""
    from app.services import copilot_service
    from app.services.openai_service import STREAM_ACTIVITY_SENTINEL, STREAM_ERROR_SENTINEL

    source = 'The company sells products to retail and enterprise customers around the world.'
    snap = filing()
    snap.content_cache.critical_excerpt = source
    candidate = ['  The company serves ', 'retail customers [7].\n']
    if outcome in {'complete', 'rejected'}:
        declarations = [{'n': 7, 'excerpt': source, 'section': 'Business'}]
        candidate += ['===CITA', 'TIONS===\n', json.dumps(declarations) if outcome == 'complete' else '[broken]']
    started = asyncio.Event()
    closed = []
    private_error = 'provider-private-error-detail'
    activity = STREAM_ACTIVITY_SENTINEL + json.dumps({'name': 'get_financial_fact', 'phase': 'done'})
    monkeypatch.setattr(copilot_service.copilot_tools, 'run_tool', lambda *args, **kwargs: fact())

    async def stream(messages, tools, run_tool, **kwargs):
        try:
            run_tool('get_financial_fact', {'concept': 'revenue', 'fiscal_year': 2025})
            yield activity
            for delta in candidate:
                yield delta
            started.set()
            if outcome == 'cancelled':
                await asyncio.Event().wait()
            if outcome == 'provider_error':
                yield STREAM_ERROR_SENTINEL + private_error
        finally:
            closed.append(True)

    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    trace = {}
    if outcome == 'cancelled':
        task = asyncio.create_task(runner._answer(snap, 'Describe the business.', trace=trace))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif outcome == 'complete':
        answer, cites, kind, _ = await runner._answer(snap, 'Describe the business.', trace=trace)
        assert answer == 'The company serves retail customers [1].' and len(cites) == 1 and kind == 'answer'
    else:
        with pytest.raises(ValueError, match='provider error event'):
            await runner._answer(snap, 'Describe the business.', trace=trace)

    assert trace['candidate_deltas'] == candidate
    assert trace['withheld_reasons'] == {'rejected': ['Incomplete citation array'],
                                         'no_envelope': ['Missing citation envelope']}.get(outcome, [])
    assert trace['provider_controls'] == [{'type': 'activity'}] + (
        [{'type': 'error'}] if outcome == 'provider_error' else [])
    assert private_error not in json.dumps(trace)
    assert trace['tool_results'][0]['name'] == 'get_financial_fact'
    assert trace['tool_results'][0]['result']['cite'] == 'F1'
    if outcome == 'cancelled':
        assert trace['service_events'] == []
    elif outcome == 'complete':
        assert trace['service_events'][0]['type'] == 'complete'
        assert trace['service_events'][0]['answer'] == answer
    else:
        message = copilot_service._STREAM_FAILURE if outcome == 'provider_error' else copilot_service._PUBLICATION_ERROR
        assert trace['service_events'] == [{'type': 'error', 'message': message}]
    assert closed == [True]
    assert copilot_service.openai_service.stream_chat_with_tools is stream


def complete_report():
    cases = runner._load_cases(runner.GOLDEN_PATH)
    plan = runner._plan(cases, 3)
    return {'planned_attempts': plan, 'runs': 3,
        'results': [{**r,'terminal_complete': True,'score': {'passed':True,'gate_failures':[]}} for r in plan],
        'summary': {'expected':18,'completed':18,'scored':18,'errors':0}}


@pytest.mark.parametrize('damage', ['missing','duplicate','error','score','terminal','veto','count','plan','runs'])
def test_full_report_rejects_incomplete_or_red_evidence(damage):
    report = complete_report()
    assert runner.validate_report(report) == []
    if damage == 'missing':
        report['results'].pop()
    elif damage == 'duplicate':
        report['results'][-1] = deepcopy(report['results'][0])
    elif damage == 'error':
        report['results'][0]['error'] = {'type':'TimeoutError'}
        report['summary']['errors'] = 1
    elif damage == 'score':
        report['results'][0].pop('score')
    elif damage == 'terminal':
        report['results'][0]['terminal_complete'] = False
    elif damage == 'veto':
        report['results'][0]['score'] = {'passed':False,'gate_failures':['NUMERIC']}
    elif damage == 'count':
        report['summary']['scored'] = 17
    elif damage == 'plan':
        for row in report['planned_attempts'][:3] + report['results'][:3]:
            row['question_id'] = 'unverified-replacement'
    else:
        report['runs'] = 1
    assert runner.validate_report(report)


F_REASON = 'Unsupported prose quotation: quotation_not_in_source'


@pytest.mark.parametrize('error,label', [
    ({'type': 'ValueError', 'stage': 'answer_or_score', 'withheld_reason': F_REASON}, 'publication withheld: ' + F_REASON),
    ({'type': 'ValueError', 'stage': 'answer_or_score', 'withheld_reason': 'Invalid citation declaration'},
     'publication withheld: Invalid citation declaration'),
    ({'type': 'ValueError', 'stage': 'answer_or_score'}, 'operationally incomplete attempt'),
    ({'type': 'ValueError', 'withheld_reason': ''}, 'operationally incomplete attempt'),
    ({'type': 'ValueError', 'withheld_reason': [F_REASON]}, 'operationally incomplete attempt'),
    ('TimeoutError', 'operationally incomplete attempt')],
    ids=['decision-f', 'other-reason', 'uncaptured', 'empty', 'not-a-string', 'not-a-dict'])
def test_withheld_attempt_is_named_and_remains_a_failure(error, label):
    report = complete_report()
    report['results'][0].update(error=error, terminal_complete=False)
    report['results'][0].pop('score')
    report['summary'].update(scored=17, errors=1)
    assert runner.validate_report(report) == [label]


def test_verified_plan_preserves_pending_questions_and_exact_golden_periods():
    raw = json.loads(runner.GOLDEN_PATH.read_text())
    assert len(raw['pending_cases']) == 2 and all(c['verified'] is False for c in raw['pending_cases'])
    cases = runner._load_cases(runner.GOLDEN_PATH)
    assert len(runner._plan(cases, 3)) == 18
    assert len({c.ticker for c in cases}) == 5
    for c in cases:
        for q in c.qa:
            assert q.expected_periods == {f.metric:c.period_of_report for f in q.expected_facts}
    for changes in ('unverified','duplicate','noid','onerun','subset'):
        bad = deepcopy(cases)
        if changes == 'unverified':
            bad[0].verified = False
        elif changes == 'duplicate':
            bad[-1] = bad[0]
        elif changes == 'noid':
            bad[0].qa[0].question_id = ''
        elif changes == 'subset':
            bad = bad[:1]
        with pytest.raises(ValueError):
            runner._plan(bad, 1 if changes == 'onerun' else 3)


@pytest.mark.asyncio
async def test_runner_keeps_failed_attempt_in_denominator_and_full_inputs(monkeypatch):
    cases = runner._load_cases(runner.GOLDEN_PATH)
    calls = []
    monkeypatch.setattr(runner, '_snapshot_for_case', lambda c: filing())
    async def answer(snap, question, **kwargs):
        calls.append(question)
        if len(calls) == 1:
            raise TimeoutError('offline')
        return 'RMB996.347 billion', [], 'answer', 0
    monkeypatch.setattr(runner, '_answer', answer)
    report = await runner.run(cases=cases, runs=3)
    assert len(calls) == len(report['results']) == 18
    assert report['summary']['expected'] == 18 and report['summary']['scored'] == 17
    assert report['summary']['errors'] == 1 and not report['accepted']
    assert isinstance(report['results'][0].get('inputs'), dict)
    assert report['results'][0]['inputs']['initial_messages']
    assert report['results'][0]['elapsed_ms'] >= 0 and report['actual_model'] is None
    assert report['summary']['pass_rate'] == report['summary']['passed'] / 18


def test_workflow_is_explicit_same_repo_ready_full_cohort_and_always_artifacts(tmp_path):
    import os
    import subprocess
    import yaml
    data = yaml.safe_load((Path(__file__).parents[3]/'.github/workflows/copilot-eval.yml').read_text())
    trigger = data.get('on', data.get(True))
    assert set(trigger) == {'pull_request'}
    assert 'ready_for_review' in trigger['pull_request']['types']
    job = data['jobs']['copilot-eval']
    assert '!github.event.pull_request.draft' in job['if']
    assert 'head.repo.full_name == github.repository' in job['if']
    steps = job['steps']
    prepare = next(s for s in steps if 'Prepare actual' in s.get('name',''))
    run = next(s for s in steps if 'Run every' in s.get('name',''))
    assert steps.index(prepare) < steps.index(run)
    assert '--runs 3' in run['run'] and '--limit' not in run['run']
    assert 'OPENAI_API_KEY' not in job['env'] and 'OPENAI_API_KEY' not in prepare.get('env', {})
    artifact = next(s for s in steps if 'actions/upload-artifact@' in s.get('uses',''))
    assert artifact['if'] == 'always()'
    summary = next(s for s in steps if 'GITHUB_STEP_SUMMARY' in s.get('run',''))
    assert summary['if'] == 'always()' and steps.index(run) < steps.index(summary)
    assert 'copilot-eval.md >> "$GITHUB_STEP_SUMMARY"' in summary['run'] and 'env' not in summary
    # The exact step under Actions' bash: it appends the readable report, and a missing one (failed
    # preparation) is not a second failure.
    readable = tmp_path/'evals/reports/copilot/copilot-eval.md'
    readable.parent.mkdir(parents=True)
    for present in (False, True):
        if present:
            readable.write_text('| ASML | publication withheld: ' + F_REASON + ' |\n')
        page = tmp_path/f'summary-{present}.md'
        result = subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', summary['run']],
            cwd=tmp_path, env={**os.environ, 'GITHUB_STEP_SUMMARY': str(page)},
            capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, result.stderr
        assert (page.read_text() if page.exists() else '') == (readable.read_text() if present else '')


def preparation(tmp_path):
    import hashlib
    cases = runner._load_cases(runner.GOLDEN_PATH)
    db = tmp_path/'prepared-source.db'
    db.write_bytes(b'offline database bytes')
    sources = []
    for c in cases:
        folder = tmp_path/c.accession_number
        folder.mkdir()
        artifacts = {}
        for kind,filename in {'html':'filing.html','xbrl':'xbrl.json','sections':'sections.json','excerpt':'excerpt.txt'}.items():
            artifact = folder/filename
            artifact.write_text('actual source bytes')
            artifacts[kind] = {'path':str(artifact),'relative_path':c.accession_number+'/'+filename,
                               'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
        sources.append({'status':'complete','accession_number':c.accession_number,
                        'reporting_currency':c.reporting_currency,'artifacts':artifacts})
    data = {'status':'complete','errors':[],
        'source_manifest_sha256':hashlib.sha256(runner.SOURCES_PATH.read_bytes()).hexdigest(),
        'database_path':str(db),'database_artifact_path':'prepared-source.db',
        'database_sha256':hashlib.sha256(db.read_bytes()).hexdigest(),
        'planned_accessions':[c.accession_number for c in cases], 'sources': sources}
    return cases,data


@pytest.mark.parametrize('damage', ['status','manifest','cohort','database','artifact','currency'])
def test_preparation_integrity_is_checked_before_any_provider(damage,tmp_path):
    cases,data = preparation(tmp_path)
    path = tmp_path/'preparation.json'
    path.write_text(json.dumps(data))
    assert runner.validate_preparation(path,cases)['status'] == 'complete'
    if damage == 'status':
        data['status'] = 'unavailable'
    elif damage == 'manifest':
        data['source_manifest_sha256'] = '0'*64
    elif damage == 'cohort':
        data['sources'].pop()
    elif damage == 'database':
        Path(data['database_path']).write_bytes(b'changed')
    elif damage == 'artifact':
        Path(data['sources'][0]['artifacts']['html']['path']).write_text('changed')
    else:
        data['sources'][0]['reporting_currency'] = 'EUR'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        runner.validate_preparation(path,cases)


@pytest.mark.parametrize('failure',['revision','preparation','credential'])
def test_cli_preflight_failure_retains_artifact_and_never_calls_model(failure,tmp_path,monkeypatch):
    import sys
    from app.config import settings
    cases,data = preparation(tmp_path)
    path = tmp_path/'preparation.json'
    path.write_text(json.dumps(data))
    output = tmp_path/'out'
    monkeypatch.setenv('GITHUB_SHA','1'*40)
    monkeypatch.setenv('DATABASE_URL','sqlite://')
    monkeypatch.setattr(settings,'OPENAI_API_KEY','offline-test')
    if failure == 'revision':
        monkeypatch.delenv('GITHUB_SHA')
    elif failure == 'preparation':
        data['status'] = 'unavailable'
        path.write_text(json.dumps(data))
    else:
        monkeypatch.setattr(settings,'OPENAI_API_KEY','')
    called = []
    async def run(**kwargs):
        called.append(True)
        return {'accepted':True}
    monkeypatch.setattr(runner,'run',run)
    monkeypatch.setattr(sys,'argv',['copilot_runner','--preparation',str(path),'--output',str(output)])
    assert runner.main() == 1 and called == []
    report = json.loads((output/'copilot-eval.json').read_text())
    assert report['accepted'] is False and report['failures']


SOURCE = 'The company sells products to retail and enterprise customers around the world.'


def sourced():
    snap = filing()
    snap.content_cache.critical_excerpt = SOURCE
    return snap


def reply(outcome):
    """A provider candidate the real service publishes or withholds (decision F, or a malformed declaration)."""
    declarations = [{'n': 7, 'excerpt': SOURCE, 'section': 'Business'}]
    if outcome == 'quotation':
        return 'The filing says "retail and wholesale customers in Europe" [7].\n===CITATIONS===\n' + json.dumps(declarations)
    if outcome == 'declaration':
        declarations[0]['n'] = '7'
    return 'The company serves retail customers [7].\n===CITATIONS===\n' + json.dumps(declarations)


def test_withheld_rows_name_their_own_reason_and_still_fail_the_run(tmp_path, monkeypatch):
    import logging
    import sys
    from types import SimpleNamespace
    from app.config import settings
    from app.services import copilot_service
    from evals import copilot_scorers
    _, data = preparation(tmp_path)
    path = tmp_path/'preparation.json'
    path.write_text(json.dumps(data))
    output = tmp_path/'out'
    monkeypatch.setenv('GITHUB_SHA', '1'*40)
    monkeypatch.setenv('DATABASE_URL', 'sqlite://')
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', 'offline-test')
    monkeypatch.setattr(sys, 'argv', ['copilot_runner', '--preparation', str(path), '--output', str(output)])
    monkeypatch.setattr(runner, '_snapshot_for_case', lambda case: sourced())
    replies = iter(['quotation', 'declaration'])
    async def stream(messages, tools, run_tool, **kwargs):
        yield reply(next(replies, 'published'))
    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    # Every published row passes, so only the withheld rows can fail the run.
    passing = SimpleNamespace(to_dict=lambda: {'passed': True, 'gate_failures': []})
    monkeypatch.setattr(copilot_scorers, 'score_copilot_answer', lambda *args, **kwargs: passing)
    telemetry = logging.getLogger('app.services.ai_metrics')
    monkeypatch.setattr(telemetry, 'handlers', [])  # main() attaches its console handler here
    level = telemetry.level
    try:
        assert runner.main() == 1
    finally:
        telemetry.setLevel(level)
    report = json.loads((output/'copilot-eval.json').read_text())
    rows = report['results']
    assert [row['tool_trace']['withheld_reasons'] for row in rows[:2]] == [[F_REASON], ['Invalid citation declaration']]
    assert [row.get('error') for row in rows[:2]] == [
        {'type': 'ValueError', 'stage': 'answer_or_score', 'withheld_reason': F_REASON},
        {'type': 'ValueError', 'stage': 'answer_or_score', 'withheld_reason': 'Invalid citation declaration'}]
    assert all('error' not in row and row['tool_trace']['withheld_reasons'] == [] for row in rows[2:])
    assert {k: report['summary'][k] for k in ('expected', 'completed', 'scored', 'errors')} == {
        'expected': 18, 'completed': 18, 'scored': 16, 'errors': 2}
    assert report['failures'] == ['publication withheld: ' + F_REASON, 'publication withheld: Invalid citation declaration']
    assert report['accepted'] is False
    readable = (output/'copilot-eval.md').read_text()
    assert '| publication withheld: ' + F_REASON + ' |' in readable
    assert '| publication withheld: Invalid citation declaration |' in readable


@pytest.mark.asyncio
async def test_withheld_capture_keeps_other_attempts_records_off_the_row():
    """The runner awaits one attempt at a time (its observer patches the provider), so a capture's
    window is its attempt. Even overlapping, a record logged by another attempt's task, or by a
    thread no attempt started, never reaches the row; a thread the attempt starts still does."""
    import threading
    from app.services.copilot_service import _UnpublishableAnswer, logger
    def withhold(reason):
        logger.warning('Copilot candidate withheld at citation publication boundary: %s', _UnpublishableAnswer(reason))
    first, second = [], []
    opened, logged = asyncio.Event(), asyncio.Event()
    async def attempt_one():
        with runner._WithheldReasons(first):
            await opened.wait()
            withhold(F_REASON)
            logged.set()
    async def attempt_two():
        with runner._WithheldReasons(second):
            opened.set()
            await logged.wait()
            await asyncio.to_thread(withhold, 'Invalid citation declaration')
            stray = threading.Thread(target=withhold, args=('Empty resolved answer',))
            stray.start()
            stray.join()
    await asyncio.gather(attempt_one(), attempt_two())
    assert first == [F_REASON] and second == ['Invalid citation declaration']
    assert not any(isinstance(f, runner._WithheldReasons) for f in logger.filters)


@pytest.mark.asyncio
async def test_withheld_capture_keeps_service_lines_in_runner_log(monkeypatch, capsys):
    """The copilot-eval job sets no root handler, so the service's warnings and tracebacks reach
    stderr (tee'd into runner.log) only through logging.lastResort, which runs only when no handler
    is on the logger's path. During an attempt the capture must leave them printed."""
    import logging
    from app.services import copilot_service
    monkeypatch.setattr(logging.getLogger(), 'handlers', [])  # the job's root logger
    replies = iter(['quotation', 'crash'])
    async def stream(messages, tools, run_tool, **kwargs):
        if next(replies) == 'crash':
            raise RuntimeError('offline provider crash')
        yield reply('quotation')
    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    traces = [{}, {}]
    for trace in traces:
        with pytest.raises(ValueError, match='provider error event'):
            await runner._answer(sourced(), 'Describe the business.', trace=trace)
    assert [trace['withheld_reasons'] for trace in traces] == [[F_REASON], []]
    printed = capsys.readouterr().err
    assert 'Copilot candidate withheld at citation publication boundary: ' + F_REASON + '\n' in printed
    assert 'Copilot answer_filing_question failed\nTraceback (most recent call last):' in printed
    assert 'RuntimeError: offline provider crash\n' in printed


def test_nullable_raw_tag_is_preserved_without_inventing_provenance():
    result = score([citation(raw_tag=None)])
    assert result.passed and result.invalid_provenance == []


@pytest.mark.asyncio
async def test_actual_service_refusal_terminal_is_accepted_without_invented_counter(monkeypatch):
    from app.services import copilot_service
    async def stream(*args, **kwargs):
        yield ('===NOT_DISCLOSED===This filing does not disclose that information.'
               '\n===FOLLOWUPS===["What did revenue total?", "What risks were disclosed?"]')
    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    result = None
    try:
        result = await runner._answer(filing(), 'Undisclosed?')
    except ValueError:
        pass
    assert result is not None, 'valid production refusal was rejected'
    answer, cites, kind, stripped = result
    assert kind == 'not_disclosed' and stripped == 0 and cites == []
    assert answer == 'This filing does not disclose that information.'


@pytest.mark.asyncio
@pytest.mark.parametrize('value', [None, True, -1, '0'])
async def test_refusal_provided_malformed_counter_is_rejected(value, monkeypatch):
    from app.services import copilot_service
    async def stream(**kwargs):
        yield completion(kind='not_disclosed', misplaced_fact_markers=value)
    monkeypatch.setattr(copilot_service, 'answer_filing_question', stream)
    with pytest.raises(ValueError, match='malformed terminal'):
        await runner._answer(filing(), 'Undisclosed?')


@pytest.mark.asyncio
@pytest.mark.parametrize('stop', ['complete', 'error', 'cancel'])
async def test_trace_retains_uncited_and_rejected_tools_and_restores_provider(stop,monkeypatch):
    import asyncio
    from app.services import copilot_service
    from app.services.ai.copilot_chat import STREAM_ERROR_SENTINEL
    supplied = iter([fact(raw_tag=None), fact(accession=OTHER)])
    monkeypatch.setattr(copilot_service.copilot_tools, 'run_tool', lambda *a, **kw: next(supplied))
    async def stream(messages, tools, run_tool, **kwargs):
        run_tool('get_financial_fact', {'concept':'revenue'})
        run_tool('get_financial_fact', {'concept':'revenue','accession_number':OTHER})
        if stop == 'cancel':
            raise asyncio.CancelledError
        if stop == 'error':
            yield STREAM_ERROR_SENTINEL + 'offline failure'
        else:
            yield 'Revenue was RMB996.347 billion.\n===CITATIONS===\n[]'
    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    trace = {}
    if stop == 'complete':
        result = await runner._answer(filing(),'Revenue?',trace=trace)
        assert result[1] == []
    else:
        with pytest.raises(asyncio.CancelledError if stop == 'cancel' else ValueError):
            await runner._answer(filing(),'Revenue?',trace=trace)
    assert copilot_service.openai_service.stream_chat_with_tools is stream
    assert len(trace.get('tool_results', [])) == 2
    assert trace['tool_results'][0]['result']['cite'] == 'F1'
    assert trace['tool_results'][0]['result']['raw_tag'] is None
    assert trace['tool_results'][1]['result'] == {'error':'invalid_filing_provenance'}
    assert trace['initial_messages'] and trace['tool_schema'] and trace['generation_options']['model']


def test_downloaded_bundle_relocates_without_original_host_paths(tmp_path):
    import shutil
    original = tmp_path/'original'
    original.mkdir()
    cases,data = preparation(original)
    (original/'preparation.json').write_text(json.dumps(data))
    relocated = tmp_path/'downloaded'
    shutil.copytree(original,relocated)
    shutil.rmtree(original)
    validated = None
    try:
        validated = runner.validate_preparation(relocated/'preparation.json',cases)
    except ValueError:
        pass
    assert validated is not None, 'valid relocated source bundle was rejected'
    assert validated['database_path'] == str(relocated/'prepared-source.db')
    assert validated['original_database_path'] == str(original/'prepared-source.db')
    data['sources'][0]['artifacts']['html']['relative_path'] = '../outside'
    (relocated/'preparation.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='artifact changed or missing'):
        runner.validate_preparation(relocated/'preparation.json',cases)


@pytest.mark.parametrize('complete',[True,False])
def test_human_readable_report_preserves_failures_counts_and_json(complete,tmp_path):
    report = complete_report() if complete else {'accepted':False,'results':[], 'failures':['preflight unavailable']}
    if complete:
        report.update(accepted=False,failures=['NUMERIC veto','publication withheld: '+F_REASON])
        report['results'][0]['score'] = {'passed':False,'gate_failures':['NUMERIC veto']}
        report['results'][1].update(terminal_complete=False,
            error={'type':'ValueError','stage':'answer_or_score','withheld_reason':F_REASON})
        report['results'][1].pop('score')
    path = runner._write_report(report,tmp_path)
    assert json.loads(path.read_text()) == report
    readable = tmp_path/'copilot-eval.md'
    assert readable.is_file()
    text = readable.read_text()
    assert 'FAIL / incomplete' in text
    assert ('Expected: 18' in text and 'NUMERIC veto' in text) if complete else 'preflight unavailable' in text
    assert ('| False | publication withheld: ' + F_REASON + ' |' in text) is complete
    assert 'not the weekly strong-judge readout' in text
