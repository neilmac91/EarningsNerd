"""Complete retained audited source, with identity and preservation counterexamples."""
import copy

from lxml import html
import pytest

from app.services.edgar.statement_disclosures import extract_statement_disclosures
from tests.unit.test_statement_relationship_source import original, SOURCES


def document():
    return html.fromstring(original('meli'))


def extract(root, **changes):
    args = dict(accession=SOURCES['meli'][0], document_url='https://example.test/selected.htm',
                report_period='2025-12-31', source_sha256=SOURCES['meli'][1],
                entity_identifier='0001099590')
    args.update(changes)
    return extract_statement_disclosures(root, **args)


def node(root, ident):
    return root.xpath('//*[@id=$ident]', ident=ident)[0]


def test_original_audited_tax_and_complete_presentation_disclosure():
    result = extract(document())
    tax = result['tax_disclosure']
    assert tax['source_sha256'] == SOURCES['meli'][1]
    assert tax['root_concept'] == 'us-gaap:IncomeTaxDisclosureTextBlock'
    assert tax['columns'][0]['rows'][5]['fact_id'] == 'f-1947'
    assert tax['columns'][0]['rows'][5]['value'] == -469_000_000
    assert tax['columns'][0]['rows'][5]['period_start'] == '2025-01-01'
    assert tax['columns'][1]['rows'][5]['value'] == -243_000_000
    assert tax['columns'][2]['rows'][5]['value'] == -284_000_000
    assert tax['text'].startswith('Income-tax disclosure, year ended 2025-12-31 (USD millions): '
                           'current income tax expense/(benefit) 1,314; '
                           'deferred income tax expense/(benefit) (469); '
                           'income tax expense/(benefit) 845.')
    assert 'Prior-year income tax expense/(benefit), 2024: 521.' in tax['text']
    assert 'increased from 21.4 % to 29.7 %' in tax['rate_note']['text']
    assert {r['period_end'] for r in tax['rate_note']['facts']} == {'2024-12-31', '2025-12-31'}
    note = result['presentation_disclosure']
    assert note['heading'] == 'Reclassification of 2023 results'
    assert len(note['paragraphs']) == 2
    assert '2023 results have been reclassified' in note['paragraphs'][0]
    assert note['paragraphs'][1] == ('This reclassification did not have an impact on previously reported '
                                     'net income, earnings per share, retained earnings or other '
                                     'components of equity or total equity.')
    assert note['root_id'] == 'f-483'
    assert 'operating' not in tax['text'].lower()


@pytest.mark.parametrize('change', [
    'wrong_sign', 'wrong_scale', 'quarter_duration', 'wrong_entity', 'wrong_currency',
    'wrong_column', 'missing_fact', 'duplicate_fact', 'wrong_component',
    'broken_chain', 'cyclic_chain', 'duplicate_root', 'missing_paragraph',
    'oversize_paragraph', 'extra_paragraph', 'incomplete_paragraph',
    'next_continuation_caveat', 'missing_following_boundary', 'shared_continuation',
    'changed_heading_malformed_supported_table',
])
def test_uncertain_present_disclosure_refuses_ownership(change):
    root = document()
    fact = node(root, 'f-1947')
    if change == 'changed_heading_malformed_supported_table':
        node(root, 'f-1930').text = 'Taxation'
        fact.set('scale', '3')
    elif change == 'wrong_sign':
        fact.attrib.pop('sign')
    elif change == 'wrong_scale':
        fact.set('scale', '3')
    elif change == 'quarter_duration':
        context = node(root, 'c-1')
        next(n for n in context.iter() if str(n.tag).endswith('startdate')).text = '2025-10-01'
    elif change == 'wrong_entity':
        context = node(root, 'c-1')
        next(n for n in context.iter() if str(n.tag).endswith('identifier')).text = '0000000001'
    elif change == 'wrong_currency':
        next(n for n in node(root, 'usd').iter() if str(n.tag).endswith('measure')).text = 'iso4217:EUR'
    elif change == 'wrong_column':
        fact.set('contextref', 'c-16')
    elif change == 'missing_fact':
        fact.getparent().remove(fact)
    elif change == 'duplicate_fact':
        fact.getparent().append(copy.deepcopy(fact))
    elif change == 'wrong_component':
        node(root, 'f-1944').text = '539'
    elif change == 'broken_chain':
        node(root, 'f-1930').set('continuedat', 'missing')
    elif change == 'cyclic_chain':
        node(root, 'f-1930-1').set('continuedat', 'f-1930-1')
    elif change == 'duplicate_root':
        source = node(root, 'f-1930')
        source.getparent().append(copy.deepcopy(source))
    elif change == 'shared_continuation':
        unrelated = html.Element('div', id='unrelated-disclosure', continuedat='f-483-3')
        unrelated.text = 'An unrelated disclosure.'
        root.append(unrelated)
    elif change == 'next_continuation_caveat':
        continuation = node(root, 'f-483-4')
        caveat = html.Element('div')
        caveat.text = 'However, these statements exclude another material presentation adjustment.'
        continuation.insert(0, caveat)
    elif change == 'missing_following_boundary':
        node(root, 'f-483-3').attrib.pop('continuedat')
    else:
        continuation = node(root, 'f-483-3')
        paragraphs = list(continuation)
        last = paragraphs[-1]
        if change == 'missing_paragraph':
            continuation.remove(last)
        elif change == 'extra_paragraph':
            continuation.append(copy.deepcopy(last))
        elif change == 'oversize_paragraph':
            span = last.xpath('.//span')[0]
            span.text = (span.text or '') + 'x' * 1600
        elif change == 'incomplete_paragraph':
            span = last.xpath('.//span')[-1]
            span.text = (span.text or '').rstrip('.')
    assert extract(root) is None


