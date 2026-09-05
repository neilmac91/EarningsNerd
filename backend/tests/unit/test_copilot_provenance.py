"""Viewed-accession and explicit currency boundaries, using the real service closure."""
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import copilot_service as service

ACC = '0000950170-25-090161'
OTHER = '0001193125-26-231755'


def fact(**changes):
    return {'concept': 'revenue', 'raw_tag': 'ifrs-full:Revenue', 'value': 996347000000,
            'unit': 'CNY', 'accession': ACC, 'period_start': None,
            'period_end': '2025-03-31', 'fiscal_year': 2025, 'fiscal_period': 'FY', **changes}


def filing():
    return SimpleNamespace(id=7, company_id=9, filing_type='20-F', filing_date=None,
        accession_number=ACC, period_end_date=datetime(2025,3,31), period_of_report='2025-03-31', document_url='https://www.sec.gov/viewed',
        sec_url=None, xbrl_data={'reporting_currency': 'RMB'},
        content_cache=SimpleNamespace(critical_excerpt='Selected filing source.', markdown_content=None),
        company=SimpleNamespace(name='Alibaba', ticker='BABA'))


@pytest.mark.parametrize('claim', [
    'Revenue USD 996.347 billion', 'Revenue $996.347B', 'Revenue US$996.347B',
    'Revenue 996.347 billion U.S. dollars', 'Revenue US dollars 996.347 billion',
    'Revenue 996.347 billion euros', 'Revenue EUR 996.347 billion',
    'Revenue USD **996.347 billion**', 'Revenue 996.347 billion **USD**',
    'Revenue USD `996.347 billion`',
])
def test_currency_contradiction_strips_actual_resolved_chip(claim):
    answer, citations, grounded, stripped = service._resolve_citations(
        claim + ' [F1]', {}, [fact(_marker='F1')], 'https://www.sec.gov/viewed')
    assert '[F1]' not in answer and '[1]' not in answer
    assert citations == [] and grounded == 0 and stripped == 1


@pytest.mark.parametrize('unit,label', [('CNY','RMB'), ('CNY','renminbi'), ('CNY','Chinese yuan'),
    ('CNY','**RMB**'), ('TWD','NT$'), ('HKD','HK$'), ('USD','US$'), ('EUR','euros'), ('CNY','')])
def test_matching_alias_or_absent_currency_keeps_chip(unit, label):
    value = fact(unit=unit, _marker='F1')
    _, cites, grounded, stripped = service._resolve_citations(
        f'Revenue {label}996.347 billion [F1]', {}, [value], 'https://www.sec.gov/viewed')
    assert len(cites) == grounded == 1 and stripped == 0
    assert cites[0]['unit'] == unit


@pytest.mark.parametrize('change', [
    {'accession': OTHER}, {'accession': None}, {'value': None}, {'value': True},
    {'value': float('nan')}, {'unit': None}, {'unit': 'USD'}, {'raw_tag': ''},
    {'concept': ''}, {'period_end': 'invalid'}, {'period_start': '2026-01-01'},
    {'kind': 'invented'},
])
@pytest.mark.asyncio
async def test_real_closure_rejects_bad_provenance_before_marker(monkeypatch, change):
    observed = []
    monkeypatch.setattr(service.copilot_tools, 'run_tool', lambda *a, **kw: fact(**change))
    async def stream(messages, tools, run_tool, **kwargs):
        observed.append(run_tool('get_financial_fact', {'concept': 'revenue', 'accession_number': OTHER}))
        yield 'Revenue was 996.347 billion [F1].'
    monkeypatch.setattr(service.openai_service, 'stream_chat_with_tools', stream)
    events = [e async for e in service.answer_filing_question(filing=filing(), question='Revenue?')]
    assert observed == [{'error': 'invalid_filing_provenance'}]
    final = [e for e in events if e['type'] == 'complete']
    assert len(final) == 1 and final[0]['citations'] == []


@pytest.mark.asyncio
async def test_snapshot_trusted_scope_and_currency_survive_context_cap(monkeypatch):
    original = filing()
    snap = service.snapshot_filing(original)
    original.accession_number = OTHER
    original.period_end_date = datetime(2026,3,31)
    observed = []
    def lookup(name, args, company_id, **scope):
        observed.append((company_id, scope))
        return fact()
    monkeypatch.setattr(service.copilot_tools, 'run_tool', lookup)
    monkeypatch.setattr(service.settings, 'COPILOT_CONTEXT_CHAR_CAP', 1)
    async def stream(messages, tools, run_tool, **kwargs):
        content = '\n'.join(m['content'] for m in messages)
        assert ACC in content and '2025-03-31' in content and 'CNY' in content
        result = run_tool('get_financial_fact', {'accession_number': OTHER})
        assert result['cite'] == 'F1'
        yield 'Revenue was RMB996.347 billion [F1].'
    monkeypatch.setattr(service.openai_service, 'stream_chat_with_tools', stream)
    events = [e async for e in service.answer_filing_question(filing=snap, question='Revenue?')]
    assert observed == [(9, {'accession_number': ACC, 'reporting_currency': 'CNY'})]
    final = next(e for e in events if e['type'] == 'complete')
    assert final['citations'][0]['accession'] == ACC
    assert snap.period_of_report == '2025-03-31'


