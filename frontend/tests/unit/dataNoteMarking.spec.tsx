import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { describe, expect, it } from 'vitest'
import { act, fireEvent, render, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import DataNotes from '@/features/analysis/components/DataNotes'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import KpiStrip from '@/features/analysis/components/KpiStrip'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import NarrativePane from '@/features/analysis/components/NarrativePane'
import TrendCharts from '@/features/analysis/components/TrendCharts'
import type { AnalysisCitation, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { groupDataNotes, noteMarksFigure, RECORD_ONLY_REASONS, type DataNoteQuality, type DataNotesDataset, type DataNotesWire } from '@/features/analysis/lib/dataNotes'
import type { FactProvenance } from '@/features/analysis/lib/provenance'
import { SOURCE_OPERANDS_PREFIX } from '@/features/analysis/lib/narrativeDisplay'

/**
 * Rule-12 gate for the quiet notation (D-061; DESIGN.md, the Calculation Provenance Rule): a figure carries a mark only
 * where its note questions the number, a review note with a reason other than the record-only legacy_calculation.
 * Unknown and unavailable notes never mark. Every note stays in the evidence dialog and the data notes; the rule
 * applies where marks render, never to the notes model.
 *
 * 1. The helper. Each case of the shared notes fixture names the letters that mark (`marked_letters`, over the citation
 *    notes where a case has them); noteMarksFigure must pick exactly those. The backend asserts that one case covers
 *    every known reason (test_analysis_data_notes.py), so a new reason has to be classified here to pass.
 * 2. Every place a letter renders or is named. The whole report (KPI cards, trend charts, narrative, metrics table and
 *    the data notes) renders the fixture's record_only_and_mixed_marking case; every letter drawn (data-note-letter,
 *    a chart's notes band), named (a control's or chip's accessible name, a chart card's Notes chip, a chart's tooltip,
 *    raised at every period by its values stop, or that stop's spoken "data note x", the fold's "figures carry notes x"), set in the fine print's summary, the open
 *    lists' letter column or a chart's footnotes (which its PNG prints) is one of its marked letters, and each marked
 *    letter shows somewhere. A site that bypasses the helper shows the
 *    record-only a, the unknown d or the gap's e. The same render holds the notation's two other clauses at their full
 *    width: no † anywhere in an annual report (a † marks only a period: the Q4 header, the period picker), the fold's
 *    derived row included, and no drawn, listed or charted letter in warning ink.
 * 3. Every note stays. Each note keeps its entry in the open data notes (the report's) or under the sources (a citation
 *    supplement); the record-only note's entry keeps its words and counts; the summary never says "No figures need
 *    review" beside it, even where it sits on a growth figure alone and every value passed, and gives the mixed note's
 *    questioning clause, not the record-only sentence its words open with; the legacy figure's dialog says "Needs
 *    review", never that checks passed, and names no letter the page does not show. Filtering the notes model instead
 *    of the render sites fails here.
 */

interface GoldenCase {
  name: string
  dataset: DataNotesDataset
  expected: DataNotesWire
  citations?: DataNoteQuality[]
  expected_citation_notes?: DataNotesWire
  marked_letters: string[]
}
const golden: { cases: GoldenCase[] } = JSON.parse(readFileSync('../backend/tests/fixtures/analysis_data_notes.json', 'utf8'))
const colors = (createRequire(import.meta.url)('../../tailwind.config.js') as { theme: { extend: { colors: { warning: Record<string, string>; chart: { review: Record<string, string> } } } } }).theme.extend.colors
const notesOf = (example: GoldenCase) => (example.expected_citation_notes ?? example.expected).notes
const allNotes = golden.cases.flatMap(notesOf)

describe('which data notes mark their figure (D-061)', () => {
  it.each(golden.cases)('marks exactly the shared fixture\'s marked_letters: $name', (example) => {
    expect(Array.isArray(example.marked_letters), 'every case names its marked letters').toBe(true)
    expect(notesOf(example).filter(noteMarksFigure).map((note) => note.letter)).toEqual(example.marked_letters)
  })

  it('is tested on every kind of note the rule tells apart', () => {
    const recordOnly = (reasons: string[]) => reasons.length > 0 && reasons.every((reason) => RECORD_ONLY_REASONS.has(reason))
    // A review note about the record alone stays unmarked; a review note that mixes it with a questioning reason marks.
    expect(allNotes.some((note) => note.kind === 'review' && recordOnly(note.reasons) && !noteMarksFigure(note)), 'an unmarked record-only review note').toBe(true)
    expect(allNotes.some((note) => note.kind === 'review' && note.reasons.some((reason) => RECORD_ONLY_REASONS.has(reason)) && !recordOnly(note.reasons) && noteMarksFigure(note)), 'a marked mixed note').toBe(true)
    expect(allNotes.some((note) => note.kind === 'unknown' && !noteMarksFigure(note)), 'an unmarked unknown note').toBe(true)
    expect(allNotes.some((note) => note.kind === 'unavailable' && !noteMarksFigure(note)), 'an unmarked unavailable note').toBe(true)
  })
})

// ---- The whole report, on the record-only and mixed case ---------------------------------------------------------
const example = golden.cases.find((entry) => entry.name === 'record_only_and_mixed_marking')!
const report: AnalysisDataset = {
  ticker: 'TST', company_name: 'Test Co', mode: example.dataset.mode, period_key: example.dataset.period_key,
  data_as_of: '2026-10-25T00:00:00Z', snapshot_id: 'gate', inflections: [], data_notes: example.expected,
  periods: example.dataset.periods.map(({ key }) => ({ key, fiscal_year: Number(key.slice(2)), fiscal_period: 'FY', period_end: `${key.slice(2)}-12-31` })),
  series: example.dataset.series.map((series) => ({
    ...series, unit: series.percent ? 'pure' : 'USD', cagr: series.cagr ?? null, points: series.points.map((point) => ({ ...point })),
  })) as AnalysisDataset['series'],
}
// The case's two citations (the record-only note a, and the mixed supplement f), then a figure with no check recorded
// (note d) and a passed one, so the narrative's four operands fold under a summary that names its letters. The third is
// derived, a calculated figure in the fold and the sources list, where a dagger once stood beside it.
const cited = ['operating_margin', 'free_cash_flow', 'net_income', 'net_income'] as const
const citations: AnalysisCitation[] = [...example.citations!, {}, { provenance: { version: 1, method: 'reported', validation: 'passed', reasons: [], formula: null, inputs: [] } }]
  .map((quality, index) => ({
    ...quality, n: index + 1, marker: `F${index + 1}`, concept: cited[index], period: 'FY2024', value: 100 + index, unit: 'USD',
    excerpt: `${cited[index]} = ${100 + index} (FY2024)`, section_ref: `XBRL · ${cited[index]}`, verified: true, fragment_url: null, derived: index === 2,
  } as AnalysisCitation))
const narrative = `Margins held [1] while cash conversion moved [2].${SOURCE_OPERANDS_PREFIX}${citations.map((citation) => `${citation.concept} USD ${citation.value} in FY2024 [${citation.n}]${citation.derived ? ' (derived Q4)' : ''}`).join('; ')}.`

async function renderReport() {
  // This gate reads notation after the real chart chunk loads. Await its module before mounting so a cold
  // transform cannot consume waitFor's rendering deadline; the separate chunk spec covers loading and failure.
  await import('@/features/analysis/components/TrendChartsV2')
  const view = render(
    <DataNotesProvider dataset={report}>
      <KpiStrip dataset={report} />
      <TrendCharts dataset={report} />
      <NarrativePane state={{ status: 'done', text: narrative, completion: { kind: 'analysis', analysis_id: 1, narrative, citations, grounded: citations.length, unverified: 0, cached: false, n_periods: 2 } }} />
      <MetricsTable dataset={report} />
      <DataNotes dataset={report} />
    </DataNotesProvider>,
  )
  // The trend charts load as their own chunk (TrendCharts' next/dynamic): the scans wait for the plots.
  await waitFor(() => expect(view.container.querySelectorAll('[data-analysis-chart] > svg').length).toBeGreaterThan(0))
  return view
}

/** What each drawn chart shows and says beyond its plot, read from the page as a reader meets it: every period's tooltip,
 *  raised by stepping the chart's values stop from Home to End, the value text the stop speaks there, and the footnote
 *  lines under the plot (the lines its PNG prints). */
function readCharts(container: HTMLElement) {
  const periods: Array<{ tooltip: HTMLElement | null; spoken: string }> = []
  const stops = [...container.querySelectorAll<HTMLElement>('[role="slider"][data-chart-values]')]
  for (const stop of stops) {
    const card = stop.closest('section[data-trend-chart]')!
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Tab' })
    act(() => stop.focus())
    fireEvent.keyDown(stop, { key: 'Home' })
    for (let period = 0; period <= Number(stop.getAttribute('aria-valuemax')); period++) {
      if (period) fireEvent.keyDown(stop, { key: 'ArrowRight' })
      const tooltip = card.querySelector<HTMLElement>('[data-chart-tooltip]')
      periods.push({ tooltip: tooltip && (tooltip.cloneNode(true) as HTMLElement), spoken: stop.getAttribute('aria-valuetext') ?? '' })
    }
    act(() => stop.blur())
  }
  const footnotes = [...container.querySelectorAll('section[data-trend-chart] [data-chart-text="footnote"]')].map((line) => ({
    mark: line.querySelector('span')?.textContent ?? '', text: line.textContent ?? '',
  }))
  return {
    stops: stops.length, periods, footnotes,
    tooltips: periods.flatMap(({ tooltip }) => (tooltip ? [tooltip] : [])), spoken: periods.map(({ spoken }) => spoken),
  }
}

describe('every surface marks and names only the notes that question the number (D-061)', () => {
  it('draws, names and summarises only marked letters, and shows each of them', async () => {
    const { container } = await renderReport()
    const seen = new Map<string, Set<string>>()
    const saw = (where: string, letters: Iterable<string>) => {
      for (const letter of letters) seen.set(letter, (seen.get(letter) ?? new Set()).add(where))
    }
    saw('a drawn letter', [...container.querySelectorAll('[data-note-letter]')].map((mark) => mark.getAttribute('data-note-letter')!))
    saw('a chart band letter', [...container.querySelectorAll('[data-analysis-chart] svg [data-text="note"]')].map((letter) => letter.textContent!))
    const names = [...container.querySelectorAll('[aria-label]')].map((element) => element.getAttribute('aria-label')!)
    saw('a Notes chip', names.filter((name) => name.startsWith('Review data notes ')).flatMap((name) => name.slice('Review data notes '.length).split(', ')))
    saw('an accessible name', names.flatMap((name) => [...name.matchAll(/data note ([a-z]+)/g)].map((match) => match[1])))
    saw('the fold summary', [...container.querySelectorAll('.markdown-body details > summary')].flatMap((summary) =>
      (/figures carry notes? ([a-z, ]+)$/.exec(summary.textContent ?? '')?.[1] ?? '').split(', ').filter(Boolean)))
    const fine = container.querySelector('[data-analysis-data-notes] > details > summary')!
    saw('the data notes summary', [...(fine.textContent ?? '').matchAll(/Note ([a-z]+):/g)].map((match) => match[1]))
    // The open lists' letter column, under the table and under the narrative's sources.
    saw('the open data notes', [...container.querySelectorAll('li[id^="analysis-data-note-"] > span:first-child')]
      .flatMap((cell) => /([a-z]+)\.$/.exec(cell.textContent ?? '')?.[1] ?? []))
    // A chart card's own chip, every period's tooltip and spoken value (raised by its values stop) and its footnotes.
    saw('a chart chip', [...container.querySelectorAll('section[data-trend-chart] [aria-label^="Review data notes "]')]
      .flatMap((chip) => chip.getAttribute('aria-label')!.slice('Review data notes '.length).split(', ')))
    const charts = readCharts(container)
    // Blind to no chart and no period: every drawn chart has its values stop, and every period it steps to raises its own
    // tooltip, headed with the period the stop speaks.
    expect(charts.stops, 'a drawn chart without its values stop').toBe(container.querySelectorAll('[data-analysis-chart] > svg').length)
    expect(charts.periods.filter(({ tooltip, spoken }) => !spoken.startsWith(`${tooltip?.querySelector('p')?.textContent?.split(' · ')[0]}`))
      .map(({ spoken }) => spoken), 'a period whose tooltip is missing or another period’s').toEqual([])
    saw('a chart tooltip', charts.tooltips.flatMap((tooltip) => [...(tooltip.textContent ?? '').matchAll(/\(([a-z]+)\)/g)].map((match) => match[1])))
    saw('a chart value text', charts.spoken.flatMap((text) => [...text.matchAll(/data note ([a-z]+)/g)].map((match) => match[1])))
    saw('a chart footnote', charts.footnotes.map((footnote) => footnote.mark).filter((mark) => /^[a-z]+$/.test(mark)))

    const stray = [...seen].filter(([letter]) => !example.marked_letters.includes(letter)).map(([letter, where]) => `${letter}: ${[...where].join(', ')}`)
    expect(stray, 'a letter shown or named for a note that marks nothing').toEqual([])
    // The fixture's marked letters all show: b on the KPI card, the table and the cash chart, c on the table and the
    // balance sheet, f on its citation chip.
    expect([...seen.keys()].sort()).toEqual([...example.marked_letters].sort())
    for (const where of ['a drawn letter', 'a chart band letter', 'a Notes chip', 'an accessible name', 'the fold summary', 'the data notes summary', 'the open data notes', 'a chart chip', 'a chart tooltip', 'a chart value text', 'a chart footnote']) {
      expect([...seen.values()].some((places) => places.has(where)), `no ${where} was read: the scan went blind`).toBe(true)
    }
  })

  it('sets no dagger beside a figure and no letter in warning ink', async () => {
    const { container } = await renderReport()
    // No dagger, by the rule's width: the whole report's text (the charts' footnotes, the lines their PNG prints,
    // included), its accessible names, value texts and titles, and every chart's tooltip at every period. A † marks only
    // a period (the Q4 header and the period picker), and an annual report has neither.
    const charts = readCharts(container)
    const texts = [
      container.textContent ?? '',
      ...[...container.querySelectorAll('[aria-label], [aria-valuetext], [title]')].flatMap((element) =>
        ['aria-label', 'aria-valuetext', 'title'].map((name) => element.getAttribute(name) ?? '')),
      ...charts.tooltips.map((tooltip) => tooltip.textContent ?? ''),
      ...charts.spoken,
    ]
    expect(texts.filter((text) => text.includes('†')), 'a dagger in the report').toEqual([])
    // The scan reaches the calculated figures: the KPI cards, the table and the fold's derived row each say so in words.
    const fold = container.querySelector('.markdown-body details ul')!
    expect([...fold.querySelectorAll('li')].filter((row) => /, calculated/.test(row.textContent ?? '')), 'the fold\'s derived row').toHaveLength(1)
    expect(within(container.querySelector<HTMLElement>('[data-analysis-metrics]')!).getAllByRole('button', { name: /, calculated\. View source/ }).length).toBeGreaterThan(0)

    // No letter in warning ink (no mark uses it): a drawn letter, the open data notes' letters (under the table and the
    // sources), a chart's band letters, its tooltip's and its footnotes', by a class, an SVG paint or colour attribute or an
    // inline style (which the browser reads back as rgb()) on the letter, on anything around it it could inherit the ink
    // from, or on anything inside it that could draw its glyph. Out of reach: ink a stylesheet rule sets by another
    // selector, since the unit tests load no stylesheet.
    const rgb = (hex: string) => { const probe = document.createElement('i'); probe.style.color = hex; return probe.style.color }
    const warningHexes = [colors.warning, colors.chart.review].flatMap((pair) => Object.values(pair))
    const warningInks = new Set([...warningHexes.map((hex) => hex.toUpperCase()), ...warningHexes.map(rgb)])
    const letters = {
      drawn: [...container.querySelectorAll('[data-note-letter]')],
      listed: [...container.querySelectorAll('li[id^="analysis-data-note-"] > span:first-child')].filter((letter) => letter.textContent),
      charted: [...container.querySelectorAll('[data-analysis-chart] svg [data-text="note"]')],
      tooltip: charts.tooltips.flatMap((tooltip) => [...tooltip.querySelectorAll<HTMLElement>('span')].filter((span) => /^ \([a-z]+\)$/.test(span.textContent ?? ''))),
      footnote: [...container.querySelectorAll('section[data-trend-chart] [data-chart-text="footnote"] > span')].filter((mark) => /^[a-z]+$/.test(mark.textContent ?? '')),
    }
    for (const [kind, found] of Object.entries(letters)) expect(found.length, `no ${kind} letter was read: the scan went blind`).toBeGreaterThan(0)
    const inked = (element: Element) => ['fill', 'stroke', 'color'].some((ink) => warningInks.has((element.getAttribute(ink) ?? '').toUpperCase())
      || warningInks.has((element as HTMLElement).style?.getPropertyValue(ink) ?? ''))
    const warningClass = ['text', 'fill', 'stroke'].flatMap((ink) => [`[class*="${ink}-warning"]`, `[class*="${ink}-chart-review"]`]).join(', ')
    const sources = (letter: Element) => { const chain = [...letter.querySelectorAll('*')]; for (let at: Element | null = letter; at; at = at.parentElement) chain.push(at); return chain }
    const inWarning = Object.values(letters).flat().filter((letter) => sources(letter).some((element) => element.matches(warningClass) || inked(element)))
    expect(inWarning.map((letter) => letter.outerHTML), 'a letter in warning ink').toEqual([])
  })

  it('keeps every note in the data notes and the record-only figure\'s note in its dialog', async () => {
    const { container } = await renderReport()
    const fine = container.querySelector<HTMLElement>('[data-analysis-data-notes]')!
    for (const note of notesOf(example)) {
      const entry = document.getElementById(note.id)
      expect(entry, `${note.letter} (${note.kind} ${note.reasons.join('+')}) has its entry`).not.toBeNull()
      expect(entry, note.letter).toHaveTextContent(note.message)
      // Report notes live in the data notes under the table; a citation supplement under the narrative's sources.
      if (example.expected.notes.some((reportNote) => reportNote.key === note.key)) expect(fine.contains(entry), note.letter).toBe(true)
    }
    const legacy = example.expected.notes.find((note) => note.reasons.every((reason) => RECORD_ONLY_REASONS.has(reason)))!
    expect(document.getElementById(legacy.id)).toHaveTextContent('Operating margin (FY2023, FY2024)')
    expect(document.getElementById(legacy.id)).toHaveTextContent('2 figures · 1 YoY comparison.')
    // Every populated figure that is not legacy, missing its record or the conflict passed: still never "No figures
    // need review" while the record-only note stands.
    expect(fine.querySelector('summary')).not.toHaveTextContent('No figures need review')
    // The mixed note b marks for its other reason: the summary gives that clause, never the record-only sentence its
    // words open with.
    const mixed = example.expected.notes.find((note) => note.letter === 'b')!
    expect(mixed.reasons).toEqual(['legacy_calculation', 'source_check_needed'])
    expect(mixed.message).toMatch(/^This saved calculation predates the current source checks\. .*A source check remains unresolved\./)
    expect(fine.querySelector('summary')).toHaveTextContent('Note b: b Free cash flow FY2024: A source check remains unresolved')
    expect(fine.querySelector('summary')).not.toHaveTextContent('predates the current source checks')

    const figure = within(container.querySelector<HTMLElement>('[data-analysis-metrics]')!).getByRole('button', { name: /^Operating margin, FY2024: .*, calculated\. View source/ })
    expect(figure.querySelector('[data-note-letter]')).toBeNull()
    await userEvent.click(figure)
    const checks = within(document.querySelector<HTMLElement>('[role="dialog"]')!).getByRole('heading', { name: 'Checks' }).closest('section')!
    expect(checks).toHaveTextContent('Needs review')
    expect(checks).toHaveTextContent(legacy.message)
    expect(checks).not.toHaveTextContent('Automated checks passed')
    // The figure's YoY carries the record-only note too: the dialog reads it in words and names no letter the page does
    // not show, in its text or its accessible names.
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!
    expect(dialog).toHaveTextContent('The recorded inputs do not identify which input this note comes from.')
    const unmarked = notesOf(example).filter((note) => !noteMarksFigure(note)).map((note) => note.letter)
    const naming = new RegExp(`\\b[Nn]otes? (?:${unmarked.join('|')})\\b`)
    expect([dialog.textContent ?? '', ...[...dialog.querySelectorAll('[aria-label]')].map((element) => element.getAttribute('aria-label')!)]
      .filter((text) => naming.test(text)), 'the dialog names a letter the page does not show').toEqual([])
  })
})

// ---- The all-clear, with a record-only note on a growth figure alone ----------------------------------------------
// Every value passed and none lacks its record; the FY2024 YoY's prior input is a legacy calculation, so the YoY carries
// legacy_calculation alone. That note marks nothing, so the summary has no letter to name, and only DataNotes' guard
// keeps "No figures need review" from it. With the YoY passed, the same report earns it.
const passedFact: FactProvenance = { version: 1, method: 'reported', validation: 'passed', reasons: [], formula: null, inputs: [] }
const growthOnly = (yoy: FactProvenance): AnalysisDataset => ({
  ticker: 'TST', company_name: 'Test Co', mode: 'annual', period_key: 'FY2023..FY2024', data_as_of: '2026-10-25T00:00:00Z',
  snapshot_id: `growth-${yoy.validation}`, inflections: [],
  periods: [2023, 2024].map((year) => ({ key: `FY${year}`, fiscal_year: year, fiscal_period: 'FY', period_end: `${year}-12-31` })),
  series: [{ concept: 'revenue', label: 'Revenue', unit: 'USD', percent: false, cagr: null, points: [
    { period: 'FY2023', value: 100, provenance: passedFact },
    { period: 'FY2024', value: 110, provenance: passedFact, yoy: 0.1, yoy_provenance: yoy },
  ] }],
})

describe('the data notes never clear a report while a record-only note stands (D-061)', () => {
  const summary = () => document.querySelector('[data-analysis-data-notes] > details > summary')!

  it('holds back "No figures need review" for a legacy note on a growth figure alone, and says it once that growth passed', () => {
    const legacy = growthOnly({ ...passedFact, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] })
    // Every value passed and none is unknown: the counts alone would clear the report.
    expect(groupDataNotes(legacy).totals).toMatchObject({ reviewValues: 0, reviewComparisons: 1, unknown: 0, passed: 2 })
    const view = render(<DataNotes dataset={legacy} />)
    expect(summary()).not.toHaveTextContent('No figures need review')
    expect(summary().querySelector('[data-note-letter]')).toBeNull()
    const note = groupDataNotes(legacy).notes[0]
    expect(noteMarksFigure(note)).toBe(false)
    expect(document.getElementById(note.id)).toHaveTextContent(note.message)
    view.unmount()

    render(<DataNotes dataset={growthOnly({ ...passedFact, method: 'calculated' })} />)
    expect(summary()).toHaveTextContent('No figures need review · 2 checked')
  })
})
