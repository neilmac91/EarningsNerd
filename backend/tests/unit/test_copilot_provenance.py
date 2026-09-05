"""Viewed-accession and explicit currency boundaries, using the real service closure."""
from copy import deepcopy
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
        accession_number=ACC, period_of_report='2025-03-31', document_url='https://www.sec.gov/viewed',
        sec_url=None, xbrl_data={'reporting_currency': 'RMB'},
        content_cache=SimpleNamespace(critical_excerpt='Selected filing source.', markdown_content=None),
        company=SimpleNamespace(name='Alibaba', ticker='BABA'))


@pytest.mark.parametrize('claim', [
    'Revenue USD 996.347 billion', 'Revenue $996.347B', 'Revenue US$996.347B',
    'Revenue 996.347 billion U.S. dollars', 'Revenue US dollars 996.347 billion',
    'Revenue 996.347 billion euros', 'Revenue EUR 996.347 billion',
])
def test_currency_contradiction_strips_actual_resolved_chip(claim):
    answer, citations, grounded, stripped = service._resolve_citations(
        claim + ' [F1]', {}, [fact(_marker='F1')], 'https://www.sec.gov/viewed')
    assert '[F1]' not in answer and '[1]' not in answer
    assert citations == [] and grounded == 0 and stripped == 1


@pytest.mark.parametrize('unit,label', [('CNY','RMB'), ('CNY','renminbi'), ('CNY','Chinese yuan'),
    ('TWD','NT$'), ('HKD','HK$'), ('USD','US$'), ('EUR','euros'), ('CNY','')])
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
    original.period_of_report = '2026-03-31'
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