def test_absent_supported_roots_is_explicitly_unavailable_without_invented_disclosure():
    result = extract(html.fromstring('<html><body><p>No supported audited source.</p></body></html>'))
    assert result == {'tax_disclosure': None, 'presentation_disclosure': None,
                      'status': {'tax_disclosure': 'no_supported_root', 'presentation_disclosure': 'no_supported_root'}}


def test_matching_cash_flow_number_cannot_replace_missing_tax_table():
    root = document()
    tax_fact = node(root, 'f-1947')
    table = next(p for p in tax_fact.iterancestors() if p.tag == 'table')
    table.getparent().remove(table)
    assert '(469)' in ' '.join(root.text_content().split())
    assert extract(root) is None


@pytest.mark.parametrize('changes', [
    {'report_period': '2024-12-31'}, {'entity_identifier': ''}, {'source_sha256': ''},
])
def test_missing_or_conflicting_supplied_identity_abstains(changes):
    assert extract(document(), **changes) is None


def test_actual_se_other_tax_layout_and_no_reclassification_subsection_are_unavailable():
    root = html.fromstring(original('se'))
    result = extract_statement_disclosures(
        root, accession=SOURCES['se'][0], document_url='https://example.test/se.htm',
        report_period='2025-12-31', source_sha256=SOURCES['se'][1],
        entity_identifier='0001703399',
    )
    assert result == {'tax_disclosure': None, 'presentation_disclosure': None,
                      'status': {'tax_disclosure': 'unsupported_layout', 'presentation_disclosure': 'no_supported_subsection'}}


@pytest.mark.parametrize('change', ['missing_rate', 'wrong_rate_context', 'rate_unit', 'truncated_rate', 'rate_continuation_caveat'])
def test_actual_comparative_rate_never_loses_source_qualification(change):
    root = document()
    fact = node(root, 'f-2128')
    if change == 'missing_rate':
        fact.getparent().remove(fact)
    elif change == 'wrong_rate_context':
        fact.set('contextref', 'c-16')
    elif change == 'rate_unit':
        fact.set('unitref', 'usd')
    elif change == 'rate_continuation_caveat':
        caveat = html.Element('div')
        caveat.text = 'The preceding effective-rate comparison excludes another adjustment.'
        node(root, 'f-1930-4').insert(0, caveat)
    else:
        paragraph = next(n for n in fact.iterancestors() if n.tag == 'div')
        last = list(paragraph.iter())[-1]
        last.tail = (last.tail or '').rstrip('.')
        last.text = (last.text or '').rstrip('.')
    assert extract(root) is None
