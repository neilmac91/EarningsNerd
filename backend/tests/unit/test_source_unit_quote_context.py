"""One source-association invariant through final and preview v2 consumers; no provider calls."""
from copy import deepcopy
import json

import pytest

from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION

# Exact retained COST 10-Q text fragments, accession 0000909832-26-000051.
DECLARATION = '(amounts in millions, except per share, share, percentages and warehouse count data)'
TITLE = 'Item\xa02—Management’s Discussion and Analysis of Financial Condition and Results of Operations'
QUOTE = ('In the first thirty-six weeks of 2026, we spent $4,228 on capital expenditures, '
         'and it is our current intention to spend approximately $6,500 during fiscal 2026, '
         'as we continue to invest in new warehouse openings, remodel existing locations, '
         'expand our depot network, and further develop our digitally-enabled businesses.')
PARAGRAPH = ('Our primary requirements for capital are acquiring land, buildings, and equipment '
             'for new and remodeled warehouses, information systems, and manufacturing and '
             'distribution facilities. ' + QUOTE + ' These expenditures are expected to be financed '
             'with cash from operations, cash and cash equivalents, and ')
SOURCE = ("ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\nTable of Contents\n\n"
          + TITLE + '\n\n' + DECLARATION + '\n\nOVERVIEW\n\nCapital Expenditure Plans\n\n'
          + PARAGRAPH + '\n\n25\n\nshort-term investments.')


@pytest.mark.asyncio
@pytest.mark.parametrize('case', [
    'primary', 'duplicate', 'no_header', 'table_header', 'conflicting_scope',
    'wrong_section', 'recovered', 'preview', 'paraphrase', 'truncated',
])
async def test_source_units_belong_to_entire_quote_in_actual_consumer(monkeypatch, case):
    service = OpenAIService()
    source = SOURCE
    quote = QUOTE
    if case == 'duplicate':
        source += '\n\n' + QUOTE
    elif case == 'no_header':
        source = source.replace(DECLARATION, '')
    elif case == 'table_header':
        source = source.replace(TITLE, 'Capital expenditure table')
    elif case == 'conflicting_scope':
        source = source.replace('Capital Expenditure Plans', '(amounts in thousands)\n\nCapital Expenditure Plans')
    elif case == 'wrong_section':
        source = source.replace('Capital Expenditure Plans', "ITEM 1 - FINANCIAL STATEMENTS:\nCapital Expenditure Plans")
    elif case == 'paraphrase':
        quote = QUOTE.replace('current intention', 'present intention')
    elif case == 'truncated':
        source = source[:source.index('\n\n25')]
    item = {'speaker': 'Costco', 'quote': quote, 'context': 'Capital Expenditure Plans',
            'source_unit_context': '(fabricated amounts in billions)'}
    sections = {'forward_signals': {'guidance': 'Authored $6,500 guidance remains unchanged.', 'quotes': [item]}}
    structured = {'schema_version': SUMMARY_SCHEMA_VERSION, 'sections': deepcopy(sections), 'metadata': {}}
    if case == 'recovered':
        structured['_recovered_sections'] = ['forward_signals']

    async def generated(*args, **kwargs):
        return deepcopy(structured)

    monkeypatch.setattr(service, 'generate_structured_summary', generated)
    if case == 'preview':
        markdown = service._partial_markdown_preview(json.dumps(structured), None)
        assert markdown and 'Source units:' not in markdown
        assert 'fabricated amounts' not in markdown
        assert quote in markdown
        return

    result = await service.summarize_filing(source, 'Costco', '10-Q', filing_excerpt=source)
    raw = result['raw_summary']
    retained = raw['sections']['forward_signals']['quotes'][0]
    assert retained['quote'] == quote  # declaration must never be stitched into the quote
    assert raw['sections']['forward_signals']['guidance'] == sections['forward_signals']['guidance']
    # The orchestrator stamps this outer envelope before persistence (summary_pipeline).
    rendered = render_sections({**raw, 'schema_version': SUMMARY_SCHEMA_VERSION})
    markdown = sections_to_markdown(rendered)
    assert markdown == result['business_overview']
    assert 'fabricated amounts' not in markdown
    if case == 'primary':
        assert retained['source_unit_context'] == DECLARATION
        assert f'Source units: {DECLARATION}' in markdown
        assert markdown.index(DECLARATION) < markdown.index(quote)
        assert '$6,500' in markdown and '$4,228' in markdown
    else:
        assert 'source_unit_context' not in retained
        assert 'Source units:' not in markdown


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['old_quote_key', 'nested_marker', 'boolean_marker', 'new_envelope'])
async def test_only_code_owned_outer_envelope_authorizes_read_and_export(monkeypatch, case):
    from types import SimpleNamespace

    from app.services.export_service import ExportService
    from app.services.provenance_service import enrich_summary_provenance
    from app.services.summary_schema import SOURCE_UNIT_CONTEXT_KEY, SOURCE_UNIT_CONTEXT_VERSION

    quote = {'speaker': 'Costco', 'quote': QUOTE, 'source_unit_context': DECLARATION}
    sections = {'forward_signals': {'guidance': 'Authored guidance.', 'quotes': [quote]}}
    # Historical pipeline copied nested model objects but constructed the outer envelope itself.
    old = {'schema_version': SUMMARY_SCHEMA_VERSION, 'sections': sections,
           'structured': {'sections': deepcopy(sections)}}
    if case == 'nested_marker':
        old['structured'][SOURCE_UNIT_CONTEXT_KEY] = SOURCE_UNIT_CONTEXT_VERSION
        quote[SOURCE_UNIT_CONTEXT_KEY] = SOURCE_UNIT_CONTEXT_VERSION
    elif case == 'boolean_marker':
        old[SOURCE_UNIT_CONTEXT_KEY] = True  # equality to integer 1 must not confer eligibility
    raw = old
    if case == 'new_envelope':
        service = OpenAIService()

        async def generated(*args, **kwargs):
            return {'sections': deepcopy(sections), 'metadata': {}, SOURCE_UNIT_CONTEXT_KEY: 999}

        monkeypatch.setattr(service, 'generate_structured_summary', generated)
        result = await service.summarize_filing(SOURCE, 'Costco', '10-Q', filing_excerpt=SOURCE)
        raw = result['raw_summary']
        # The actual orchestrator's existing outer schema stamp, not a changed rollout policy.
        raw['schema_version'] = SUMMARY_SCHEMA_VERSION
        assert raw[SOURCE_UNIT_CONTEXT_KEY] == SOURCE_UNIT_CONTEXT_VERSION
        assert SOURCE_UNIT_CONTEXT_KEY not in raw['structured']
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview='',
                              financial_highlights={}, risk_factors=[], management_discussion='',
                              key_changes='', schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name='Costco'), filing_type='10-Q',
                             filing_date=None, period_end_date=None, sec_url='', document_url='',
                             content_cache=SimpleNamespace(critical_excerpt=SOURCE))
    web = json.dumps(enrich_summary_provenance(summary, filing)['rendered_sections'])
    exporter = ExportService()
    pdf = exporter.generate_pdf_html(summary, filing)
    csv = exporter.generate_csv(summary, filing)
    markdown = sections_to_markdown(render_sections(raw))
    for displayed in (web, pdf, csv, markdown):
        assert ('Source units:' in displayed) is (case == 'new_envelope')
    assert raw['sections']['forward_signals']['quotes'][0]['quote'] == QUOTE
