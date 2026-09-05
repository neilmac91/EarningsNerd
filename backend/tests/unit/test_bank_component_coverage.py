"""Observed JPM G5 omission: populated tables must retain filing components."""
from copy import deepcopy
import json
import pytest
from app.services.openai_service import openai_service
from app.services.ai.bank_guards import ground_bank_component_rows
from app.services.ai.xbrl_narrative import build_xbrl_narrative_section
from app.services.provenance_service import enrich_financial_highlights
from evals.schema import GoldenFiling
from evals.scorers import score_bank_revenue_integrity
from evals.runner import GOLDEN_PATH


def metrics(currency='USD'):
    return {'reporting_currency': currency, **{
        key: {'current': {'value': current, 'period': '2025-12-31', 'currency': currency, 'raw_tag': tag},
              'prior': {'value': prior, 'period': '2024-12-31', 'currency': currency}}
        for key, current, prior, tag in [
            ('revenue', 182447000000, 177556000000, 'us-gaap:RevenuesNetOfInterestExpense'),
            ('net_interest_income', 95443000000, 92583000000, 'us-gaap:InterestIncomeExpenseNet'),
            ('noninterest_income', 87004000000, 84973000000, 'us-gaap:NoninterestIncome'),
        ]}}


def test_reported_total_directive_agrees_with_actual_components():
    grounding = metrics()
    text = build_xbrl_narrative_section(grounding)
    assert 'Revenue figure above is a reported total' in text
    assert 'NO single revenue line' not in text
    assert '$87,004,000,000' in text
    grounding.pop('revenue')
    no_total = build_xbrl_narrative_section(grounding)
    assert 'NO single revenue line' in no_total
    assert 'Revenue figure above is a reported total' not in no_total


def test_populated_table_recovers_jpm_components_and_verifiable_provenance():
    revenue = {'metric': 'Total net revenue', 'current_period': '$182.4B', 'commentary': 'Reported total.'}
    sections = {'results_that_matter': {'table': [revenue,
        {'metric': 'Noninterest income', 'current_period': '$1B', 'commentary': 'Wrong analysis',
         'supporting_evidence': 'Invented quotation'},
        {'metric': 'Non-Interest Income', 'current_period': '$2B'}]}}
    grounding = metrics()
    original = deepcopy(grounding)
    openai_service._apply_structured_fallbacks(sections, {}, grounding)
    table = sections['results_that_matter']['table']
    assert table[-1] == revenue
    assert len(table) == 3
    nii, noninterest = table[:2]
    assert nii['current_period'] == '$95,443,000,000 (2025-12-31)'
    assert noninterest['current_period'] == '$87,004,000,000 (2025-12-31)'
    assert noninterest['prior_period'] == '$84,973,000,000 (2024-12-31)'
    assert noninterest['commentary'] == noninterest['supporting_evidence'] == ''
    assert noninterest['source_basis'] == 'standardized_xbrl'
    assert noninterest['raw_tag'] == 'us-gaap:NoninterestIncome'
    filing = GoldenFiling.from_dict(next(f for f in json.loads(GOLDEN_PATH.read_text())['filings'] if f['ticker'] == 'JPM'))
    assert score_bank_revenue_integrity(json.dumps(table), filing.ground_truth) == (1.0, [])
    class Filing:
        document_url = 'https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/jpm-20251231.htm'
    enriched = enrich_financial_highlights(sections['results_that_matter'], Filing(), grounding)
    assert all(row['source_verified'] for row in enriched['table'][:2])
    before = deepcopy(sections)
    openai_service._apply_structured_fallbacks(sections, {}, grounding)
    assert sections == before
    assert grounding == original


@pytest.mark.parametrize('invalid', ['period', 'currency', 'value'])
def test_stale_foreign_or_invalid_component_is_not_injected(invalid):
    grounding = metrics()
    grounding['noninterest_income']['current'][invalid] = {
        'period': '2024-12-31', 'currency': 'EUR', 'value': float('nan')
    }[invalid]
    out = ground_bank_component_rows({'table': []}, grounding)
    assert [r['metric'] for r in out['table']] == ['Net Interest Income']


@pytest.mark.parametrize('invalid', ['period', 'currency'])
def test_component_prior_must_align_with_headline_and_currency(invalid):
    grounding = metrics('EUR')
    grounding['noninterest_income']['prior'][invalid] = {
        'period': '2023-12-31', 'currency': 'USD'
    }[invalid]
    out = ground_bank_component_rows({'table': []}, grounding)
    row = out['table'][1]
    assert row['current_period'] == 'EUR 87,004,000,000 (2025-12-31)'
    assert row['prior_period'] == ''
