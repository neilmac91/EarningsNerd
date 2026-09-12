"""Server-owned repair of a wholly uncited, explicit single-fact answer.

The retained #825 second Copilot assessment (`results[14]`, BABA 20-F `0000950170-25-090161`,
run 2) shipped "Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million." with an
empty tool trace, an empty citations array and zero stripped markers — the right number with no
attribution. The placement guards cannot reach it: they only ever REMOVE a marker, and this answer
never placed one.

The repair attaches a marker only when the filing's own fact proves it covers the claimed year,
which means the fact must carry its own reported duration. `test_quarterly_point_in_an_annual_
filing_never_certifies` drives the real production transformation to show why nothing weaker will
do: a three-month revenue point ending on the fiscal year end survives the companyfacts fallback,
loses its start, and reaches the fact table labelled `FY`. A fact with no duration therefore
abstains — including the retained BABA row itself, which is pinned below as a known incomplete
case rather than quietly presented as fixed.

These tests drive the real service path with a fake stream and a scoped fact lookup; every
negative control leaves the answer byte-identical.
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
    """The viewed filing's revenue fact WITH a trustworthy reported duration (364 days).

    This is the shape the repair can certify. Pass `period_start=None` for the shape most runtime
    rows actually have today — see `undated_fact`.
    """
    return {'concept': 'revenue', 'raw_tag': 'us-gaap:Revenues', 'value': 996347000000.0,
            'unit': 'CNY', 'accession': ACC, 'period_start': '2024-04-01',
            'period_end': '2025-03-31', 'fiscal_year': 2025, 'fiscal_period': 'FY', **changes}


def undated_fact(**changes):
    """The same fact as the per-filing ingest path actually stores it: no duration at all."""
    return fact(period_start=None, **changes)


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
async def test_uncited_answer_gains_a_citation_when_the_fact_proves_the_year(monkeypatch):
    """The positive path: same prose, one real chip, numbering agreeing with the citations list.

    The fact here carries a 364-day reported duration, so it demonstrably covers the claimed year.
    """
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
async def test_retained_baba_row_still_abstains_because_it_carries_no_duration(monkeypatch):
    """KNOWN INCOMPLETE — the retained #825 defect is not repaired by this change.

    `results[14]`'s filing stored its revenue through the per-filing ingest path, which writes no
    `period_start`. Nothing in the record proves the figure spans the fiscal year the sentence
    claims, so the repair abstains and the answer ships exactly as it did. Certifying it on the
    annual form and the `FY` label alone would put a verified chip on a possibly-quarterly figure.
    Closing this needs duration carried into the fact record — an ingestion change owned elsewhere.
    """
    complete = await _complete(monkeypatch, UNCITED, lookup=lambda *a, **kw: undated_fact())

    assert complete['answer'] == UNCITED
    assert complete['citations'] == [] and complete['grounded'] == 0
    assert complete['uncited_figures'] == 1


INGESTED_ACCESSION = '0000320193-25-000079'


def _ingest(start, end='2025-03-29'):
    """Source companyfacts item -> stored fact row -> runtime tool result, all production code.

    `_parse_company_facts` ranks and keeps the point, `append_items` emits it,
    `extract_standardized_metrics` carries it, `normalize_standardized_to_facts` builds the row and
    `_fact_provenance` projects what the Copilot tool actually returns.
    """
    from app.models.financial_fact import FinancialFact
    from app.services.edgar.xbrl_service import EdgarXBRLService
    from app.services.facts_service import normalize_standardized_to_facts

    item = {'end': end, 'val': 95359000000.0, 'form': '10-K', 'accn': INGESTED_ACCESSION,
            'filed': '2025-05-02', 'fy': 2025, 'fp': 'FY'}
    if start is not None:
        item['start'] = start
    payload = {'facts': {'us-gaap': {'Revenues': {'units': {'USD': [item]}}}}}
    svc = EdgarXBRLService.__new__(EdgarXBRLService)
    standardized = svc.extract_standardized_metrics(
        svc._parse_company_facts(payload, INGESTED_ACCESSION))
    row = [r for r in normalize_standardized_to_facts(9, 7, INGESTED_ACCESSION, '10-K', standardized)
           if r['concept'] == 'revenue'][0]
    return row, service.copilot_tools._fact_provenance(FinancialFact(**row))


def _ingested_claim_and_view():
    claim = service._plan_uncited_fact_citation(
        'Revenue for the fiscal year ended March 29, 2025 was $95,359 million.')
    view = filing(filing_type='10-K', period_of_report='2025-03-29',
                  accession_number=INGESTED_ACCESSION, xbrl_data={'reporting_currency': 'USD'})
    return claim, view


def test_quarterly_point_in_an_annual_filing_never_certifies():
    """The realistic regression: a three-month point ending on the fiscal year end.

    This is the case the companyfacts fallback ranks but never rejects — an annual filing may
    legitimately disclose a quarter, so selection is unchanged and the point is still kept and
    still labelled `FY` from the FORM. What changed is that its real duration now survives to the
    stored row, so the claim layer can refuse it instead of mistaking it for a year. It passes
    `_valid_fact_provenance`, so only the duration requirement stands between it and a verified
    annual citation.
    """
    row, runtime = _ingest('2024-12-29')
    claim, view = _ingested_claim_and_view()

    # The duration is preserved honestly, and the FY label is still there — both facts matter.
    assert runtime['period_start'] == '2024-12-29' and runtime['fiscal_period'] == 'FY'
    assert service._valid_fact_provenance(runtime, INGESTED_ACCESSION, 'USD')
    assert claim is not None and claim['value'] == 95359000000.0
    assert not service._fact_certifies_claim(runtime, claim, view)


def test_freshly_ingested_annual_point_certifies_end_to_end():
    """The repaired path: a genuine annual source duration reaches the row, the tool and the chip."""
    row, runtime = _ingest('2024-03-30')
    claim, view = _ingested_claim_and_view()

    assert str(row['period_start']) == '2024-03-30'
    assert runtime['period_start'] == '2024-03-30'
    assert service._fact_certifies_claim(runtime, claim, view)


def test_a_source_point_with_no_start_stays_unknown_through_ingestion():
    """Missing duration is carried as missing — never filled in from the form or the period end."""
    row, runtime = _ingest(None)
    claim, view = _ingested_claim_and_view()

    assert row['period_start'] is None and runtime['period_start'] is None
    assert runtime['fiscal_period'] == 'FY'
    assert not service._fact_certifies_claim(runtime, claim, view)


@pytest.mark.asyncio
async def test_freshly_ingested_annual_point_reaches_the_citation(monkeypatch):
    """The whole visible path: source duration -> stored row -> tool -> rendered chip."""
    _row, runtime = _ingest('2024-03-30')
    view = filing(filing_type='10-K', period_of_report='2025-03-29',
                  accession_number=INGESTED_ACCESSION, xbrl_data={'reporting_currency': 'USD'})
    complete = await _complete(
        monkeypatch, 'Revenue for the fiscal year ended March 29, 2025 was $95,359 million.',
        lookup=lambda *a, **kw: dict(runtime), view=view)

    assert complete['answer'] == (
        'Revenue for the fiscal year ended March 29, 2025 was $95,359 million [1].')
    assert len(complete['citations']) == 1
    assert complete['citations'][0]['period_start'] == '2024-03-30'
    assert complete['grounded'] == 1 and complete['uncited_figures'] == 0


def test_preserved_durations_never_reach_the_model_prompt():
    """Extraction now carries durations; the model-facing block must be byte-identical without them.

    That block is truncated at a fixed cap, so a new key would displace excerpt content — widening
    what the model sees is a prompt change with its own evidence requirements.
    """
    undated = {'revenue': [{'period': '2025-03-29', 'value': 1.0, 'form': '10-K'}],
               'reporting_currency': 'USD'}
    dated = {'revenue': [{'period': '2025-03-29', 'value': 1.0, 'form': '10-K',
                          'period_start': '2024-03-30'}],
             'reporting_currency': 'USD'}
    assert service._compact_xbrl_block(dated) == service._compact_xbrl_block(undated)
    assert 'period_start' not in service._compact_xbrl_block(dated)


def test_newly_dated_facts_do_not_let_a_mismatched_comparison_through():
    """Populating duration must not accidentally certify a derived comparison.

    `_prior_comparable` is the reader that gains data here; it must still refuse an annual current
    period paired with a prior quarter, and still accept a genuine year-over-year pair.
    """
    from datetime import date as _date

    from app.models.financial_fact import FinancialFact

    def row(start, end, value):
        return FinancialFact(concept='revenue', unit='USD', value=value,
                             period_start=_date.fromisoformat(start),
                             period_end=_date.fromisoformat(end))

    current = row('2025-01-01', '2025-12-31', 100)
    assert not service.copilot_tools._prior_comparable(current, row('2024-10-01', '2024-12-31', 25))
    assert service.copilot_tools._prior_comparable(current, row('2024-01-01', '2024-12-31', 90))


def test_the_annual_window_matches_the_two_modules_that_already_own_it():
    """One annual window repo-wide: drift in either owner must fail here, not widen certification."""
    from app.services.edgar.instance_extractor import DURATION_WINDOWS
    from app.services.facts_service import _CF_ANNUAL_WINDOW

    assert service._ANNUAL_DURATION_DAYS == _CF_ANNUAL_WINDOW
    assert all(DURATION_WINDOWS[form] == service._ANNUAL_DURATION_DAYS
               for form in ('10-K', '20-F', '40-F'))


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
    pytest.param(lambda: dict(undated_fact()), id='no-reported-duration'),
    pytest.param(lambda: dict(fact(period_start='2024-12-31')), id='quarterly-duration'),
    pytest.param(lambda: dict(fact(period_start='2024-07-01')), id='nine-month-ytd-duration'),
    pytest.param(lambda: dict(fact(period_start='2023-04-01')), id='two-year-duration'),
    pytest.param(lambda: dict(fact(period_start='not-a-date')), id='unparseable-duration'),
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


@pytest.mark.asyncio
async def test_declared_but_unplaced_text_citation_still_gets_the_certified_chip(monkeypatch):
    """The model declared a source and forgot to place its marker, so the prose is still uncited.

    The declared-but-never-placed citation is dropped as always; the repair supplies the chip the
    figure actually needs, and numbering still comes from the one resolver pass.
    """
    declared = (f'{UNCITED}{service._CITATIONS_SENTINEL}'
                '[{"n": 1, "excerpt": "Selected filing source.", "section": "Item 5"}]')
    complete = await _complete(monkeypatch, declared)

    assert complete['answer'] == REPAIRED
    assert len(complete['citations']) == 1
    assert complete['citations'][0]['section_ref'] == 'XBRL \u00b7 us-gaap:Revenues'


def test_an_unrepresentable_numeral_never_certifies():
    """A numeral too large to be a float must abstain, not compare as an infinite value."""
    absurd = service._plan_uncited_fact_citation(
        'Revenue for the fiscal year ended March 31, 2025 was RMB' + '9' * 400 + ' million.')
    assert not service._fact_certifies_claim(fact(), absurd, filing())


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
