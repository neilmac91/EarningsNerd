// The zone every render below reads (Node re-reads process.env.TZ on assignment): New York, behind UTC.
process.env.TZ = 'America/New_York'

import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// recharts measures the DOM, which jsdom can't do: stub it, as analysis-teaser.spec.tsx does.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))
vi.mock('react-markdown', () => ({ default: ({ children }: { children: string }) => <div>{children}</div> }))
vi.mock('remark-gfm', () => ({ default: () => null }))
// The page reads its link through useSearchParams; PeekLocked's UpgradeModal calls useRouter.
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(), useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/features/companies/components/CompanySearch', () => ({ default: ({ onSelect }: { onSelect: (ticker: string) => void }) => <button onClick={() => onSelect('REGN')}>Select Regeneron</button> }))
vi.mock('@/lib/analytics', () => ({ default: { analysisRun: vi.fn() } }))
vi.mock('@/features/analysis/api/analysis-api', async (original) => ({ ...await original<typeof import('@/features/analysis/api/analysis-api')>(), getAnalysisDataset: vi.fn(), streamAnalysis: vi.fn() }))

import { Card } from '@/components/ui'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'
import AnalysisTeaser from '@/features/analysis/components/AnalysisTeaser'
import ResultsHeader from '@/features/analysis/components/ResultsHeader'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'
import { getAnalysisDataset, streamAnalysis, type AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { SAMPLE_ANALYSIS_DATASET } from '@/features/marketing/lib/landing-samples'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The results header (MPA WP4b; coherence §4.1 N1, §4.4): one line on the page ground at the top of a run's results,
 * "Regeneron Pharmaceuticals, Inc. · REGN · Annual FY2016–FY2025 · data as of October 24, 2026", read from the run on
 * screen. It names the results' region, so the module headings keep their h2 under the page h1. Its clauses break
 * between, never inside: each is an inline-block carrying the separator after it on a no-break space, so no line
 * starts with "·". The feedback launcher steps aside from it as from the KPI strip. The page's control card drops to
 * the control level, a hairline with no shadow (Card elevation="none"). The Free teaser and the landing demo take no
 * header: their caption and title bar name the sample, which has no live date. Its source date shares the data notes'
 * hook; analysis-source-date.spec.tsx holds that day on both surfaces. The geometry (12px over the KPI strip, the module gaps, the computed border and shadow, the
 * clauses whole on a phone) is tests/e2e/analysis-layout.spec.ts "analysis results header".
 */

const REGN: AnalysisDataset = {
  ...SAMPLE_ANALYSIS_DATASET,
  ticker: 'REGN',
  // EDGAR's conformed name, in capitals: the header prints the display form.
  company_name: 'REGENERON PHARMACEUTICALS, INC.',
  mode: 'annual',
  period_key: 'FY2016..FY2025',
  data_as_of: '2026-10-24T15:00:00Z',
}

const clauses = (root: ParentNode) => [...root.querySelectorAll('[data-results-clause]')].map((clause) => clause.textContent)

afterEach(() => vi.restoreAllMocks())

describe('the results header', () => {
  it('names the run: display name, ticker, mode with its range, and the source day', () => {
    const { container } = render(<ResultsHeader dataset={REGN} id="results" />)
    const header = container.querySelector('[data-analysis-results-header]')!
    expect(header.tagName).toBe('P')
    expect(header).toHaveAttribute('id', 'results')
    expect(header).toHaveTextContent(/^Regeneron Pharmaceuticals, Inc\. · REGN · Annual FY2016–FY2025 · data as of October 24, 2026$/)
    // The ticker in the data face, as the page's company row sets it; the name in the primary ink at 600; the line in
    // the secondary ink, on the ground (no card).
    expect(within(header as HTMLElement).getByText('REGN')).toHaveClass('tnum', 'font-data')
    expect(within(header as HTMLElement).getByText('Regeneron Pharmaceuticals, Inc.')).toHaveClass('font-semibold', 'text-text-primary-light', 'dark:text-text-primary-dark')
    expect(header).toHaveClass('text-sm', 'text-text-secondary-light', 'dark:text-text-secondary-dark')
    expect(header.className).not.toMatch(/\b(?:bg-|border|shadow-|rounded)/)
    // The feedback launcher steps aside from the run's name as from its figures (lib/launcherKeepClear); the browser
    // holds what it does at 390px (tests/e2e/feedback-launcher-keep-clear.spec.ts (d) and (e)).
    expect(header).toHaveAttribute('data-launcher-keep-clear')
  })

  it.each([
    ['a quarterly run', { mode: 'quarterly', period_key: '2023Q3..2026Q2' }, 'Quarterly Q3 2023–Q2 2026'],
    ['a one-year run', { period_key: 'FY2021..FY2021' }, 'Annual FY2021'],
  ] as const)('prints %s as the chart PNG header does', (_, edit, range) => {
    const { container } = render(<ResultsHeader dataset={{ ...REGN, ...edit }} id="results" />)
    expect(clauses(container)[2]).toBe(`${range}\u00A0·`)
  })

  it('starts at the ticker when the run names no company, with no empty clause', () => {
    const { container } = render(<ResultsHeader dataset={{ ...REGN, company_name: '' }} id="results" />)
    expect(container.querySelector('[data-analysis-results-header]')).toHaveTextContent(/^REGN · Annual FY2016–FY2025 · data as of October 24, 2026$/)
    expect(clauses(container)).toHaveLength(3)
  })

  it('breaks between clauses, never inside one, and never starts a line with the separator', () => {
    const { container } = render(<ResultsHeader dataset={REGN} id="results" />)
    const header = container.querySelector('[data-analysis-results-header]')!
    const parts = [...header.querySelectorAll('[data-results-clause]')]
    expect(parts.map((part) => part.textContent)).toEqual([
      'Regeneron Pharmaceuticals, Inc.\u00A0·',
      'REGN\u00A0·',
      'Annual FY2016–FY2025\u00A0·',
      'data as of October 24, 2026',
    ])
    // Each clause is one box a line moves whole, until it alone is wider than the line.
    for (const part of parts) expect(part).toHaveClass('inline-block', 'max-w-full')
    // Between two clauses the header holds one ordinary space, its only break opportunity; every separator sits inside
    // the clause before it, joined by a no-break space, so a line ends on "·" and none starts with it.
    const between = [...header.childNodes].filter((node) => !(node instanceof Element && node.matches('[data-results-clause]')))
    expect(between.map((node) => node.textContent)).toEqual([' ', ' ', ' '])
    for (const part of parts) expect(part.textContent).not.toMatch(/^\s*·| ·/)
  })
})

describe('on the analysis page', () => {
  async function runPage(dataset: AnalysisDataset) {
    vi.mocked(getAnalysisDataset).mockResolvedValue(dataset)
    vi.mocked(streamAnalysis).mockImplementation(async () => {})
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.currentUser(), { id: 7 })
    client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
    client.setQueryData(queryKeys.analysisCoverage('REGN'), {
      ticker: 'REGN', company_name: 'Regeneron (as the picker read it)', supported: true,
      annual: dataset.periods.map((period) => ({ ...period, has_core: true })), quarterly: [], limits: { annual: 10, quarterly: 12 },
    })
    const view = render(<QueryClientProvider client={client}><AnalysisPageClient /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Select Regeneron' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Run analysis' }))
    return view
  }

  it('names the results region with the run, above the KPI strip, the module headings kept at h2', async () => {
    await runPage(REGN)
    // The region is named by the header, from the run on screen, not the picker's reading of the company. Each
    // separator follows its clause on a no-break space, which the name keeps.
    const results = await screen.findByRole('region', { name: /^Regeneron Pharmaceuticals, Inc\.\u00A0· REGN\u00A0· Annual FY2016–FY2025\u00A0· data as of October 24, 2026$/ })
    const header = results.querySelector('[data-analysis-results-header]')!
    expect(results.getAttribute('aria-labelledby')).toBe(header.id)
    // The header and the KPI strip are one block, 12px apart; the modules are 16px apart on a phone and 24px from sm.
    const block = header.parentElement!
    expect(block.parentElement).toBe(results)
    expect(block.firstElementChild).toBe(header)
    expect(header.nextElementSibling?.querySelector('[data-analysis-kpi]')).not.toBeNull()
    expect(block).toHaveClass('flex', 'flex-col', 'gap-3')
    expect(results).toHaveClass('flex', 'flex-col', 'gap-4', 'sm:gap-6')
    expect(results.firstElementChild).toBe(block)
    // The modules' headings stay h2, under the page's one h1, and the header is none.
    expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual(['Multi-Period Analysis'])
    const levels = within(results).getAllByRole('heading').map((heading) => heading.tagName)
    expect(levels.length).toBeGreaterThan(2)
    expect(new Set(levels)).toEqual(new Set(['H2']))
    expect(within(results).getByRole('heading', { name: 'Metrics by period' }).tagName).toBe('H2')
  })

  it('sets the company and period form at the control level: a hairline, no shadow', async () => {
    const { container } = await runPage(REGN)
    await screen.findByRole('region', { name: /^Regeneron Pharmaceuticals/ })
    const controls = container.querySelector('[data-analysis-controls]')!
    expect(controls).toHaveClass('border', 'border-border-light', 'bg-panel-light', 'dark:border-white/10', 'dark:bg-panel-dark')
    expect(controls.className).not.toMatch(/(?:^|\s)shadow-e\d/)
    // The results' own cards keep their lift.
    expect(container.querySelector('[data-analysis-kpi]')).toHaveClass('shadow-e2')
  })
})

