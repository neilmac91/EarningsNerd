import { describe, expect, it, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { citationDisplay, compactNarrativeText, splitNarrativeEvidence, SOURCE_OPERANDS_PREFIX, type NarrativeOperand } from '@/features/analysis/lib/narrativeDisplay'
import { render, screen, fireEvent, within } from '@testing-library/react'

import NarrativePane, { type NarrativeState } from '@/features/analysis/components/NarrativePane'
import type { AnalysisCitation, AnalysisCompletion, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import DataNotes from '@/features/analysis/components/DataNotes'
import type { NarrativePresentation } from '@/features/analysis/lib/narrativePresentation'
import { groupQualityNotes } from '@/features/analysis/lib/dataNotes'

const citation: AnalysisCitation = {
  n: 1,
  excerpt: 'Revenue = 391,035,000,000 (FY2024)',
  section_ref: 'XBRL · us-gaap:Revenues',
  verified: true,
  fragment_url: null,
  concept: 'revenue',
  period: 'FY2024',
  derived: false,
}

function doneCompletion(overrides: Partial<AnalysisCompletion> = {}): AnalysisCompletion {
  return {
    kind: 'analysis',
    analysis_id: 7,
    narrative: 'Revenue grew to $391.0B [1].',
    citations: [citation],
    grounded: 1,
    unverified: 0,
    cached: false,
    n_periods: 6,
    ...overrides,
  }
}

const doneState = (overrides: Partial<NarrativeState> = {}): NarrativeState => ({
  status: 'done',
  text: 'Revenue grew to $391.0B [1].',
  completion: doneCompletion(),
  ...overrides,
})

describe('NarrativePane readable evidence', () => {
  const operands: AnalysisCitation[] = [
    { ...citation, concept: 'free_cash_flow', n: 1, period: '2026Q2', value: 1746000000, excerpt: 'Free cash flow = 1,746,000,000 (2026Q2)' },
    { ...citation, concept: 'net_income', n: 2, period: '2026Q2', value: 15848000000, excerpt: 'Net income = 15,848,000,000 (2026Q2)' },
  ]
  const renderText = (text: string) => render(<NarrativePane state={doneState({ text, completion: doneCompletion({ narrative: text, citations: operands, grounded: 2 }) })} />)

  it('pins the evidence prefix to the backend code-owned renderer', () => {
    const renderer = readFileSync(resolve(process.cwd(), '../backend/app/services/trend_analysis/observations.py'), 'utf8')
    expect(renderer).toContain(`f"${SOURCE_OPERANDS_PREFIX}{operands}."`)
  })

  it('keeps short findings inline without swallowing the next sentence or hiding their source chips', () => {
    const text = 'Cash conversion fell. Source operands: Free cash flow USD 1,746,000,000 in 2026Q2 [1]; Net income USD 15,848,000,000 in 2026Q2 [2]. Net income declined. Source operands: Net income USD 15,848,000,000 in 2026Q2 [2]. Watch cash next.'
    const { container } = renderText(text)
    expect(screen.getByText('Cash conversion fell.')).toBeInTheDocument()
    expect(screen.getByText('Net income declined.')).toBeInTheDocument()
    expect(screen.getByText('Watch cash next.')).toBeInTheDocument()
    const disclosures = Array.from(container.querySelectorAll('details')).filter((element) => element.textContent?.includes('behind this'))
    expect(disclosures).toHaveLength(0)
    const evidence = screen.getAllByRole('list', { name: 'Figures behind this finding' })
    expect(evidence).toHaveLength(2)
    expect(within(evidence[0]).getAllByRole('button')).toHaveLength(2)
    expect(evidence[0]).toHaveTextContent('Free cash flow $1.7B, Q2 2026')
    expect(evidence[0].querySelectorAll('[data-note-letter]')).toHaveLength(2)
    expect(document.getElementById('analysis-source-1')).toHaveTextContent('1.7B (1,746,000,000)')
    expect(document.getElementById('analysis-source-2')).toHaveTextContent('15.8B (15,848,000,000)')
  })

  it('compacts explicit-currency prose and preserves threshold precision, links and code', () => {
    const { container } = renderText('Revenue was USD 60,801,000,000 in 2026Q2 [1]. EPS was EUR 6.23 per share. The current ratio was 1.00004x, above 1.00x. Other ratio 2.2256x. [Filing](https://example.com/2026Q2) and `USD 60,801,000,000 in 2026Q2`.')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('Revenue was $60.8B in Q2 2026')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('EPS was €6.23')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('1.00004×, above 1.00×')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('Other ratio 2.23×')
    expect(screen.getByRole('link', { name: 'Filing' })).toHaveAttribute('href', 'https://example.com/2026Q2')
    expect(container.querySelector('code')).toHaveTextContent('USD 60,801,000,000 in 2026Q2')
  })

  it('preserves distinct close amounts across citation and Markdown nodes without rewriting the relation', () => {
    const exact = 'In 2026Q2, free cash flow of USD 1,001,000,000 [1] was below net income of USD 1,004,000,000 [2].'
    expect(compactNarrativeText(exact)).toBe('In Q2 2026, free cash flow of USD 1,001,000,000 [1] was below net income of USD 1,004,000,000 [2].')
    const { container } = renderText('In 2026Q2, free cash flow of **USD 1,001,000,000** [1] was below net income of _USD 1,004,000,000_ [2]. Source operands: Free cash flow USD 1,001,000,000 in 2026Q2 [1]; Net income USD 1,004,000,000 in 2026Q2 [2]. Revenue was USD 60,801,000,000. EPS EUR 6.231 per share was below EUR 6.234 per share.')
    const prose = container.querySelector('.markdown-body')!
    expect(prose).toHaveTextContent('free cash flow of USD 1,001,000,000 [1]a was below net income of USD 1,004,000,000 [2]a')
    expect(prose).not.toHaveTextContent('$1.0B')
    expect(prose).toHaveTextContent('Revenue was $60.8B')
    expect(prose).toHaveTextContent('EPS EUR 6.231 per share was below EUR 6.234 per share')
    const evidence = screen.getByRole('list', { name: 'Figures behind this finding', hidden: true })
    expect(evidence).toHaveTextContent('USD 1,001,000,000')
    expect(evidence).toHaveTextContent('USD 1,004,000,000')
    expect(within(evidence).getAllByRole('button', { hidden: true })).toHaveLength(2)
  })

  it('keeps an unrecognized or unresolved operand tail visible instead of dropping it', () => {
    const { container } = renderText('Keep this. Source operands: Free cash flow USD 1,746,000,000 in 2026Q2 [99]; Net income USD 15,848,000,000 in 2026Q2 [2]. More evidence. Source operands: malformed source text.')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('Source operands:')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('[99]')
    expect(container.querySelector('.markdown-body')).toHaveTextContent('malformed source text')
    expect(screen.queryByText(/figures behind this/)).not.toBeInTheDocument()
  })

  it('uses structured evidence with server-formatted values and keeps following prose visible', () => {
    const lead = 'Cash conversion fell. Revenue was EUR 1.6B and cash was GBP 23.4M.'
    const tail = ' Source operands: Free cash flow $1.746B in Q2 2026 [1].'
    const text = `${lead}${tail} Watch the next filing.`
    const presentation: NarrativePresentation = {
      format_version: 'analysis-narrative-v1', snapshot_id: 'snapshot-1', data_notes_version: 1,
      offset_encoding: 'utf-16',
      notes: { version: 1, notes: [], totals: { reviewValues: 0, reviewComparisons: 0, unavailable: 0, passed: 1, unknown: 0, calculated: 0, total: 1 } },
      evidence: [{ observation_id: 'cash_conversion', section: 'red_flags',
        tail: { start: lead.length, end: lead.length + tail.length, text: tail },
        operands: [{ marker: 'F1', concept: 'free_cash_flow', label: 'Free cash flow', value: 1746000000,
          unit: 'USD', percent: false, period: '2026Q2', citation_id: 1, derived: false, display_value: '$1.746B' }],
      }],
    }
    const completion = doneCompletion({ narrative: text, citations: [operands[0]], narrative_presentation: presentation })
    const { container } = render(<NarrativePane state={doneState({ text, completion })} />)
    expect(screen.getByText(lead)).toBeInTheDocument()
    expect(container.querySelector('.markdown-body')).not.toHaveTextContent('€1.0.6B')
    expect(container.querySelector('.markdown-body')).not.toHaveTextContent('£23.0.4M')
    expect(screen.getByText('Watch the next filing.')).toBeInTheDocument()
    expect(container.querySelector('.markdown-body')).not.toHaveTextContent('Source operands:')
    const evidence = screen.getByRole('list', { name: 'Figures behind this finding', hidden: true })
    expect(evidence).toHaveTextContent('$1.746B')
    expect(evidence).toHaveTextContent('Q2 2026')
    expect(within(evidence).getByRole('button', { hidden: true })).toHaveAccessibleName(/Citation 1:/)
    expect(evidence.closest('details')).toBeNull()
  })

  it('names original filing links by their source, figure and period', () => {
    const sources = operands.map((operand) => ({ ...operand, source_url: 'https://www.sec.gov/Archives/edgar/data/1326801/000132680126000001/meta-20260630.htm' }))
    render(<NarrativePane state={doneState({ completion: doneCompletion({ citations: sources }) })} />)
    expect(screen.getByRole('link', { name: 'Original filing for source 1: free cash flow, Q2 2026' })).toHaveAttribute('href', sources[0].source_url)
    expect(screen.getByRole('link', { name: 'Original filing for source 2: net income, Q2 2026' })).toHaveAttribute('href', sources[1].source_url)
  })

  it.each(['legacy', 'structured'] as const)('keeps every letter in a long %s evidence summary and restores disclosures after print', (mode) => {
    const sources: AnalysisCitation[] = [
      { ...operands[0], n: 1 },
      { ...operands[1], n: 2, reconciled: false },
      { ...operands[0], n: 3, provenance: { version: 1, method: 'reported', validation: 'needs_review', reasons: ['source_conflict'], formula: null, inputs: [] } },
      { ...operands[1], n: 4 },
    ]
    const lead = 'Watch the cash conversion pattern.'
    const tail = `${SOURCE_OPERANDS_PREFIX}${sources.map((source) => `${source.concept} USD ${source.value} in ${source.period} [${source.n}]`).join('; ')}.`
    const text = `${lead}${tail}`
    const presentation: NarrativePresentation = {
      format_version: 'analysis-narrative-v1', snapshot_id: 'snapshot-1', data_notes_version: 1, offset_encoding: 'utf-16',
      notes: { version: 1, notes: groupQualityNotes(sources).notes, totals: { reviewValues: 2, reviewComparisons: 0, unavailable: 0, passed: 0, unknown: 2, calculated: 0, total: 4 } },
      evidence: [{ observation_id: 'cash_conversion', section: 'red_flags', tail: { start: lead.length, end: text.length, text: tail },
        operands: sources.map((source) => ({ marker: `F${source.n}`, concept: source.concept!, label: source.concept!, value: source.value!, unit: 'USD', percent: false, period: source.period!, citation_id: source.n, derived: false, display_value: `$${source.value}` })),
      }],
    }
    const completion = doneCompletion({ narrative: text, citations: sources, ...(mode === 'structured' ? { narrative_presentation: presentation } : {}) })
    const empty: AnalysisDataset = { ticker: 'META', company_name: 'Meta Platforms', mode: 'quarterly', period_key: '2026Q2', periods: [], series: [], inflections: [] }
    const { container } = render(<><DataNotes dataset={empty} /><NarrativePane state={doneState({ text, completion })} /></>)
    const evidence = container.querySelector('.markdown-body details')!
    expect(evidence).not.toHaveAttribute('open')
    const summary = evidence.querySelector('summary')!
    expect(summary).toHaveTextContent('Show the 4 source figures behind this · figures carry notes a, b, c')
    expect(summary).not.toHaveClass('text-brand-strong')
    expect(within(evidence).getAllByRole('button', { hidden: true })).toHaveLength(4)
    const notes = container.querySelector<HTMLDetailsElement>('[data-analysis-data-notes] > details')!
    notes.open = true
    const prior = [...container.querySelectorAll('details')].map((details) => details.open)
    expect(prior).toContain(false)
    expect(prior).toContain(true)
    fireEvent(window, new Event('beforeprint'))
    fireEvent(window, new Event('beforeprint'))
    expect([...container.querySelectorAll('details')].every((details) => details.open)).toBe(true)
    fireEvent(window, new Event('afterprint'))
    expect([...container.querySelectorAll('details')].map((details) => details.open)).toEqual(prior)
  })

  it.each(['legacy', 'structured'] as const)('folds the backend-produced compatibility fixture in %s tabs', (mode) => {
    const fixture = JSON.parse(readFileSync(resolve(process.cwd(), '../backend/tests/fixtures/analysis_legacy_evidence.json'), 'utf8')) as {
      expected: { narrative: string; citations: AnalysisCitation[]; narrative_presentation: NarrativePresentation }
      legacy_operands: NarrativeOperand[][]
    }
    const { narrative, citations, narrative_presentation: presentation } = fixture.expected
    // The backend test pins these bytes to the real producer. Keep this parser unchanged:
    // an already-open Phase 1 tab drops the new envelope and takes exactly this path.
    const parts = splitNarrativeEvidence(narrative, citations)
    expect(parts.filter((part) => part.kind === 'evidence').map((part) => part.operands)).toEqual(fixture.legacy_operands)
    const completion = doneCompletion({ narrative, citations,
      ...(mode === 'structured' ? { narrative_presentation: presentation } : {}),
    })
    const { container } = render(<NarrativePane state={doneState({ text: narrative, completion })} />)
    expect(container.querySelector('.markdown-body')).not.toHaveTextContent('Source operands:')
    expect(screen.getByText(/Watch how revenue in the next reporting update/)).toBeInTheDocument()
    const blocks = screen.getAllByRole('list', { name: 'Figures behind this finding', hidden: true })
    expect(blocks).toHaveLength(fixture.legacy_operands.length)
    blocks.forEach((block, index) => {
      expect(within(block).getAllByRole('button', { hidden: true })).toHaveLength(fixture.legacy_operands[index].length)
      expect(block).toHaveTextContent('Q4 2025')
      expect(block).toHaveTextContent('1.00004×')
      if (mode === 'structured') {
        presentation.evidence[index].operands.forEach((operand) => expect(block.textContent).toContain(operand.display_value))
      }
    })
  })

  it('uses explicit wire units for non-dollar and computed-window citation figures', () => {
    expect(citationDisplay({ ...citation, value: 1250000000, unit: 'EUR', period: '2026Q2', excerpt: 'Revenue = 1,250,000,000 (2026Q2)' }))
      .toBe('Revenue · Q2 2026 · €1.3B (1,250,000,000 EUR)')
    expect(citationDisplay({ ...citation, concept: 'revenue', value: 0.125, unit: 'growth fraction', period: 'FY2021..FY2024', excerpt: 'Revenue CAGR = 12.5% (FY2021..FY2024)' }))
      .toContain('12.5% (0.125 (growth fraction))')
    expect(citationDisplay({ ...citation, concept: 'net_margin', value: -3.25, unit: 'percentage points', period: 'FY2021..FY2024', excerpt: 'Net margin change = -3.25pp (FY2021..FY2024)' }))
      .toContain('-3.3pp (-3.25 percentage points)')
  })

  it('retains exact citation precision and describes a legacy calculation without implying recorded inputs', () => {
    const citations = [
      { ...citation, value: 26.065360767092647, excerpt: 'Net margin = 26.1% (2026Q2)', section_ref: 'XBRL · net_margin', provenance: { version: 1 as const, method: 'calculated' as const, validation: 'needs_review' as const, reasons: ['legacy_calculation'], formula: null, inputs: [] } },
      { ...citation, n: 2, value: 1.00004, excerpt: 'Current ratio = 1.00004x (2026Q2)' },
    ]
    render(<NarrativePane state={doneState({ completion: doneCompletion({ citations }) })} />)
    expect(document.getElementById('analysis-source-1')).toHaveTextContent('26.1% (26.065360767092645%)')
    expect(document.getElementById('analysis-source-2')).toHaveTextContent('1.00004× (1.00004 ratio)')
    const chip = screen.getByRole('button', { name: 'Citation 1: XBRL · net_margin. Net margin · Q2 2026 · 26.1% (26.065360767092645%), data note a' })
    expect(chip).toHaveAttribute('title', 'Net margin · Q2 2026 · 26.1% (26.065360767092645%) · XBRL · net_margin')
    expect(chip.querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    const source = document.getElementById('analysis-source-1')!
    expect(source).toHaveTextContent('Calculated figure')
    expect(source).not.toHaveTextContent('Calculated from filing figures')
    expect(source).not.toHaveTextContent('Calculated from recorded inputs')
    expect(document.getElementById('analysis-data-note-a')).toHaveTextContent('This saved calculation predates the current automated checks. Its inputs need review.')
  })
})

describe('NarrativePane citation chips', () => {
  it('keeps source-entry resolution separate from an unreconciled dataset value', () => {
    const state = doneState({ completion: doneCompletion({ citations: [{ ...citation, reconciled: false }] }) })
    const { rerender } = render(<NarrativePane state={state} />)
    expect(screen.getByText('1 source')).toBeInTheDocument()
    const notesButton = screen.getByRole('button', { name: 'Review data notes a' })
    expect(document.getElementById('analysis-source-1')?.querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    expect(screen.getByRole('button', { name: /Citation 1:.*data note a/ })).toBeInTheDocument()
    fireEvent.click(notesButton)
    const note = document.getElementById('analysis-data-note-a')!
    expect(note.closest('details')).toHaveAttribute('open')
    expect(note).toHaveFocus()
    expect(note).toHaveTextContent('This figure has not passed EarningsNerd’s automated consistency checks')
    expect(screen.getByText('Sources · SEC XBRL values and calculated figures')).toBeInTheDocument()
    rerender(<NarrativePane state={doneState()} />)
    expect(document.querySelector('[data-note-kind="review"]')).not.toBeInTheDocument()
    expect(document.querySelector('[data-note-kind="unknown"]')).toBeInTheDocument()
  })

  it('retains a citation-only concern beside report notes without changing report counts or colliding IDs', () => {
    const dataset: AnalysisDataset = {
      ticker: 'TST', company_name: 'Test', mode: 'annual', period_key: 'FY2024',
      periods: [{ key: 'FY2024', fiscal_year: 2024, fiscal_period: 'FY', period_end: '2024-12-31' }],
      series: [{ concept: 'revenue', label: 'Revenue', unit: 'USD', percent: false, cagr: null, points: [{
        period: 'FY2024', value: 391035000000,
        provenance: { version: 1, method: 'reported', validation: 'needs_review', reasons: ['unit_mismatch'], formula: null, calculation_version: 'quarterly-v2', inputs: [] },
      }] }], inflections: [],
    }
    const state = doneState({ completion: doneCompletion({ citations: [{ ...citation, reconciled: false }] }) })
    const { rerender } = render(<DataNotesProvider dataset={dataset}><DataNotes dataset={dataset} /><NarrativePane state={state} /></DataNotesProvider>)
    expect(screen.getByText(/1 figure needs review/)).toBeInTheDocument()
    expect(screen.queryByText(/2 figures need review/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Citation 1:.*data note b/ })).toBeInTheDocument()
    expect(document.querySelectorAll('#analysis-data-note-a')).toHaveLength(1)
    expect(document.querySelectorAll('#analysis-data-note-b')).toHaveLength(1)
    const note = document.getElementById('analysis-data-note-b')!
    fireEvent.click(screen.getByRole('button', { name: 'Review data notes b' }))
    expect(note.closest('details')).toHaveAttribute('open')
    expect(note).toHaveFocus()
    expect(note).toHaveTextContent('This figure has not passed EarningsNerd’s automated consistency checks')
    expect(document.getElementById('analysis-data-note-a')).toHaveTextContent('The source inputs use different units or currencies')
    const passed = structuredClone(dataset)
    passed.series[0].points[0].provenance!.validation = 'passed'
    passed.series[0].points[0].provenance!.reasons = []
    rerender(<DataNotesProvider dataset={passed}><DataNotes dataset={passed} /><NarrativePane state={state} /></DataNotesProvider>)
    expect(screen.getByText(/No figures need review · 1 checked/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Citation 1:.*data note a/ }).querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    expect(document.getElementById('analysis-data-note-a')).toHaveTextContent('This figure has not passed EarningsNerd’s automated consistency checks')
  })

  beforeEach(() => {
    // jsdom doesn't implement scrollIntoView — stub it (same pattern as highlightInDom.spec.ts).
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('renders a chip for a resolved [1] marker', () => {
    render(<NarrativePane state={doneState()} />)
    const chip = screen.getByRole('button', { name: /citation 1: xbrl · us-gaap:revenues/i })
    expect(chip).toHaveTextContent('[1]')
  })

  it('scrolls to and flashes the matching Sources row when a chip is clicked', () => {
    render(<NarrativePane state={doneState()} />)
    const chip = screen.getByRole('button', { name: /citation 1/i })
    const sourceRow = document.getElementById('analysis-source-1')
    expect(sourceRow).not.toBeNull()

    fireEvent.click(chip)
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    expect(sourceRow).toHaveClass('citation-flash')
  })

  it('leaves an unmatched [2] as plain text (no chip)', () => {
    const state = doneState({
      text: 'A claim with no citation [2].',
      completion: doneCompletion({ narrative: 'A claim with no citation [2].' }),
    })
    render(<NarrativePane state={state} />)
    expect(screen.getByText(/\[2\]/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /citation 2/i })).not.toBeInTheDocument()
  })

  it('does not inject chips while streaming (raw markers stay plain text)', () => {
    render(<NarrativePane state={{ status: 'streaming', text: 'Revenue grew [1]', stage: 'writing' }} />)
    expect(screen.getByText(/\[1\]/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /citation 1/i })).not.toBeInTheDocument()
  })

  it('shows mismatch and removed-reference warnings without calling source entries verified', () => {
    const state = doneState({ completion: doneCompletion({ unverified: 2, mismatched: 1 }) })
    render(<NarrativePane state={state} />)
    const badge = screen.getByText('1 source')
    expect(badge).toHaveAttribute(
      'title',
      expect.stringContaining('1 figure printed next to a source entry could not be reconciled')
    )
    expect(screen.getByText('Some source references need attention')).toBeInTheDocument()
    expect(
      screen.getByText(/2 model source references did not resolve to the analysis dataset and were removed/)
    ).toHaveTextContent('Check the Sources list before relying on the narrative figure')
    expect(screen.queryByText(/verified citations/)).not.toBeInTheDocument()
  })

  it('omits the unverified caveat from the tooltip when nothing was stripped', () => {
    render(<NarrativePane state={doneState()} />)
    const badge = screen.getByText('1 source')
    expect(badge.getAttribute('title')).not.toContain('did not resolve')
    expect(screen.queryByText('Some source references need attention')).not.toBeInTheDocument()
  })

  it('replaces the verified/cached badges with a Sample badge in teaser mode (F3)', () => {
    const state = doneState({ completion: doneCompletion({ cached: true }) })
    render(<NarrativePane state={state} sample />)
    // Approximate demo figures must never wear the "verified" claim.
    expect(screen.getByText('Sample data')).toBeInTheDocument()
    expect(screen.queryByText(/^\d+ sources?$/)).not.toBeInTheDocument()
    expect(screen.queryByText('Cached')).not.toBeInTheDocument()
    expect(screen.getByText(/Sources · sample data/)).toBeInTheDocument()
  })
})
