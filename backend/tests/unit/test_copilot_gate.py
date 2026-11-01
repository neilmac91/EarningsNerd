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


def test_every_planned_case_declares_the_excerpt_source_its_preparation_must_record():
    # E80: native with the canonical sections the filing supplies whole, or a fallback the RUNBOOK documents for the
    # filing; a native declaration that leaves a section out, and every fallback, says why. BABA's 20-Fs supply stub
    # financials (FY2025 a stub MD&A too), and ASML's 20-F is the cohort's one fallback. A missing or malformed
    # declaration stops the plan.
    cases = runner._load_cases(runner.GOLDEN_PATH)
    whole = ['financials', 'mda', 'risk']
    assert [(c.ticker, c.excerpt_source['outcome'], c.excerpt_source.get('sections')) for c in cases] == [
        ('AAPL', 'native', whole), ('TSLA', 'native', whole), ('MSFT', 'native', whole),
        ('BABA', 'native', ['mda', 'risk']), ('BABA', 'native', ['risk']), ('ASML', 'fallback', None)]
    assert cases[-1].excerpt_source['fallback_reason'] == 'sections_not_supplied'
    for declared, valid in [
        ({'outcome': 'native', 'sections': whole, 'basis': 'every section whole'}, True),
        ({'outcome': 'native', 'sections': ['financials', 'mda'], 'basis': 'a 10-Q with no Risk Factors item'}, True),
        ({'outcome': 'fallback', 'fallback_reason': 'native_excerpt_thin', 'basis': 'documented'}, True),
        ({}, False), ('native', False), ({'outcome': 'cached'}, False),
        ({'outcome': 'native'}, False),
        ({'outcome': 'native', 'sections': []}, False),
        ({'outcome': 'native', 'sections': 'mda', 'basis': 'x'}, False),
        ({'outcome': 'native', 'sections': [['mda']], 'basis': 'x'}, False),
        ({'outcome': 'native', 'sections': ['mda', 'mda'], 'basis': 'x'}, False),
        ({'outcome': 'native', 'sections': ['notes'], 'basis': 'x'}, False),
        ({'outcome': 'native', 'sections': ['financials', 'mda']}, False),  # a section left out says why
        ({'outcome': 'native', 'sections': ['mda'], 'basis': ' '}, False),
        ({'outcome': 'native', 'sections': whole, 'basis': None}, False),
        ({'outcome': 'native', 'sections': ['mda'], 'basis': 'x', 'fallback_reason': None}, False),
        ({'outcome': 'fallback', 'fallback_reason': 'sections_not_supplied'}, False),
        ({'outcome': 'fallback', 'fallback_reason': 'sections_not_supplied', 'basis': ' '}, False),
        ({'outcome': 'fallback', 'fallback_reason': 'native_sections_disabled', 'basis': 'x'}, False),
        ({'outcome': 'fallback', 'fallback_reason': 'unrecorded', 'basis': 'x'}, False),
        ({'outcome': 'fallback', 'fallback_reason': 'sections_not_supplied', 'basis': 'x', 'sections': ['mda']}, False),
        ({'outcome': 'cached', 'fallback_reason': 'sections_not_supplied', 'basis': 'x'}, False),
        ({'outcome': 'fallback', 'fallback_reason': 'sections_not_supplied', 'basis': 7}, False),
    ]:
        bad = deepcopy(cases)
        bad[0].excerpt_source = declared
        if valid:
            assert len(runner._plan(bad, 3)) == 18
        else:
            with pytest.raises(ValueError, match='declares no valid excerpt source'):
                runner._plan(bad, 3)