describe('Card elevation', () => {
  it.each([
    ['none', []],
    ['e1', ['shadow-e1']],
    ['e2', ['shadow-e2']],
    [undefined, ['shadow-e2']],
  ] as const)('%s keeps the panel and the hairline and lifts by its shadow only', (elevation, shadows) => {
    const { container } = render(<Card elevation={elevation}>x</Card>)
    const card = container.firstElementChild!
    expect(card).toHaveClass('rounded-xl', 'border', 'border-border-light', 'bg-panel-light', 'dark:shadow-none')
    expect(card.className.split(/\s+/).filter((name) => /^shadow-e\d$/.test(name))).toEqual(shadows)
  })
})

describe('the sample surfaces', () => {
  it.each([['the Free teaser', AnalysisTeaser], ['the landing demo', AnalysisDemo]] as const)('%s takes no results header and claims no live date for its sample', (_, Component) => {
    const { container } = render(<Component />)
    expect(container.querySelector('[data-analysis-results-header]')).toBeNull()
    // Its run line names the sample; the only source date it prints is the saved run's, in its data notes' detail.
    const notes = container.querySelector('[data-analysis-data-notes]')!
    const outsideNotes = (container.textContent ?? '').replace(notes.textContent ?? '', '')
    expect(outsideNotes).not.toMatch(/as of/i)
    expect(notes).toHaveTextContent('sample data (one saved run)')
  })

  it("the Free teaser's preview stands its modules as the page does: 16px apart on a phone, 24px from sm", () => {
    const { container } = render(<AnalysisTeaser />)
    const strip = container.querySelector('[data-analysis-kpi]')!.closest('[data-launcher-keep-clear]')!
    expect(strip.parentElement).toHaveClass('flex', 'flex-col', 'gap-4', 'sm:gap-6')
  })
})
