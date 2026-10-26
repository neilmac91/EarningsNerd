import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { buildChartModel } from '@/features/analysis/lib/charts/model'
import { resolveDataNotes, type DataNote } from '@/features/analysis/lib/dataNotes'
import { comparisonLocations, selectHeadlineFigures, topLineConcept } from '@/features/analysis/lib/reportPresentation'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { case: string; dataset: AnalysisDataset }>
}
const dataset = (name: string) => structuredClone(FIXTURE.datasets[name].dataset)

describe('the first chart and the notes agree on what it draws', () => {
  const yoyNote = (concept: string, period: string) => ({ comparisons: [{ concept, period, basis: 'yoy' }] }) as unknown as DataNote

  it('a note names the growth chart for a comparison it plots, and not once the top line is in two currencies', () => {
    const ds = dataset('REGN_annual')
    expect(comparisonLocations(ds, resolveDataNotes(ds))(yoyNote('revenue', 'FY2024'))[0].chart).toBe(1)
    ds.series.find((series) => series.concept === 'revenue')!.points[3].unit = 'EUR'
    expect(comparisonLocations(ds, resolveDataNotes(ds))(yoyNote('revenue', 'FY2024'))[0].chart).toBe(0)
  })

  it('with no top line in the window, the engine draws no first chart', () => {
    const ds = dataset('LOVE_annual')
    ds.series = ds.series.filter((series) => series.concept !== 'net_interest_income')
    ds.series.find((series) => series.concept === 'revenue')!.points = []
    expect(buildChartModel('topline', ds).panels).toEqual([])
  })
})

describe('the top line the KPI strip, the notes and the first chart share (D16)', () => {
  it('an insurer’s is premiums earned, a bank’s net interest income', () => {
    expect(topLineConcept(dataset('PGR_quarterly'))).toBe('premiums_earned')
    expect(selectHeadlineFigures(dataset('PGR_quarterly'))[0].series.concept).toBe('premiums_earned')
    expect(topLineConcept(dataset('JPM_annual'))).toBe('net_interest_income')
    expect(topLineConcept(dataset('LOVE_annual'))).toBe('revenue')
    expect(topLineConcept(dataset('O_annual'))).toBe('revenue')
  })

  it('revenue with no value in the window gives way to the next top line', () => {
    const ds = dataset('LOVE_annual')
    ds.series.find((series) => series.concept === 'revenue')!.points = []
    expect(topLineConcept(ds)).toBe('net_interest_income')
    expect(selectHeadlineFigures(ds)[0].series.concept).toBe('net_interest_income')
  })
})