@pytest.mark.parametrize('form', ['10-K', '10-Q', '20-F'])
def test_the_native_floors_are_where_the_assembler_reads_a_section_as_the_filing_s_own(form):
    # Under its floor the assembler backfills financials or MD&A with a dense window of the document, and skips any
    # section under 200 characters: the model then reads something other than that section, so a declared section
    # must reach its floor.
    from app.services.excerpt_provenance import NATIVE_SECTION_KEYS
    from app.services.openai_service import openai_service
    floors, letters = runner.NATIVE_SECTION_FLOORS, {'financials': 'f', 'mda': 'm', 'risk': 'r'}
    assert tuple(floors) == NATIVE_SECTION_KEYS

    def read_as_its_own(lengths):
        sections = {key: letters[key] * length for key, length in lengths.items()}
        excerpt = openai_service.assemble_excerpt_from_sections(sections, form, filing_text='<p>The document.</p>')
        return {'financials': 'FINANCIAL STATEMENTS CONTEXT (recovered from filing)' not in excerpt,
                'mda': 'MD&A CONTEXT (recovered from filing)' not in excerpt,
                'risk': letters['risk'] * lengths['risk'] in excerpt}

    assert read_as_its_own(floors) == dict.fromkeys(floors, True)
    for key, floor in floors.items():
        assert read_as_its_own({**floors, key: floor - 1}) == {other: other != key for other in floors}, key


