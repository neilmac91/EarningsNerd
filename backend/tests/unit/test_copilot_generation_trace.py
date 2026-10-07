"""A private evidence regeneration retains each physical candidate's evidence boundary."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services import copilot_service
from app.services.openai_service import STREAM_ACTIVITY_SENTINEL, STREAM_ERROR_SENTINEL
from evals import copilot_runner, copilot_scorers

SOURCE = 'The company sells products to retail and enterprise customers around the world.'
QUOTATION_REASON = 'Unsupported prose quotation: quotation_not_in_source'
DECLARATION_REASON = 'Invalid citation declaration'


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['rescued', 'rejected', 'provider_error'])
async def test_private_generations_keep_separate_evidence_boundaries(outcome, monkeypatch):
    """Drive the real service and report owner; no candidate may overwrite or absorb another."""
    def snapshot(case):
        return SimpleNamespace(
            company_id=1, accession_number=case.accession_number, filing_type=case.filing_type,
            period_of_report=date.fromisoformat(case.period_of_report), xbrl_data={},
            company=SimpleNamespace(ticker=case.ticker, name='Test Company'),
            content_cache=SimpleNamespace(critical_excerpt=SOURCE, markdown_content=None),
            document_url=None, sec_url=None,
        )

    monkeypatch.setattr(copilot_runner, '_snapshot_for_case', snapshot)
    monkeypatch.setattr(copilot_service.copilot_tools, 'run_tool',
                        lambda name, args, *a, **kw: {'concepts': ['revenue'], 'probe': args['probe']})
    monkeypatch.setattr(copilot_scorers, 'score_copilot_answer',
                        lambda *a, **kw: SimpleNamespace(to_dict=lambda: {'passed': True, 'gate_failures': []}))
    replies = []
    for generation in range(2):
        declaration = {'n': 7, 'excerpt': SOURCE, 'section': 'Business'}
        prose = ('The filing says "retail and wholesale customers in Europe" [7].'
                 if generation == 0 else 'The company serves retail customers [7].')
        if generation == 1 and outcome == 'rejected':
            declaration['n'] = '7'
        replies.append([] if generation == 1 and outcome == 'provider_error' else
                       [prose + '\n', '===CITATIONS===\n', json.dumps([declaration])])
    calls, closed = [], []
    activity = STREAM_ACTIVITY_SENTINEL + json.dumps({'name': 'list_available_concepts', 'phase': 'done'})

    async def stream(messages, tools, run_tool, **kwargs):
        call = len(calls)
        generation = call % 2
        calls.append(call)
        try:
            run_tool('list_available_concepts', {'probe': generation})
            # Tool rounds mutate live messages; retained input must remain the original snapshot.
            messages.append({'role': 'assistant', 'content': 'tool-round-mutation'})
            yield activity
            for delta in replies[generation]:
                yield delta
            if generation == 1 and outcome == 'provider_error':
                yield STREAM_ERROR_SENTINEL + 'private-provider-error-details'
        finally:
            closed.append(call)

    monkeypatch.setattr(copilot_service.openai_service, 'stream_chat_with_tools', stream)
    report = await copilot_runner.run()
    assert len(calls) == 36 and closed == calls
    assert copilot_service.openai_service.stream_chat_with_tools is stream
    assert report['summary']['errors'] == (0 if outcome == 'rescued' else 18)
    assert report['accepted'] is (outcome == 'rescued')
    for row in report['results']:
        trace = row['tool_trace']
        generations = trace['generation_attempts']
        assert [g['generation_index'] for g in generations] == [0, 1]
        assert [g['candidate_deltas'] for g in generations] == replies
        controls = [[{'type': 'activity'}], [{'type': 'activity'}] + (
            [{'type': 'error'}] if outcome == 'provider_error' else [])]
        assert [g['provider_controls'] for g in generations] == controls
        assert [g['tool_results'][0]['args'] for g in generations] == [{'probe': 0}, {'probe': 1}]
        assert [g['tool_results'][0]['result']['probe'] for g in generations] == [0, 1]
        reasons = [QUOTATION_REASON] + ([DECLARATION_REASON] if outcome == 'rejected' else [])
        assert trace['withheld_reasons'] == reasons
        assert [g['withheld_reasons'] for g in generations] == [
            [QUOTATION_REASON], [DECLARATION_REASON] if outcome == 'rejected' else [],
        ]
        assert trace['candidate_deltas'] == replies[0] + replies[1]
        assert trace['tool_results'] == generations[0]['tool_results'] + generations[1]['tool_results']
        assert trace['provider_controls'] == controls[0] + controls[1]
        assert trace['initial_messages'] == row['inputs']['initial_messages'] == generations[0]['initial_messages']
        assert trace['generation_options'] == generations[0]['generation_options']
        assert all(g['tool_schema'] == trace['tool_schema'] for g in generations)
        assert 'tool-round-mutation' not in json.dumps([g['initial_messages'] for g in generations])
        assert generations[1]['initial_messages'][0]['content'].endswith(copilot_service._EVIDENCE_RETRY_GUIDANCE)
        assert replies[0][0].strip() not in json.dumps(generations[1]['initial_messages'])
        if outcome == 'rejected':
            assert row['error']['withheld_reason'] == DECLARATION_REASON
        elif outcome == 'provider_error':
            assert 'withheld_reason' not in row['error']
            assert report['failures'] == ['operationally incomplete attempt']
        else:
            assert 'error' not in row and row['terminal_complete'] is True
    assert 'private-provider-error-details' not in json.dumps(report)