def test_derived_operand_origin_and_identity_are_not_hidden_by_top_level():
    operands = [fact(concept='gross_profit', value=10), fact(value=20)]
    derived = fact(concept='gross_profit', value=.5, unit='pure', kind='margin', source_facts=operands)
    assert service._valid_fact_provenance(derived, ACC, 'CNY')
    for bad in ([], operands[:1], [operands[0], fact(accession=OTHER)],
                [operands[0], fact(unit='USD')], [operands[0], fact(value=None)]):
        assert not service._valid_fact_provenance({**derived, 'source_facts': bad}, ACC, 'CNY')
    altered = deepcopy(derived)
    altered['source_facts'][1]['concept'] = 'total_assets'
    assert service._fact_identity(derived) != service._fact_identity(altered)
    assert service._fact_identity(derived) == service._fact_identity(deepcopy(derived))


@pytest.mark.asyncio
async def test_actual_closure_distinguishes_denominators_and_reuses_exact_expression(monkeypatch):
    numerator = fact(concept='gross_profit', value=10, period_start='2024-04-01')
    denominator = fact(value=20, period_start='2024-04-01')
    first = fact(concept='gross_profit', value=.5, unit='pure', kind='margin',
                 source_facts=[numerator, denominator])
    second = deepcopy(first)
    second['source_facts'][1]['concept'] = 'total_assets'
    replies = iter([first, second, first])
    monkeypatch.setattr(service.copilot_tools, 'run_tool', lambda *a, **kw: deepcopy(next(replies)))
    markers = []
    async def stream(messages, tools, run_tool, **kwargs):
        for _ in range(3):
            markers.append(run_tool('compute_metric', {'kind': 'margin'})['cite'])
        yield 'Gross margin was 50% [F1]. Gross margin was 50% [F2]. Again gross margin 50% [F1].'
    monkeypatch.setattr(service.openai_service, 'stream_chat_with_tools', stream)
    final = [e async for e in service.answer_filing_question(filing=filing(), question='Margins?')][-1]
    assert markers == ['F1', 'F2', 'F1']
    assert len(final['citations']) == 2
    assert [c['source_facts'][1]['concept'] for c in final['citations']] == ['revenue', 'total_assets']


@pytest.mark.asyncio
async def test_native_sdk_tool_wire_carries_viewed_scope_and_currency(monkeypatch):
    import json
    import httpx2
    from tests.unit.test_provider_resilience import service_for, chunk, event
    requests, lookups = [], []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            data = chunk(choices=[{'index': 0, 'delta': {'tool_calls': [
                {'index': 0, 'id': 'native1', 'type': 'function', 'function': {
                    'name': 'get_financial_fact', 'arguments': json.dumps({'concept': 'revenue', 'accession_number': OTHER})}}]},
                'finish_reason': 'tool_calls'}])
        else:
            data = chunk('Revenue was RMB996.347 billion [F1].')
        return httpx2.Response(200, headers={'content-type': 'text/event-stream'},
                               content=event(data) + b'data: [DONE]\n\n')
    def lookup(name, args, company_id, **scope):
        lookups.append((name, company_id, scope))
        return fact()
    monkeypatch.setattr(service.copilot_tools, 'run_tool', lookup)
    async with service_for(handler) as sdk_service:
        monkeypatch.setattr(service, 'openai_service', sdk_service)
        final = [e async for e in service.answer_filing_question(filing=filing(), question='Revenue?')][-1]
    assert len(requests) == 2
    context = '\n'.join(m['content'] for m in requests[0]['messages'])
    assert ACC in context and 'CNY' in context and '2025-03-31' in context
    assert lookups == [('get_financial_fact', 9, {'accession_number': ACC, 'reporting_currency': 'CNY'})]
    wire_fact = json.loads(requests[1]['messages'][-1]['content'])
    assert wire_fact['accession'] == ACC and wire_fact['unit'] == 'CNY' and wire_fact['cite'] == 'F1'
    assert final['type'] == 'complete' and final['citations'][0]['accession'] == ACC


def test_real_orm_snapshot_retains_period_and_sources_after_expiry_and_close(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, joinedload
    from app.models import Base, Company, Filing, FilingContentCache
    engine = create_engine('sqlite:///' + str(tmp_path/'snapshot.db'))
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            company = Company(cik='1577552', ticker='BABA', name='Alibaba')
            row = Filing(company=company, accession_number=ACC, filing_type='20-F',
                filing_date=datetime(2025,6,26), period_end_date=datetime(2025,3,31),
                document_url='https://www.sec.gov/Archives/edgar/data/1577552/000095017025090161/baba-20250331.htm',
                sec_url='https://www.sec.gov/Archives/edgar/data/1577552/000095017025090161/',
                xbrl_data={'reporting_currency':'CNY'})
            row.content_cache = FilingContentCache(critical_excerpt='Exact selected text.')
            db.add(row)
            db.commit()
            loaded = db.query(Filing).options(joinedload(Filing.company), joinedload(Filing.content_cache)).one()
            snap = service.snapshot_filing(loaded)
            db.expire_all()
        assert snap.period_of_report == '2025-03-31' and snap.accession_number == ACC
        assert snap.company.ticker == 'BABA' and snap.content_cache.critical_excerpt == 'Exact selected text.'
        context = service._build_context_message(snap, snap.content_cache.critical_excerpt)
        assert 'REPORT PERIOD: 2025-03-31' in context and 'CNY' in context
    finally:
        engine.dispose()