def test_the_runner_imports_no_settings_before_main_sets_its_database():
    # main() points DATABASE_URL at the prepared database after the preflight; a module the runner imports, or its
    # __main__ prelude (ai_metrics.set_trigger), that built Settings first (app.config) would bind the default database
    # instead, and every row would error. The runner runs as __main__, prelude and all, and main() stops at its
    # argument parser (no --preparation) before it sets anything; the modules are listed only once main() has stopped
    # there, so a prelude that never reaches main() prints nothing and fails.
    import subprocess
    import sys
    code = ('import runpy, sys\nsys.argv = ["copilot_runner"]\n'
            'try:\n    runpy.run_module("evals.copilot_runner", run_name="__main__")\n'
            'except SystemExit as stop:\n    assert stop.code == 2, stop.code\n'
            '    print(sorted(m for m in sys.modules if m in ("app.config", "app.database")))')
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(runner.__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '[]'


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
    import sqlite3
    from contextlib import closing
    cases = runner._load_cases(runner.GOLDEN_PATH)
    db = tmp_path/'prepared-source.db'
    # The prepared database's tables the preflight reads the Copilot's excerpt from, each case's excerpt in them.
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute('CREATE TABLE filings (id INTEGER PRIMARY KEY, accession_number TEXT)')
        connection.execute('CREATE TABLE filing_content_cache (filing_id INTEGER PRIMARY KEY, critical_excerpt TEXT)')
        for number, c in enumerate(cases, 1):
            connection.execute('INSERT INTO filings VALUES (?, ?)', (number, c.accession_number))
            connection.execute('INSERT INTO filing_content_cache VALUES (?, ?)',
                               (number, f'excerpt of {c.accession_number}'))
    sources = []
    for c in cases:
        folder = tmp_path/c.accession_number
        folder.mkdir()
        artifacts = {}
        native = c.excerpt_source['outcome'] == 'native'
        for kind,filename in {'html':'filing.html','xbrl':'xbrl.json','sections':'sections.json','excerpt':'excerpt.txt'}.items():
            artifact = folder/filename
            # Distinct bytes per artifact, so a hash bound to the wrong one fails. A filing declared to fall back
            # (ASML) had no section mapping: the preparation writes JSON null.
            artifact.write_text('null' if kind == 'sections' and not native else f'{kind} of {c.accession_number}')
            artifacts[kind] = {'path':str(artifact),'relative_path':c.accession_number+'/'+filename,
                               'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
        # The builder's record of the declared excerpt source over these very artifacts (excerpt_provenance, E80-C1):
        # each declared section at its native floor, any other a stub just under it (as BABA's financials are).
        declared = c.excerpt_source.get('sections', [])
        supplied = [{'key':key,'supplied_chars':floor if key in declared else floor - 1}
                    for key,floor in runner.NATIVE_SECTION_FLOORS.items()] if native else []
        record = {'schema_version':2,'accession':c.accession_number,'filing_type':c.filing_type,
                  'source':'edgartools' if native else 'regex_fallback',
                  'outcome':c.excerpt_source['outcome'],'fallback_reason':c.excerpt_source.get('fallback_reason'),
                  'document_sha256':artifacts['html']['sha256'],
                  'sections_sha256':artifacts['sections']['sha256'] if native else None,
                  'excerpt_sha256':artifacts['excerpt']['sha256'],
                  'supplied_sections':supplied,'missing_sections':[] if native else ['financials','mda','risk']}
        sources.append({'status':'complete','accession_number':c.accession_number,
                        'reporting_currency':c.reporting_currency,'artifacts':artifacts,'excerpt_provenance':record})
    data = {'status':'complete','errors':[],
        'source_manifest_sha256':hashlib.sha256(runner.SOURCES_PATH.read_bytes()).hexdigest(),
        'database_path':str(db),'database_artifact_path':'prepared-source.db',
        'database_sha256':hashlib.sha256(db.read_bytes()).hexdigest(),
        'planned_accessions':[c.accession_number for c in cases], 'sources': sources}
    return cases,data


def _fallback_source(data, cases):
    """The prepared source of the cohort's one filing declared to fall back (ASML's 20-F)."""
    [case] = [c for c in cases if c.excerpt_source['outcome'] == 'fallback']
    return next(s for s in data['sources'] if s['accession_number'] == case.accession_number)


# Each damage to a prepared source, and what its refusal names: the field, the section and its length, or the recorded
# and the declared source, outcome and reason, never a hash or text.
SOURCE_DAMAGES = {
    'status': 'source preparation incomplete', 'manifest': 'source manifest differs', 'cohort': 'cohort incomplete',
    'database': 'prepared database changed', 'artifact': 'artifact changed or missing', 'currency': 'currency differs',
    'database_unreadable': 'prepared scratch database is unreadable',
    'database_excerpt': 'prepared critical_excerpt: ', 'database_excerpt_null': 'prepared critical_excerpt: ',
    'undeclared_case': 'golden case declares no valid excerpt source',
    'no_provenance': 'excerpt provenance unavailable', 'schema_1': 'excerpt provenance unavailable',
    'another_filing': 'prepared accession: ', 'filing_type': 'prepared filing_type: ',
    'document_hash': 'prepared document_sha256: ', 'provenance_hash': 'prepared sections_sha256: ',
    'unset_sections_hash': 'prepared sections_sha256: ', 'fallback_sections_hashed': 'prepared sections_sha256: ',
    'excerpt_hash': 'prepared excerpt_sha256: ', 'cached': 'prepared document_sha256, sections_sha256: ',
    'fallback':
        r'excerpt source edgartools fallback \(sections_not_supplied\) is not the declared native \(None\) from edgartools',
    'source_disagrees': r'excerpt source regex_fallback native \(None\) is not the declared native \(None\) from edgartools',
    'declared_fallback_native':
        r'excerpt source regex_fallback native \(None\) is not the declared fallback \(sections_not_supplied\) from regex_fallback',
    'other_fallback_reason': r'native_excerpt_thin\) is not the declared fallback \(sections_not_supplied\)',
    'coverage_absent': 'records no valid section coverage', 'coverage_none': 'records no valid section coverage',
    'coverage_string': 'records no valid section coverage', 'supplied_absent': 'records no valid section coverage',
    'supplied_chars_text': 'records no valid section coverage',
    'supplied_chars_bool': 'records no valid section coverage',
    'supplied_duplicate': 'records no valid section coverage',
    'supplied_entry_text': 'records no valid section coverage',
    'supplied_unknown_key': 'records no valid section coverage', 'missing_unknown_key': 'records no valid section coverage',
    'fallback_coverage_none': 'records no valid section coverage',
    'declared_section_missing': r'under the native floor \(risk missing\)',
    'declared_section_unsupplied': r'under the native floor \(risk missing\)',
    'declared_section_stub': r'under the native floor \(mda 2999/3000\)',
    'declared_sections_stub': r'under the native floor \(financials 0/5000, mda 2999/3000\)',
}


# The damages to the preparation as a whole name no source; the declared fallback's name ASML's accession, and the
# rest the first source's (AAPL's).
WHOLE_PREPARATION = {'status', 'manifest', 'cohort', 'database', 'database_unreadable', 'artifact', 'currency'}
FALLBACK_SOURCE = {'declared_fallback_native', 'other_fallback_reason', 'fallback_sections_hashed',
                   'fallback_coverage_none'}


@pytest.mark.parametrize('damage,refusal', SOURCE_DAMAGES.items(), ids=SOURCE_DAMAGES)
def test_preparation_integrity_is_checked_before_any_provider(damage,refusal,tmp_path):
    import hashlib
    import sqlite3
    from contextlib import closing
    cases,data = preparation(tmp_path)
    path = tmp_path/'preparation.json'
    path.write_text(json.dumps(data))
    assert runner.validate_preparation(path,cases)['status'] == 'complete'
    record = data['sources'][0]['excerpt_provenance']
    database = Path(data['database_path'])
    if damage == 'schema_1':
        record['schema_version'] = 1
    elif damage == 'another_filing':
        record['accession'] = data['sources'][1]['accession_number']
    elif damage == 'filing_type':
        record['filing_type'] = '10-Q'
    elif damage == 'document_hash':
        record['document_sha256'] = '0'*64
    elif damage == 'excerpt_hash':
        record['excerpt_sha256'] = '0'*64
    elif damage == 'unset_sections_hash':
        record['sections_sha256'] = None  # sections were supplied and hashed, so an unset hash names no input
    elif damage == 'cached':
        record.update(outcome='cached', fallback_reason=None, document_sha256=None, sections_sha256=None,
                      missing_sections=None)
    elif damage == 'source_disagrees':
        record['source'] = 'regex_fallback'
    elif damage == 'coverage_absent':
        record.pop('missing_sections')
    elif damage == 'coverage_none':
        record['missing_sections'] = None  # read as "nothing missing", it would accept any coverage
    elif damage == 'coverage_string':
        record['missing_sections'] = 'risk'  # read as a set, its letters name no section
    elif damage == 'supplied_absent':
        record.pop('supplied_sections')
    elif damage == 'supplied_chars_text':
        record['supplied_sections'][0]['supplied_chars'] = '60874'
    elif damage == 'supplied_chars_bool':
        record['supplied_sections'][0]['supplied_chars'] = True
    elif damage == 'supplied_duplicate':
        record['supplied_sections'].append(dict(record['supplied_sections'][1]))
    elif damage == 'supplied_entry_text':
        record['supplied_sections'][0] = 'financials'  # an entry that is not a mapping
    elif damage == 'supplied_unknown_key':
        record['supplied_sections'].append({'key': 'notes', 'supplied_chars': 9999})
    elif damage == 'missing_unknown_key':
        record['missing_sections'] = ['notes']
    elif damage == 'fallback_coverage_none':
        _fallback_source(data, cases)['excerpt_provenance']['missing_sections'] = None  # a fallback's coverage too
    elif damage == 'declared_section_missing':
        record['missing_sections'] = ['risk']
    elif damage == 'declared_section_unsupplied':
        record['supplied_sections'] = record['supplied_sections'][:2]  # risk neither supplied nor named missing
    elif damage == 'declared_section_stub':
        record['supplied_sections'][1]['supplied_chars'] = 2999  # MD&A one character under the assembler's floor
    elif damage == 'declared_sections_stub':
        record['supplied_sections'][0]['supplied_chars'] = 0
        record['supplied_sections'][1]['supplied_chars'] = 2999
    elif damage == 'declared_fallback_native':
        _fallback_source(data, cases)['excerpt_provenance'].update(outcome='native', fallback_reason=None)
    elif damage == 'other_fallback_reason':
        _fallback_source(data, cases)['excerpt_provenance']['fallback_reason'] = 'native_excerpt_thin'
    elif damage == 'fallback_sections_hashed':
        # The declared fallback's record names no sections, but sections were prepared for it.
        source = _fallback_source(data, cases)
        sections = Path(source['artifacts']['sections']['path'])
        sections.write_text('{"mda": "text"}')
        source['artifacts']['sections']['sha256'] = hashlib.sha256(sections.read_bytes()).hexdigest()
    elif damage == 'database_excerpt':
        # The text the run hands the Copilot is not the excerpt the builder recorded and the preparation kept.
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("UPDATE filing_content_cache SET critical_excerpt = 'other bytes' WHERE filing_id = 1")
        data['database_sha256'] = hashlib.sha256(database.read_bytes()).hexdigest()
    elif damage == 'database_excerpt_null':
        # A filing whose prepared excerpt is NULL: the run would hand the Copilot no excerpt at all.
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("UPDATE filing_content_cache SET critical_excerpt = NULL WHERE filing_id = 1")
        data['database_sha256'] = hashlib.sha256(database.read_bytes()).hexdigest()
    elif damage == 'database_unreadable':
        database.write_bytes(b'not a database')
        data['database_sha256'] = hashlib.sha256(database.read_bytes()).hexdigest()
    elif damage == 'undeclared_case':
        cases[0].excerpt_source = {}
    elif damage == 'status':
        data['status'] = 'unavailable'
    elif damage == 'manifest':
        data['source_manifest_sha256'] = '0'*64
    elif damage == 'cohort':
        data['sources'].pop()
    elif damage == 'database':
        database.write_bytes(b'changed')
    elif damage == 'artifact':
        Path(data['sources'][0]['artifacts']['html']['path']).write_text('changed')
    elif damage == 'no_provenance':
        data['sources'][0].pop('excerpt_provenance')
    elif damage == 'fallback':
        record.update(outcome='fallback', fallback_reason='sections_not_supplied')
    elif damage == 'provenance_hash':
        record['sections_sha256'] = '0'*64
    else:
        assert damage == 'currency'
        data['sources'][0]['reporting_currency'] = 'EUR'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=refusal) as refused:
        runner.validate_preparation(path,cases)
    if damage not in WHOLE_PREPARATION:
        named = _fallback_source(data, cases) if damage in FALLBACK_SOURCE else data['sources'][0]
        assert str(refused.value).endswith(': ' + named['accession_number'])


def test_a_declared_thin_native_excerpt_is_accepted_on_the_record_that_names_it(tmp_path):
    # native_excerpt_thin: sections were supplied, but the native assembly was too thin, so the builder fell back with
    # the sections hashed. A case may declare it as its filing's own, and the record that names it then counts.
    import hashlib
    cases,data = preparation(tmp_path)
    [case] = [c for c in cases if c.excerpt_source['outcome'] == 'fallback']
    case.excerpt_source = {**case.excerpt_source, 'fallback_reason': 'native_excerpt_thin'}
    source = _fallback_source(data, cases)
    sections = Path(source['artifacts']['sections']['path'])
    sections.write_text('{"mda": "thin"}')
    source['artifacts']['sections']['sha256'] = hashlib.sha256(sections.read_bytes()).hexdigest()
    source['excerpt_provenance'].update(fallback_reason='native_excerpt_thin',
        sections_sha256=source['artifacts']['sections']['sha256'],
        supplied_sections=[{'key': 'mda', 'supplied_chars': 4}], missing_sections=['financials', 'risk'])
    path = tmp_path/'preparation.json'
    path.write_text(json.dumps(data))
    assert runner.validate_preparation(path, cases)['status'] == 'complete'


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
    replies = iter(['quotation', 'quotation', 'declaration'])
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
    assert [row['tool_trace']['withheld_reasons'] for row in rows[:2]] == [[F_REASON, F_REASON], ['Invalid citation declaration']]
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
    replies = iter(['quotation', 'quotation', 'crash'])
    async def stream(messages, tools, run_tool, **kwargs):
        if next(replies) == 'crash':
            raise RuntimeError('offline provider crash')
        yield reply('quotation')
    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    traces = [{}, {}]
    for trace in traces:
        with pytest.raises(ValueError, match='provider error event'):
            await runner._answer(sourced(), 'Describe the business.', trace=trace)
    assert [trace['withheld_reasons'] for trace in traces] == [[F_REASON, F_REASON], []]
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
