import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { describe, expect, it, vi } from 'vitest'
import { render, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const tooltips = vi.hoisted(() => ({ contents: [] as Array<(props: Record<string, unknown>) => React.ReactNode> }))

// Recharts measures the DOM, which jsdom cannot do: the trend-charts specs' stub, drawing each Line's dots and each
// Bar's shapes from the chart's rows, so every chart mark renders through TrendCharts' own note lookup.
vi.mock('recharts', async () => {
  const { createContext, useContext } = await import('react')
  type Row = Record<string, number | string | null>
  const Data = createContext<Row[]>([])
  const Chart = ({ children, data }: { children: React.ReactNode; data: Row[] }) => <Data.Provider value={data}><svg>{children}</svg></Data.Provider>
  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ComposedChart: Chart,
    LineChart: Chart,
    Rectangle: (props: React.SVGProps<SVGRectElement>) => <rect {...props} />,
    usePlotArea: () => ({ x: 0, y: 0, width: 300, height: 160 }),
    useXAxisScale: () => {
      const rows = useContext(Data)
      return (period: string) => rows.findIndex((row) => row.period === period) * 20
    },
    useYAxisScale: () => (value: number) => 100 - value,
    Bar: ({ dataKey, shape }: { dataKey: string; shape: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g>{rows.map((row, index) => <g key={index}>{row[dataKey] == null ? null : shape({ x: index * 20, y: 10, width: 15, height: 20, payload: row })}</g>)}</g>
    },
    Line: ({ dataKey, dot }: { dataKey: string; dot: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g>{rows.map((row, index) => <g key={index}>{dot({ cx: index * 20, cy: 50, value: row[dataKey], payload: row })}</g>)}</g>
    },
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: ({ content }: { content: (props: Record<string, unknown>) => React.ReactNode }) => {
      tooltips.contents.push(content)
      return null
    },
  }
})

import DataNotes from '@/features/analysis/components/DataNotes'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import KpiStrip from '@/features/analysis/components/KpiStrip'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import NarrativePane from '@/features/analysis/components/NarrativePane'
import TrendCharts from '@/features/analysis/components/TrendCharts'
import type { AnalysisCitation, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { chartDataNotes } from '@/features/analysis/lib/chartExport'
import { groupDataNotes, noteMarksFigure, RECORD_ONLY_REASONS, resolveDataNotes, type DataNoteQuality, type DataNotesDataset, type DataNotesWire } from '@/features/analysis/lib/dataNotes'
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
 *    a chart's "Data note x" mark), named (a control's or chip's accessible name, a chart tooltip's "· note x", the
 *    fold's "figures carry notes x"), set in the fine print's summary, the open lists' letter column or a chart's PNG
 *    footer (chartDataNotes) is one of its marked letters, and each marked letter shows somewhere. A site that bypasses the helper shows the
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

function renderReport() {
  tooltips.contents = []
  return render(
    <DataNotesProvider dataset={report}>
      <KpiStrip dataset={report} />
      <TrendCharts dataset={report} />
      <NarrativePane state={{ status: 'done', text: narrative, completion: { kind: 'analysis', analysis_id: 1, narrative, citations, grounded: citations.length, unverified: 0, cached: false, n_periods: 2 } }} />
      <MetricsTable dataset={report} />
      <DataNotes dataset={report} />
    </DataNotesProvider>,
  )
}

/** Every chart tooltip's text, at every period, over every series it can name. */
function tooltipTexts(): string[] {
  const payload = report.series.map((series) => ({ dataKey: series.concept, name: series.label, value: 1 }))
  return tooltips.contents.flatMap((content) => report.periods.map(({ key }) => {
    const tip = render(<>{content({ active: true, label: key, payload })}</>)
    const text = tip.container.textContent ?? ''
    tip.unmount()
    return text
  }))
}

describe('every surface marks and names only the notes that question the number (D-061)', () => {
  it('draws, names and summarises only marked letters, and shows each of them', () => {
    const { container } = renderReport()
    const seen = new Map<string, Set<string>>()
    const saw = (where: string, letters: Iterable<string>) => {
      for (const letter of letters) seen.set(letter, (seen.get(letter) ?? new Set()).add(where))
    }
    saw('a drawn letter', [...container.querySelectorAll('[data-note-letter]')].map((mark) => mark.getAttribute('data-note-letter')!))
    saw('a chart mark', [...container.querySelectorAll('g[aria-label^="Data note "]')].map((mark) => mark.getAttribute('aria-label')!.slice('Data note '.length)))
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
    expect(tooltips.contents.length, 'the charts drew their tooltips').toBeGreaterThan(0)
    for (const text of tooltipTexts()) saw('a chart tooltip', [...text.matchAll(/· note ([a-z]+)/g)].map((match) => match[1]))
    // A chart's PNG footer and its chip read chartDataNotes; the footer is drawn only on export, so read it here.
    const panel = chartDataNotes(report, report.series, resolveDataNotes(report), true)
    saw('a chart panel', panel.panelNotes.map((note) => note.letter))
    saw('a PNG footer', panel.exportNotes.flatMap((line) => [...line.matchAll(/^Note ([a-z]+):/g)].map((match) => match[1])))

    const stray = [...seen].filter(([letter]) => !example.marked_letters.includes(letter)).map(([letter, where]) => `${letter}: ${[...where].join(', ')}`)
    expect(stray, 'a letter shown or named for a note that marks nothing').toEqual([])
    // The fixture's marked letters all show: b on the KPI card, the table and the cash chart, c on the table and the
    // balance sheet, f on its citation chip.
    expect([...seen.keys()].sort()).toEqual([...example.marked_letters].sort())
    for (const where of ['a drawn letter', 'a chart mark', 'a Notes chip', 'an accessible name', 'the fold summary', 'the data notes summary', 'the open data notes', 'a chart tooltip', 'a chart panel', 'a PNG footer']) {
      expect([...seen.values()].some((places) => places.has(where)), `no ${where} was read: the scan went blind`).toBe(true)
    }
  })

  it('sets no dagger beside a figure and no letter in warning ink', () => {
    const { container } = renderReport()
    // No dagger, by the rule's width: the whole report's text, its accessible names and titles, every chart tooltip and
    // the PNG footer. A † marks only a period (the Q4 header and the period picker), and an annual report has neither.
    const texts = [
      container.textContent ?? '',
      ...[...container.querySelectorAll('[aria-label], [title]')].flatMap((element) => [element.getAttribute('aria-label') ?? '', element.getAttribute('title') ?? '']),
      ...tooltipTexts(),
      ...chartDataNotes(report, report.series, resolveDataNotes(report), true).exportNotes,
    ]
    expect(texts.filter((text) => text.includes('†')), 'a dagger in the report').toEqual([])
    // The scan reaches the calculated figures: the KPI cards, the table and the fold's derived row each say so in words.
    const fold = container.querySelector('.markdown-body details ul')!
    expect([...fold.querySelectorAll('li')].filter((row) => /, calculated/.test(row.textContent ?? '')), 'the fold\'s derived row').toHaveLength(1)
    expect(within(container.querySelector<HTMLElement>('[data-analysis-metrics]')!).getAllByRole('button', { name: /, calculated\. View source/ }).length).toBeGreaterThan(0)

    // No letter in warning ink (no mark uses it): a drawn letter, the open data notes' letters (under the table and the
    // sources), a chart's letters, by a class on the letter or around it, or by an SVG fill.
    const warningInks = new Set([colors.warning, colors.chart.review].flatMap((pair) => Object.values(pair)).map((hex) => hex.toUpperCase()))
    const letters = {
      drawn: [...container.querySelectorAll('[data-note-letter]')],
      listed: [...container.querySelectorAll('li[id^="analysis-data-note-"] > span:first-child')].filter((letter) => letter.textContent),
      charted: [...container.querySelectorAll('g[aria-label^="Data note "] text')],
    }
    for (const [kind, found] of Object.entries(letters)) expect(found.length, `no ${kind} letter was read: the scan went blind`).toBeGreaterThan(0)
    const inWarning = Object.values(letters).flat().filter((letter) =>
      letter.closest('[class*="text-warning"], [class*="fill-warning"]') || warningInks.has((letter.getAttribute('fill') ?? '').toUpperCase()))
    expect(inWarning.map((letter) => letter.outerHTML), 'a letter in warning ink').toEqual([])
  })

  it('keeps every note in the data notes and the record-only figure\'s note in its dialog', async () => {
    const { container } = renderReport()
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
