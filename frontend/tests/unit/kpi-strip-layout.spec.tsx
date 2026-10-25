import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import KpiStrip from '@/features/analysis/components/KpiStrip'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { KPI_FACE_GLYPHS, KPI_FIGURE_ADVANCE, KPI_MARK_ADVANCE, KPI_MARK_GAP, kpiValueWidth } from '@/features/analysis/lib/kpiStripLayout'
import { compactCurrencyCountUp, fmtCurrency } from '@/lib/format'
import { SAMPLE_ANALYSIS_DATASET } from '@/features/marketing/lib/landing-samples'

type Theme = { fontSize: Record<string, [string, unknown]>; spacing: Record<string, string>; borderWidth: Record<string, string> }
const require = createRequire(import.meta.url)
const theme = (require('tailwindcss/resolveConfig') as (config: unknown) => { theme: Theme })(require('../../tailwind.config.js')).theme
const here = path.dirname(fileURLToPath(import.meta.url))
const source = (file: string) => readFileSync(path.resolve(here, '../..', file), 'utf8')
const STRIP = source('features/analysis/components/KpiStrip.tsx')
const rem = (value: string) => parseFloat(value)
/** The figure face's advance: Geist Mono's every glyph, and EN Figure Minus draws the minus at it (DESIGN.md). */
const ADVANCE = 0.6

const dataset = (unit: string, values: number[]): AnalysisDataset => ({
  ticker: 'TST', company_name: 'Test Co', mode: 'annual', period_key: 'FY2024..FY2025',
  periods: [
    { key: 'FY2024', fiscal_year: 2024, fiscal_period: 'FY', period_end: '2024-12-31' },
    { key: 'FY2025', fiscal_year: 2025, fiscal_period: 'FY', period_end: '2025-12-31' },
  ],
  series: (['revenue', 'net_income', 'free_cash_flow'] as const).slice(0, values.length).map((concept, index) => ({
    concept, label: concept, unit, percent: false, cagr: null,
    points: [{ period: 'FY2024', value: values[index] / 2 }, { period: 'FY2025', value: values[index], derived: concept === 'free_cash_flow' }],
  })),
  inflections: [],
})

