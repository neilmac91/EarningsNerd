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
    rendered = render_sections(raw['structured'])
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
