"""Selected-filing recovery context and actual offline SDK request contracts."""
import asyncio
from contextlib import asynccontextmanager
import json
import re
import threading
from unittest.mock import AsyncMock

import httpx2
from openai import AsyncOpenAI
import pytest

from app.services.ai import recovery_context as context
from app.services.ai import provider_requests
from app.services.openai_service import OpenAIService


@asynccontextmanager
async def native_service(handler):
    service = object.__new__(OpenAIService)
    service.model = 'deepseek-v4-pro'
    service.fallback_client = None
    service._task_models = {}
    service._model_overrides = {}
    service._recovery_semaphore = asyncio.Semaphore(1)
    async with AsyncOpenAI(api_key='offline', base_url='https://api.deepseek.com/v1', max_retries=0,
                           http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))) as client:
        service.client = client
        yield service


def response(payload):
    return httpx2.Response(200, json={'id': 'offline', 'object': 'chat.completion', 'created': 1,
        'model': 'deepseek-chat', 'choices': [{'index': 0, 'finish_reason': 'stop',
        'message': {'role': 'assistant', 'content': json.dumps(payload)}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}})


def test_plain_text_preserves_whitespace_and_comparators_without_html_parser(monkeypatch):
    monkeypatch.setattr(context, 'BeautifulSoup', lambda *a, **k: pytest.fail('plain source parsed'))
    source = ' \nRevenue < 5 and margin > 2.\n\t'
    assert context.clean_filing_source(source) == source


@pytest.mark.parametrize('hidden', ['<script>SECRET</script>', '<style>SECRET</style>',
    '<template>SECRET</template>', '<ix:hidden><b>SECRET</b></ix:hidden>', '<ix:header>SECRET</ix:header>',
    '<!--SECRET-->', '<span hidden>SECRET</span>', '<span style="display: none !important">SECRET</span>',
    '<span style="visibility:hidden; color:red">SECRET</span>'])
def test_explicit_hidden_markup_is_removed_without_losing_visible_source(hidden):
    cleaned = context.clean_filing_source('<div>VISIBLE $125 million</div>' + hidden)
    assert 'VISIBLE $125 million' in cleaned and 'SECRET' not in cleaned
    assert '<' not in cleaned and '>' not in cleaned


@pytest.mark.asyncio
async def test_failed_html_cleanup_cannot_reenter_raw_fallback_or_call_recovery(monkeypatch):
    monkeypatch.setattr(context, 'BeautifulSoup', lambda *a, **k: (_ for _ in ()).throw(ValueError('broken')))
    service = object.__new__(OpenAIService)
    monkeypatch.setattr(service, 'extract_critical_sections', lambda *a, **k: pytest.fail('raw fallback'))
    service._recovery_semaphore = asyncio.Semaphore(1)
    service._run_secondary_completion = AsyncMock(return_value=None)
    prepared = service._parse_and_clean_text('<p>RAW ONLY</p>', '10-Q')
    assert prepared['filing_sample'] == '' and prepared['recovery_sources'] == ()
    assert await service._recover_single_section('risks', '10-Q', (), '', {}) == ('risks', None)
    service._run_secondary_completion.assert_not_called()


@pytest.mark.parametrize('form', ['10-K', '10-Q', '20-F', '20-F/A'])
def test_actual_layout_labels_and_amendments_preserve_selected_families(form):
    service = object.__new__(OpenAIService)
    layout = service._SECTION_LAYOUT[form.removesuffix('/A')]
    sample = '\n\n'.join(f'{label}:\n{family} SENTINEL' for family, label, _ in layout)
    prepared = service._parse_and_clean_text('UNSELECTED RAW', form, sample)
    assert prepared['filing_sample'] == sample
    assert [(b.label, b.text, b.families) for b in prepared['recovery_sources']] == [
        (label, family + ' SENTINEL', (family,)) for family, label, _ in layout]


def test_recovered_labels_combined_windows_and_internal_source_are_preserved_once():
    labels = ['FINANCIAL STATEMENTS CONTEXT (recovered from filing)', 'MD&A CONTEXT (recovered from filing)',
              'FINANCIAL & MD&A CONTEXT (recovered from filing)', 'RISK & NARRATIVE CONTEXT (recovered from filing)']
    sample = '\n\n'.join(f'{label}:\nSOURCE{i}\n' + '='*50 + '\ncontiguous see Item 8 prose' for i, label in enumerate(labels))
    blocks = context.recovery_blocks(sample, ())
    assert [b.families for b in blocks] == [('financials',), ('mda',), ('financials', 'mda'), ('risk',)]
    assert all('='*50 + '\ncontiguous see Item 8 prose' in b.text for b in blocks)
    result = context.build_recovery_context('results_that_matter', blocks, sample)
    assert result.count('SOURCE2') == 1 and 'SOURCE0' in result and 'SOURCE1' in result and 'SOURCE3' not in result
    assert 'SOURCE2' in context.build_recovery_context('forward_signals', blocks, sample)
    assert 'SOURCE3' in context.build_recovery_context('risks', blocks, sample)


def test_family_budget_precedes_repeated_block_budget_and_is_exactly_bounded():
    blocks = (context.RecoveryBlock('Financial A', 'A'*40000, ('financials',)),
              context.RecoveryBlock('Financial B', 'B'*40000, ('financials',)),
              context.RecoveryBlock('Management', 'M'*40000, ('mda',)))
    result = context.build_recovery_context('results_that_matter', blocks, '')
    assert len(result) == 30000
    assert 7400 < result.count('A') < 7600 and 7400 < result.count('B') < 7600
    assert 14900 < result.count('M') < 15100
    assert result.index('Financial A:') < result.index('Financial B:') < result.index('Management:')


def test_short_family_releases_budget_and_label_heavy_family_keeps_body():
    blocks = (context.RecoveryBlock('Financial', 'SHORT', ('financials',)),
              context.RecoveryBlock('Management', 'M'*40000, ('mda',)))
    result = context.build_recovery_context('results_that_matter', blocks, '')
    assert len(result) == 30000 and result.count('M') > 29900
    crowded = tuple(context.RecoveryBlock('Financial '+str(i), f'BODY{i}', ('financials',)) for i in range(2000))
    result = context.build_recovery_context('results_that_matter', crowded + (blocks[1],), '')
    assert len(result) <= 30000 and 'Financial 0:\nB' in result and 'Management:\nM' in result
    assert result.count('M') > 14000
    headings = list(re.finditer(r'^([^:\n]+):\n', result, re.M))
    assert len(headings) > 2
    for index, heading in enumerate(headings):
        label = heading[1]
        end = headings[index + 1].start() if index + 1 < len(headings) else len(result)
        body = result[heading.end():end].strip('\n')
        assert body and (f'BODY{label.split()[-1]}'.startswith(body) if label.startswith('Financial ') else set(body) == {'M'})


def test_neutral_fallback_is_labelled_contiguous_and_empty_stays_empty():
    sample = 'unlabelled selected prose ' * 2000
    result = context.build_recovery_context('risks', (), sample)
    assert result == 'Filing excerpt:\n' + sample.strip()[:30000-len('Filing excerpt:\n')]
    assert context.build_recovery_context('risks', (), ' \n ') == ''


@pytest.mark.asyncio
@pytest.mark.parametrize('fallback', [False, True])
async def test_actual_critical_extractor_first_financial_block_reaches_native_recovery_request(fallback, monkeypatch):
    requests, calls = [], []
    def handler(req):
        requests.append(json.loads(req.content))
        return response({'results_that_matter': {'table': [{'metric': 'Revenue', 'current_period': '$125 million'}]}})
    monkeypatch.setattr(provider_requests, 'record_ai_call', lambda **kw: calls.append(kw) or kw)
    financial = ('CONSOLIDATED STATEMENTS OF OPERATIONS ' if fallback else 'ITEM 1.    FINANCIAL STATEMENTS\n')
    financial += 'FINANCIAL_SENTINEL Revenue $125 million ' + 'F'*40000
    raw = financial + "\nITEM 2.    MANAGEMENT'S DISCUSSION AND ANALYSIS\nMDA_SENTINEL " + 'M'*30000
    async with native_service(handler) as service:
        sample = service.extract_critical_sections(raw, '10-Q', cleaned_text=raw)
        label = 'FINANCIAL DATA' if fallback else 'ITEM 1 - FINANCIAL STATEMENTS'
        assert len(sample) > 60000 and 'recovered from filing' not in sample
        assert sample.startswith('\n\n' + '='*50 + label + ':\n')
        blocks = context.recovery_blocks(sample, service._SECTION_LAYOUT['10-Q'])
        key, value = await service._recover_single_section('results_that_matter', '10-Q', blocks, sample, {})
    assert key == 'results_that_matter' and value['table'][0]['current_period'] == '$125 million'
    prompt = requests[0]['messages'][1]['content']
    emitted = prompt.split('FILING EXCERPT:\n', 1)[1].split('\n\nReturn JSON', 1)[0]
    assert label + ':\n' in emitted and 'FINANCIAL_SENTINEL' in emitted and 'MDA_SENTINEL' in emitted
    assert len(emitted) == 30000 and emitted.count('M') > 14000
    assert requests[0]['max_tokens'] == 500 and requests[0]['temperature'] == .1
    assert calls[0]['operation'] == 'section_recovery' and calls[0]['usage'].total_tokens == 12


@pytest.mark.asyncio
async def test_primary_wire_preserves_plain_excerpt_and_prepares_context_off_loop(monkeypatch):
    requests, threads = [], []
    source = ' \nITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\nSELECTED $125 million\n\t'
    def handler(req):
        requests.append(json.loads(req.content))
        return response({'metadata': {}, 'sections': {}})
    original = OpenAIService._parse_and_clean_text
    def tracked(self, *args):
        threads.append(threading.get_ident())
        return original(self, *args)
    monkeypatch.setattr(OpenAIService, '_parse_and_clean_text', tracked)
    monkeypatch.setattr(context, 'BeautifulSoup', lambda *a, **k: pytest.fail('unselected raw parsed'))
    async with native_service(handler) as service:
        service._assemble_structured_summary = AsyncMock(return_value={'assembled': True})
        assert await service.generate_structured_summary('<div>UNSELECTED RAW</div>', 'Fixture', '10-K', filing_excerpt=source) == {'assembled': True}
        args = service._assemble_structured_summary.call_args.args
    assert threads and all(t != threading.get_ident() for t in threads)
    prompt = requests[0]['messages'][1]['content']
    assert 'CRITICAL FILING EXCERPTS:\n' + source in prompt and 'UNSELECTED RAW' not in prompt
    assert args[2] == source
    assert args[4] == (context.RecoveryBlock('ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA',
                                           'SELECTED $125 million', ('financials',)),)


@pytest.mark.asyncio
async def test_real_assembly_marks_recovered_sections_for_snap_exclusion():
    seen = []
    def handler(req):
        seen.append(json.loads(req.content))
        return response({'risks': [{'summary': 'Selected risk', 'supporting_evidence': 'SELECTED RISK', 'materiality': 'high'}]})
    async with native_service(handler) as service:
        service._find_empty_sections = lambda sections: ['risks']
        sample = 'ITEM 1A - RISK FACTORS:\nSELECTED RISK'
        blocks = context.recovery_blocks(sample, service._SECTION_LAYOUT['10-K'])
        result = await service._assemble_structured_summary('{"metadata":{},"sections":{}}', '10-K', sample, None, blocks)
    assert result.get('_recovered_sections') == ['risks']
    assert result['sections']['risks'][0]['supporting_evidence'] == 'SELECTED RISK'
    assert 'ITEM 1A - RISK FACTORS:\nSELECTED RISK' in seen[0]['messages'][1]['content']
