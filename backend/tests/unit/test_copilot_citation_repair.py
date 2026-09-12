"""Server-owned repair of a wholly uncited, explicit single-fact answer.

The retained #825 second Copilot assessment (`results[14]`, BABA 20-F `0000950170-25-090161`,
run 2) shipped "Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million." with an
empty tool trace, an empty citations array and zero stripped markers — the right number with no
attribution. The placement guards cannot reach it: they only ever REMOVE a marker, and this answer
never placed one. These tests drive the real service path with a fake stream and a scoped fact
lookup, so the positive control is the actual defect and every negative control abstains with the
answer byte-identical.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import copilot_service as service

ACC = '0000950170-25-090161'
OTHER = '0001193125-26-231755'
UNCITED = 'Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million.'
REPAIRED = 'Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million [1].'


def fact(**changes):
    """The viewed filing's own revenue fact, exactly as `copilot_tools` returns it at runtime.

    `period_start` is None because `facts_service._build_facts` never writes one — the reason this
    repair certifies annual SCOPE (annual form + period of report + FY label) and not duration.
    """
    return {'concept': 'revenue', 'raw_tag': 'us-gaap:Revenues', 'value': 996347000000.0,
            'unit': 'CNY', 'accession': ACC, 'period_start': None, 'period_end': '2025-03-31',
            'fiscal_year': 2025, 'fiscal_period': 'FY', **changes}


def filing(**changes):
    fields = dict(id=7, company_id=9, filing_type='20-F', filing_date=None,
        accession_number=ACC, period_end_date=datetime(2025, 3, 31), period_of_report='2025-03-31',
        document_url='https://www.sec.gov/viewed', sec_url=None,
        xbrl_data={'reporting_currency': 'RMB'},
        content_cache=SimpleNamespace(critical_excerpt='Selected filing source.', markdown_content=None),
        company=SimpleNamespace(name='Alibaba', ticker='BABA'))
    return SimpleNamespace(**{**fields, **changes})


async def _complete(monkeypatch, answer, *, lookup=None, view=None, model_calls=None):
    """Run the real generator over a fake stream; return its single terminal `complete` event.

    `model_calls` collects what the MODEL asked for through the closure the eval harness observes,
    so a server-initiated lookup can be shown never to enter tool-call history.
    """
    monkeypatch.setattr(service.copilot_tools, 'run_tool',
                        lookup if lookup is not None else (lambda *a, **kw: dict(fact())))

    async def stream(messages, tools, run_tool, **kwargs):
        for name, args in (model_calls or []):
            yield f"{service.STREAM_ACTIVITY_SENTINEL}{{}}"
            run_tool(name, args)
        yield answer

    monkeypatch.setattr(service.openai_service, 'stream_chat_with_tools', stream)
    events = [e async for e in service.answer_filing_question(
        filing=view if view is not None else filing(), question='Revenue?')]
    terminal = [e for e in events if e['type'] == 'complete']
    assert len(terminal) == 1
    return terminal[0]


@pytest.mark.asyncio
async def test_retained_uncited_answer_gains_the_filings_own_citation(monkeypatch):
    """The actual defect: same prose, one real chip, numbering agreeing with the citations list."""
    complete = await _complete(monkeypatch, UNCITED)

    assert complete['answer'] == REPAIRED
    assert len(complete['citations']) == 1
    cite = complete['citations'][0]
    assert cite['n'] == 1 and '[1]' in complete['answer']
    assert (cite['concept'], cite['accession'], cite['period_end'], cite['unit'],
            cite['value'], cite['verified']) == ('revenue', ACC, '2025-03-31', 'CNY',
                                                 996347000000.0, True)
    assert complete['grounded'] == 1 and complete['misplaced_fact_markers'] == 0
    # The advisory coverage counter follows the repair; it never drives it.
    assert (complete['figure_count'], complete['uncited_figures']) == (1, 0)


@pytest.mark.asyncio
async def test_server_lookup_is_labelled_and_never_becomes_model_tool_history(monkeypatch):
    """A local lookup the server started must not be recorded as something the model called."""
    observed = []

    def lookup(name, args, company_id, **scope):
        observed.append((name, args, company_id, scope))
        return dict(fact())

    seen_by_harness = []

    async def stream(messages, tools, run_tool, **kwargs):
        # The eval harness observes model tool calls by wrapping exactly this closure.
        seen_by_harness.append('stream-started')
        yield UNCITED

    monkeypatch.setattr(service.copilot_tools, 'run_tool', lookup)
    monkeypatch.setattr(service.openai_service, 'stream_chat_with_tools', stream)
    events = [e async for e in service.answer_filing_question(filing=filing(), question='Revenue?')]

    assert [e for e in events if e['type'] == 'activity'] == []
    assert observed == [('get_financial_fact', {'concept': 'revenue'}, 9,
                         {'accession_number': ACC, 'reporting_currency': 'CNY'})]
    assert seen_by_harness == ['stream-started']
    assert [e for e in events if e['type'] == 'complete'][0]['answer'] == REPAIRED


@pytest.mark.asyncio
async def test_rounded_display_precision_still_certifies(monkeypatch):
    """"RMB996.3 billion" is the correct rounding of the filing value at the precision written."""
    rounded = 'Revenue for the fiscal year ended March 31, 2025 was RMB996.3 billion.'
    complete = await _complete(monkeypatch, rounded)
    assert complete['answer'] == rounded[:-1] + ' [1].'
    assert len(complete['citations']) == 1


@pytest.mark.asyncio
async def test_existing_citation_is_preserved_and_no_second_lookup_runs(monkeypatch):
    """An answer that already cites its figure keeps its own text and provenance untouched."""
    lookups = []

    def lookup(name, args, company_id, **scope):
        lookups.append(name)
        return dict(fact())

    complete = await _complete(
        monkeypatch, 'Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million [F1].',
        lookup=lookup, model_calls=[('get_financial_fact', {'concept': 'revenue'})])

    assert complete['answer'] == REPAIRED          # the model's own marker, renumbered as always
    assert len(complete['citations']) == 1         # not two — the repair never ran
    assert lookups == ['get_financial_fact']       # exactly the model's call


@pytest.mark.asyncio
async def test_known_advisory_false_positive_answer_is_untouched(monkeypatch):
    """The Microsoft shape the scorer flags: figures DO carry adjacent markers, so nothing changes."""
    msft = ('Revenue was $281.72B [F1] and diluted earnings per share were $13.64 [F2] for the '
            'fiscal year ended June 30, 2025.')
    facts = [{'concept': 'revenue', 'raw_tag': 'us-gaap:Revenues', 'value': 281724000000.0,
              'unit': 'USD', 'accession': ACC, 'period_start': None, 'period_end': '2025-06-30',
              'fiscal_year': 2025, 'fiscal_period': 'FY'},
             {'concept': 'eps_diluted', 'raw_tag': 'us-gaap:EarningsPerShareDiluted',
              'value': 13.64, 'unit': 'USD/shares', 'accession': ACC, 'period_start': None,
              'period_end': '2025-06-30', 'fiscal_year': 2025, 'fiscal_period': 'FY'}]
    pending = iter(facts)
    view = filing(period_of_report='2025-06-30', filing_type='10-K',
                  xbrl_data={'reporting_currency': 'USD'})
    complete = await _complete(monkeypatch, msft, lookup=lambda *a, **kw: dict(next(pending)),
                               view=view,
                               model_calls=[('get_financial_fact', {'concept': 'revenue'}),
                                            ('get_financial_fact', {'concept': 'eps_diluted'})])

    assert complete['answer'] == msft.replace('[F1]', '[1]').replace('[F2]', '[2]')
    assert len(complete['citations']) == 2 and complete['misplaced_fact_markers'] == 0


# Text the repair must refuse: each is an unsupported factual form, not a complete reported
# annual figure, so the answer must survive byte-identical with no citation at all.
@pytest.mark.parametrize('answer', [
    pytest.param('Revenue for fiscal 2025 was RMB996,347 million.', id='year-only-scope'),
    pytest.param('Revenue for the quarter ended March 31, 2025 was RMB996,347 million.', id='quarterly-text'),
    pytest.param('Revenue for the fiscal year ending March 31, 2025 was RMB996,347 million.', id='forward-looking'),
    pytest.param('Revenue for the fiscal year ended March 2025 was RMB996,347 million.', id='no-day'),
    pytest.param('Revenue for the fiscal year ended February 30, 2025 was RMB996,347 million.', id='impossible-date'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was 996,347 million.', id='no-currency'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was US$996,347 million.', id='claimed-currency-not-the-filings'),
    pytest.param('Cloud revenue for the fiscal year ended March 31, 2025 was RMB996,347 million.', id='segment-subject'),
    pytest.param('Sales for the fiscal year ended March 31, 2025 was RMB996,347 million.', id='bare-sales'),
    pytest.param('The filing states "Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million."', id='quotation'),
    pytest.param('If the disposal is excluded, revenue for the fiscal year ended March 31, 2025 was RMB996,347 million.', id='conditional'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million, up 5.9% from the prior year.', id='comparative'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million, driven by cloud growth.', id='causal'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million. Net income was RMB130,109 million.', id='multi-metric'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was approximately RMB996,347 million.', id='hedged'),
    pytest.param('Revenue for the fiscal year ended March 31, 2025 was RMB996.4 billion, or about US$137 billion.', id='convenience-translation'),
])
@pytest.mark.asyncio
async def test_unsupported_claim_shapes_abstain(monkeypatch, answer):
    complete = await _complete(monkeypatch, answer)
    assert complete['answer'] == answer
    assert complete['citations'] == [] and complete['grounded'] == 0


# Evidence the filing does not actually supply. The sentence is the qualifying one every time, so
# only the returned fact (or the viewed filing) differs — amount coincidence must never certify.
@pytest.mark.parametrize('lookup', [
    pytest.param(lambda: dict(fact(concept='net_income')), id='equal-amount-wrong-concept'),
    pytest.param(lambda: dict(fact(accession=OTHER)), id='wrong-accession'),
    pytest.param(lambda: dict(fact(period_end='2024-03-31')), id='wrong-full-date'),
    pytest.param(lambda: dict(fact(fiscal_period='Q4')), id='quarterly-not-annual'),
    pytest.param(lambda: dict(fact(fiscal_period=None)), id='unlabelled-period'),
    pytest.param(lambda: dict(fact(unit='USD')), id='wrong-currency'),
    pytest.param(lambda: dict(fact(unit=None)), id='unknown-unit'),
    pytest.param(lambda: dict(fact(value=-996347000000.0)), id='wrong-sign'),
    pytest.param(lambda: dict(fact(value=996347000000.0 / 1000)), id='wrong-scale'),
    pytest.param(lambda: dict(fact(value=996347500000.001)), id='outside-display-rounding'),
    pytest.param(lambda: dict(fact(kind='yoy_growth', unit='pure', value=0.059,
                                   source_facts=[fact(), fact()])), id='derived-result'),
    pytest.param(lambda: {'error': 'ambiguous_fact'}, id='ambiguous'),
    pytest.param(lambda: {'error': 'not_disclosed', 'available_concepts': []}, id='not-disclosed'),
    pytest.param(lambda: {'error': 'filing_scope_unavailable'}, id='scope-unavailable'),
    pytest.param(lambda: None, id='malformed-result'),
])
@pytest.mark.asyncio
async def test_uncertified_evidence_abstains(monkeypatch, lookup):
    complete = await _complete(monkeypatch, UNCITED, lookup=lambda *a, **kw: lookup())
    assert complete['answer'] == UNCITED
    assert complete['citations'] == [] and complete['grounded'] == 0
    assert complete['uncited_figures'] == 1      # still advisory, still honest


# The viewed filing itself cannot support an annual claim.
@pytest.mark.parametrize('view', [
    pytest.param(filing(filing_type='10-Q'), id='quarterly-form'),
    pytest.param(filing(filing_type='6-K'), id='free-form-report'),
    pytest.param(filing(filing_type=None), id='unknown-form'),
    pytest.param(filing(period_of_report='2024-03-31'), id='filing-period-disagrees'),
    pytest.param(filing(period_of_report=None), id='filing-period-absent'),
])
@pytest.mark.asyncio
async def test_non_annual_or_mismatched_filing_abstains(monkeypatch, view):
    complete = await _complete(monkeypatch, UNCITED, view=view)
    assert complete['answer'] == UNCITED and complete['citations'] == []


@pytest.mark.asyncio
async def test_repair_never_ships_a_marker_the_resolver_would_strip(monkeypatch):
    """The placement guards run on the exact window the resolver will compute, so a certified
    insertion is never converted straight back into a stripped marker."""
    complete = await _complete(monkeypatch, UNCITED)
    assert complete['misplaced_fact_markers'] == 0 and complete['answer'] == REPAIRED


def test_display_rounding_half_interval_is_the_last_stated_digit():
    """The numeral must be the correct rounding of the filing value at the precision written."""
    whole = service._plan_uncited_fact_citation(UNCITED)
    tenths = service._plan_uncited_fact_citation(
        'Revenue for the fiscal year ended March 31, 2025 was RMB996.3 billion.')
    assert (whole['value'], whole['tolerance']) == (996347000000.0, 5e5)
    assert (tenths['value'], tenths['tolerance']) == (996300000000.0, 5e7)
    assert whole['concept'] == 'revenue' and whole['currency'] == 'CNY'
    assert whole['period_end'] == '2025-03-31'
    # And that interval is what certification actually compares against, signed.
    view = filing()
    assert service._fact_certifies_claim(fact(value=996347000000.0 + 499999), whole, view)
    assert not service._fact_certifies_claim(fact(value=996347000000.0 + 500001), whole, view)