describe('the KPI strip sizes its columns from its widest value (E197)', () => {
  it('measures a value with the tokens that draw it', () => {
    const marks = source('features/analysis/components/DataNoteMark.tsx')
    expect(STRIP).toMatch(/data-kpi-value className="[^"]*\btext-2xl\b/)
    expect(marks).toMatch(/const MARK = '[^']*\btext-data-xs\b/)
    expect(marks.match(/\$\{(dagger|letter)\} ml-0\.5 /g), 'the dagger and the letter each keep 2px').toHaveLength(2)
    expect(KPI_FIGURE_ADVANCE).toBeCloseTo(ADVANCE * rem(theme.fontSize['2xl'][0]), 9)
    expect(KPI_MARK_ADVANCE).toBeCloseTo(ADVANCE * rem(theme.fontSize['data-xs'][0]), 9)
    expect(KPI_MARK_GAP).toBe(rem(theme.spacing['0.5']))
    // E197's two cases, 138.2px each at a 16px root: CHF at 320px and CA$ at 360px.
    expect(kpiValueWidth('CHF 22.8B', true)).toBeCloseTo(8.6375, 9)
    expect(kpiValueWidth('CA$968.0M', true)).toBeCloseTo(8.6375, 9)
    expect(kpiValueWidth('$1.7B', true, 'ab')).toBeCloseTo(5 * 0.9 + (0.125 + 0.4125) + (0.125 + 2 * 0.4125), 9)
    expect(kpiValueWidth('-36.1%', false)).toBeCloseTo(6 * 0.9, 9)
  })

  it('adds the card\'s padding and border to the value, as the cards draw them', () => {
    expect(STRIP).toMatch(/<Card className="[^"]*\bp-3 sm:p-4\b/)
    expect(source('components/ui/Card.tsx')).toMatch(/'border border-border-light/)
    expect(theme.borderWidth.DEFAULT).toBe('1px')
    expect(STRIP).toContain(`[--kpi-card:calc(var(--kpi-value)_+_${2 * rem(theme.spacing['3'])}rem_+_2px)]`)
    expect(STRIP).toContain(`sm:[--kpi-card:calc(var(--kpi-value)_+_${2 * rem(theme.spacing['4'])}rem_+_2px)]`)
    // The shares of the strip leave room for the grid's gap (gap-3).
    expect(STRIP).toMatch(/'grid gap-3 /)
    const gap = rem(theme.spacing['3'])
    expect(STRIP).toContain(`[--kpi-half:calc((100%_-_${gap}rem)_/_2_-_0.5px)]`)
    expect(STRIP).toContain(`[--kpi-each:calc((100%_-_(var(--kpi-cols)_-_1)_*_${gap}rem)_/_var(--kpi-cols)_-_0.5px)]`)
  })

  it('takes two cards or one below lg, one per tile (four at most), two or one from lg, and one below 17em', () => {
    // KPI_GRID's own rule, evaluated: its custom properties and its tracks' minimum for a viewport, a strip width and a
    // root size, then auto-fill's count, floor((strip + gap) / (minimum + gap)).
    const grid = STRIP.match(/const KPI_GRID = '([^']*)'/)?.[1] ?? ''
    const classes = grid.split(' ')
    const gap = rem(theme.spacing['3'])
    /** The tracks' minimum as a function of the strip's width, for one viewport, root, value and tile count. */
    const minimum = (viewport: number, root: number, value: number, tiles: number) => {
      const vars: Record<string, string> = { 'kpi-value': `${value}rem`, 'kpi-cols': `${tiles}` }
      let template = ''
      for (const name of classes) {
        const match = /^(sm:|lg:)?\[(--[\w-]+|grid-template-columns):(.+)\]$/.exec(name)
        if (!match || (match[1] === 'sm:' && viewport < 640) || (match[1] === 'lg:' && viewport < 1024)) continue
        if (match[2] === 'grid-template-columns') template = match[3]
        else vars[match[2].slice(2)] = match[3]
      }
      let expression = /^repeat\(auto-fill,minmax\((.+),1fr\)\)$/.exec(template)?.[1] ?? 'NaN'
      for (let depth = 0; depth < 5; depth++) expression = expression.replace(/var\(--([\w-]+)\)/g, (_, key: string) => `(${vars[key]})`)
      const js = expression.replace(/_/g, ' ').replace(/calc\(/g, '(').replace(/max\(/g, 'Math.max(').replace(/min\(/g, 'Math.min(')
        .replace(/(\d*\.?\d+)rem/g, `($1*${root})`).replace(/(\d*\.?\d+)px/g, '($1)').replace(/100%/g, '(strip)')
      return new Function('strip', `return (${js})`) as (strip: number) => number
    }
    const fallback = classes.includes('[@container(width<17em)]:grid-cols-1')
    // The values of E197 and of the fixtures, in rem on one line: "$60.8B", "$1.7B†", "$1.7B†a", "CHF 22.8B†", "-CHF 999.9B†a".
    const values = [kpiValueWidth('$60.8B', false), kpiValueWidth('$1.7B', true), kpiValueWidth('$1.7B', true, 'a'), kpiValueWidth('CHF 22.8B', true), kpiValueWidth('-CHF 999.9B', true, 'a')]
    const problems: string[] = []
    let checked = 0
    for (const root of [16, 32]) for (const viewport of [360, 800, 1280]) for (const tiles of [3, 4]) for (const value of values) {
      const track = minimum(viewport, root, value, tiles)
      const chrome = (viewport >= 640 ? 2 * rem(theme.spacing['4']) : 2 * rem(theme.spacing['3'])) * root + 2
      const card = value * root + chrome
      for (let strip = 200; strip <= 1500; strip += 0.5) {
        const n = fallback && strip < 17 * root ? 1 : Math.max(1, Math.floor((strip + gap * root) / (track(strip) + gap * root)))
        const share = (count: number) => (strip - (count - 1) * gap * root) / count
        const fail = (why: string) => problems.length < 20 && problems.push(`${viewport}px viewport, ${root}px root, ${tiles} tiles, a ${card}px card, a ${strip}px strip: ${n} columns (${why})`)
        if (n > 1 && card > share(n) + 1e-9) fail('a card narrower than its value')
        if (tiles === 4 && n === 3) fail('three of four')
        if (strip < 17 * root) { if (n !== 1) fail('below 17em'); continue }
        if (viewport < 1024 && n > 2) fail('more than two below lg')
        if (viewport < 1024 && card <= share(2) - 0.5 && n !== 2) fail('one where two fit below lg')
        if (viewport >= 1024 && card <= share(tiles) - 0.5 && n !== tiles) fail('fewer than one per tile where they fit')
        if (viewport >= 1024 && card > share(tiles) && n !== (card <= share(2) ? 2 : 1)) fail('neither two nor one where the tiles do not fit')
        checked++
      }
    }
    expect(problems).toEqual([])
    expect(checked).toBeGreaterThan(50_000)
    expect(grid, 'no fixed column count fights the widest value').not.toMatch(/(^| )(lg:)?grid-cols-[2-4]\b/)
  })

  it('lays the landing sample\'s three tiles three across, the count no wrapper caps any more', () => {
    const { container } = render(<KpiStrip dataset={SAMPLE_ANALYSIS_DATASET} />)
    expect(container.querySelectorAll('[data-analysis-kpi]')).toHaveLength(3)
    expect(container.querySelector('dl')!.style.getPropertyValue('--kpi-cols')).toBe('3')
  })

  it('counts a glyph the figure face lacks at a full em, so the budget never undercuts what paints', () => {
    // Geist Mono has no ₩ or ₫ (E203): they print in another face, so each counts a full em.
    expect(kpiValueWidth('₩22.8B', true)).toBeCloseTo(kpiValueWidth('$22.8B', true) + (1 - 0.6) * 1.5, 9)
    for (const glyph of KPI_FACE_GLYPHS) expect(kpiValueWidth(`${glyph}22.8B`, false), glyph).toBeCloseTo(6 * 0.9, 9)
  })

  it('sets the widest value, as the cards render it, and the tile count on the strip', () => {
    const { container, rerender } = render(<KpiStrip dataset={dataset('CHF', [59_893_000_000, 22_768_000_000, 14_831_000_000])} />)
    const strip = () => container.querySelector('dl')!
    // The strip rounds its value up at the fourth decimal of a rem, so it never undercuts a value.
    const budget = () => parseFloat(strip().style.getPropertyValue('--kpi-value'))
    const covers = (widths: number[]) => { const widest = Math.max(...widths); expect(budget()).toBeGreaterThanOrEqual(widest); expect(budget() - widest).toBeLessThan(1e-4) }
    // Each card's final value (the count-up is mid-tween here) with the marks it draws: its dagger and its note letter.
    const drawn = (data: AnalysisDataset) => [...container.querySelectorAll('[data-analysis-kpi]')].map((card) => {
      const series = data.series.find((item) => item.label === card.querySelector('dt')!.textContent)!
      const button = card.querySelector('[data-kpi-value] button')!
      const final = fmtCurrency(series.points.at(-1)!.value, { compact: true, currency: series.unit })
      return kpiValueWidth(final, button.textContent!.includes('†'), button.querySelector('[data-note-letter]')?.getAttribute('data-note-letter'))
    })
    const chf = dataset('CHF', [59_893_000_000, 22_768_000_000, 14_831_000_000])
    expect(drawn(chf)).toHaveLength(3)
    expect(strip().style.getPropertyValue('--kpi-value')).toMatch(/^\d+(\.\d{1,4})?rem$/)
    covers(drawn(chf))
    // Free cash flow's dagger makes it wider than the nine-glyph "CHF 59.9B" and "CHF 22.8B".
    expect(Math.max(...drawn(chf))).toBeGreaterThanOrEqual(kpiValueWidth('CHF\u00a014.8B', true))
    expect(strip().style.getPropertyValue('--kpi-cols')).toBe('3')
    const usd = dataset('USD', [281_700_000_000, 101_800_000_000])
    rerender(<KpiStrip dataset={usd} />)
    expect(drawn(usd)).toHaveLength(2)
    covers(drawn(usd))
    expect(strip().style.getPropertyValue('--kpi-cols')).toBe('2')
  })

  it('counts up in the unit its value ends in, so no frame is wider than that value', () => {
    expect(STRIP).toMatch(/compactCurrencyCountUp\(point\.value as number, series\.unit\.split\('\/'\)\[0\]\)/)
    const finals = [22_768_000_000, 968_000_000, -1_746_000_000, 384_500_000, 999_960_000_000, 5_000_000, 12_300, 0.5, 999.9]
    for (const currency of ['USD', 'CAD', 'CHF', 'JPY', 'EUR', 'HKD']) for (const final of finals) {
      const frame = compactCurrencyCountUp(final, currency)
      const last = fmtCurrency(final, { compact: true, currency })
      expect(frame(final), `${currency} ${final}`).toBe(last)
      for (let step = 0; step <= 200; step++) {
        const shown = frame(final * step / 200)
        expect([...shown].length, `${currency} ${final}: "${shown}" before "${last}"`).toBeLessThanOrEqual([...last].length)
      }
    }
    // An update from a larger value (useCountUp tweens previous → next) prints those frames compactly, never "$1,700.0M".
    const update = compactCurrencyCountUp(450_000_000, 'USD')
    for (let step = 0; step <= 200; step++) {
      const value = 1_700_000_000 + (450_000_000 - 1_700_000_000) * step / 200
      expect([...update(value)].length, update(value)).toBeLessThanOrEqual([...fmtCurrency(value, { compact: true })].length)
    }
    // Compact notation on every frame would show "CHF 999.9M" on the way to "CHF 22.8B", one glyph wider.
    expect(compactCurrencyCountUp(22_768_000_000, 'CHF')(999_900_000)).toBe('CHF\u00a01.0B')
  })
})
