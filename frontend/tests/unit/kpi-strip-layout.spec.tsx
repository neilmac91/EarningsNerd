import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import KpiStrip from '@/features/analysis/components/KpiStrip'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { KPI_FIGURE_ADVANCE, KPI_MARK_ADVANCE, KPI_MARK_GAP, kpiValueGlyphs, kpiValueWidth, kpiWidestCss } from '@/features/analysis/lib/kpiStripLayout'
import { NOTE_MARK } from '@/features/analysis/components/DataNoteMark'
import { compactCurrencyCountUp, fmtCurrency } from '@/lib/format'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'

type Theme = { fontSize: Record<string, [string, unknown]>; spacing: Record<string, string>; borderWidth: Record<string, string> }
const require = createRequire(import.meta.url)
const theme = (require('tailwindcss/resolveConfig') as (config: unknown) => { theme: Theme })(require('../../tailwind.config.js')).theme
const here = path.dirname(fileURLToPath(import.meta.url))
const source = (file: string) => readFileSync(path.resolve(here, '../..', file), 'utf8')
const STRIP = source('features/analysis/components/KpiStrip.tsx')
const rem = (value: string) => parseFloat(value)
/** A --kpi-value expression's length in rem at given advances (the face's 0.6em unless given the measured ones). */
const atAdvances = (css: string, figure = KPI_FIGURE_ADVANCE, mark = KPI_MARK_ADVANCE) => new Function(`return ${css
  .replace(/var\(--kpi-figure\)/g, `(${figure})`).replace(/var\(--kpi-mark\)/g, `(${mark})`)
  .replace(/(\d*\.?\d+)rem/g, '($1)').replace(/calc\(/g, '(').replace(/max\(/g, 'Math.max(')}`)() as number
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
    expect(marks.match(/\$\{large \? '[^']+' : '[^']+'\} ml-0\.5 /g), 'the letter keeps 2px (no figure carries a dagger, D-061)').toHaveLength(1)
    expect(KPI_FIGURE_ADVANCE).toBeCloseTo(ADVANCE * rem(theme.fontSize['2xl'][0]), 9)
    expect(KPI_MARK_ADVANCE).toBeCloseTo(ADVANCE * rem(theme.fontSize['data-xs'][0]), 9)
    expect(KPI_MARK_GAP).toBe(rem(theme.spacing['0.5']))
    // E197's two cases, 138.2px each at a 16px root: CHF at 320px and CA$ at 360px.
    expect(kpiValueWidth('CHF 22.8B')).toBeCloseTo(8.1, 9)
    // A marked letter adds its glyph and its 2px: "CA$968.0M" with a note's "a" is 138.2px at a 16px root.
    expect(kpiValueWidth('CA$968.0M', 'a')).toBeCloseTo(8.6375, 9)
    expect(kpiValueWidth('$1.7B', 'ab')).toBeCloseTo(5 * 0.9 + 0.125 + 2 * 0.4125, 9)
    expect(kpiValueWidth('-36.1%')).toBeCloseTo(6 * 0.9, 9)
  })

  it('measures the advances in probes set like the value and its marks, and starts from the face\'s 0.6em', () => {
    // The figure probe takes every class of KpiTile's dd but its layout and its inks, so whatever sets the value's
    // face, size, weight, numerals or tracking (now or later) sets the probe's too.
    const classes = (pattern: RegExp, skip: string[]) => (STRIP.match(pattern)?.[1] ?? '').split(' ').filter((name) => name && !skip.includes(name)).sort()
    const value = classes(/data-kpi-value className="([^"]*)"/, ['min-w-0', 'text-figure-light', 'dark:text-figure-dark'])
    expect(value).toContain('text-2xl')
    expect(classes(/const FIGURE_PROBE = '([^']*)'/, ['block', 'w-max', 'whitespace-pre'])).toEqual(value)
    // The mark probe is a letter in DataNoteMark's own classes (NOTE_MARK) at the value's weight, hidden from every reader
    // and never a note: it carries no data-note-letter.
    const { container } = render(<KpiStrip dataset={dataset('USD', [5_000_000_000, 1_000_000_000])} />)
    const probes = container.querySelector('div[aria-hidden="true"].invisible')!
    expect(probes.querySelectorAll('span')[0].textContent).toBe('0000000000')
    const letter = [...probes.querySelectorAll('span')].find((span) => span.textContent === 'a' && !span.children.length)!
    expect(letter.className).toBe(NOTE_MARK)
    expect(letter.hasAttribute('data-note-letter')).toBe(false)
    expect(letter.parentElement!.className).toContain('font-semibold')
    // Until it measures, the strip takes the face's 0.6em, the advances the width model starts from.
    const rems = (value: number) => `${Math.round(value * 1e4) / 1e4}rem`
    expect(STRIP).toContain(`[--kpi-figure:${rems(KPI_FIGURE_ADVANCE)}] [--kpi-mark:${rems(KPI_MARK_ADVANCE)}]`)
  })

  it('writes the widest value as a CSS max() that equals the widest width at any advances, whole pixels included', () => {
    const values: Array<[string, string?]> = [['$60.8B'], ['$1.7B', 'a'], ['26.1%', 'a'], ['CHF\u00a022.8B'], ['CA$968.0M', 'a'], ['₩22.8B'], ['-$1.7B'], ['$1.7B']]
    const css = kpiWidestCss(values.map(([text, letter]) => kpiValueGlyphs(text, letter)))
    const term = String.raw`calc\(\d+ \* var\(--kpi-figure\) \+ \d+ \* var\(--kpi-mark\) \+ [\d.]+rem\)`
    expect(css).toMatch(new RegExp(`^max\\(${term}(, ${term})*\\)$`))
    // "$1.7B" and "-$1.7B" can never be the widest ("$60.8B" matches or passes them in every term).
    expect(css.match(/calc\(/g)!.length).toBeLessThan(values.length)
    // 0.6em at 16px and 32px roots, and the whole pixels a snapping browser paints there (14px and 7px, 29px and 13px).
    const ADVANCES = [[KPI_FIGURE_ADVANCE, KPI_MARK_ADVANCE], [14 / 16, 7 / 16], [29 / 32, 13 / 32], [15 / 16, 6 / 16]]
    for (const [figure, mark] of ADVANCES) {
      expect(atAdvances(css, figure, mark), `${figure}rem, ${mark}rem`).toBeCloseTo(Math.max(...values.map(([text, letter]) => kpiValueWidth(text, letter, figure, mark))), 4)
    }
    // Which value is widest turns on the advances: more figure glyphs win where the figure's advance is large, more marks
    // and rest where it is small. Each value below is the widest at one of the advances, so every term must stay.
    const turns = [{ figure: 7, mark: 0, rest: 0 }, { figure: 5, mark: 0, rest: 1.84 }, { figure: 5, mark: 4, rest: 0.125 }]
    const widestAt = ADVANCES.map(([figure, mark]) => turns.reduce((best, value, index) => value.figure * figure + value.mark * mark + value.rest > turns[best].figure * figure + turns[best].mark * mark + turns[best].rest + 1e-9 ? index : best, 0))
    expect(new Set(widestAt).size, `the widest at each advance: ${widestAt}`).toBe(turns.length)
    const both = kpiWidestCss(turns)
    expect(both.match(/calc\(/g)!.length).toBe(turns.length)
    for (const [figure, mark] of ADVANCES) {
      expect(atAdvances(both, figure, mark), `${figure}rem, ${mark}rem`).toBeCloseTo(Math.max(...turns.map((value) => value.figure * figure + value.mark * mark + value.rest)), 9)
    }
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
      // In compiled order: Tailwind emits the base rules, then sm:, then lg:, whatever their order in the class.
      const rank = (name: string) => (name.startsWith('lg:') ? 2 : name.startsWith('sm:') ? 1 : 0)
      for (const name of [...classes].sort((a, b) => rank(a) - rank(b))) {
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
    // The values of E197 and of the fixtures, in rem on one line: "$60.8B", "$1.7B", "$1.7Ba", "CHF 22.8B", "CA$968.0Ma", "-CHF 999.9Ba".
    const values = [kpiValueWidth('$60.8B'), kpiValueWidth('$1.7B'), kpiValueWidth('$1.7B', 'a'), kpiValueWidth('CHF 22.8B'), kpiValueWidth('CA$968.0M', 'a'), kpiValueWidth('-CHF 999.9B', 'a')]
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

  it('gives the landing demo\'s strip its three tiles as its column count, with no wrapper overriding its columns', () => {
    const { container } = render(<AnalysisDemo />)
    const strip = container.querySelector('[data-analysis-kpi]')!.closest('dl')!
    expect(strip.querySelectorAll('[data-analysis-kpi]')).toHaveLength(3)
    expect(strip.style.getPropertyValue('--kpi-cols')).toBe('3')
    // A wrapper used to cap the landing's columns (`lg:[&>div>dl]:grid-cols-3`); the strip's own rule now decides them.
    const wrappers: string[] = []
    for (let node = strip.parentElement; node && node !== container; node = node.parentElement) wrappers.push(...node.classList)
    expect(wrappers.filter((name) => /\[&[^\]]*dl\]|\bgrid-cols-/.test(name))).toEqual([])
  })

  it('counts a glyph the figure face lacks at 1.25em, wider than any face found to draw one', () => {
    // Geist Mono has no ₩ or ₫ (E203) and no narrow no-break space ("F CFA"); DejaVu Sans Bold draws ₩ at 1.103em.
    expect(kpiValueWidth('₩22.8B')).toBeCloseTo(kpiValueWidth('$22.8B') + (1.25 - 0.6) * 1.5, 9)
    for (const glyph of ['\u202f', '₩', '₫']) expect(kpiValueWidth(glyph), glyph).toBeCloseTo(1.25 * 1.5, 9)
    // Its latin-ext file has the peso, rupee and shekel signs at 0.6em.
    for (const value of ['₱22.8B', '₹22.8B', '₪22.8B', '€22.8B', 'CHF\u00a01.0B']) expect(kpiValueWidth(value), value).toBeCloseTo([...value].length * 0.9, 9)
  })

  it('sets the widest value, as the cards render it, and the tile count on the strip', () => {
    const { container, rerender } = render(<KpiStrip dataset={dataset('CHF', [59_893_000_000, 22_768_000_000, 14_831_000_000])} />)
    const strip = () => container.querySelector('dl')!
    // The budget at the face's 0.6em, the advances jsdom leaves in place (it paints nothing to measure).
    const budget = () => atAdvances(strip().style.getPropertyValue('--kpi-value'))
    const covers = (widths: number[]) => { const widest = Math.max(...widths); expect(budget()).toBeGreaterThanOrEqual(widest); expect(budget() - widest).toBeLessThan(1e-4) }
    // Each card's final value (the count-up is mid-tween here) with the mark it draws: a note letter, where one shows.
    const drawn = (data: AnalysisDataset) => [...container.querySelectorAll('[data-analysis-kpi]')].map((card) => {
      const series = data.series.find((item) => item.label === card.querySelector('dt')!.textContent)!
      const button = card.querySelector('[data-kpi-value] button')!
      const final = fmtCurrency(series.points.at(-1)!.value, { compact: true, currency: series.unit })
      return kpiValueWidth(final, button.querySelector('[data-note-letter]')?.getAttribute('data-note-letter'))
    })
    const chf = dataset('CHF', [59_893_000_000, 22_768_000_000, 14_831_000_000])
    expect(drawn(chf)).toHaveLength(3)
    expect(strip().style.getPropertyValue('--kpi-value')).toMatch(/^max\(calc\(/)
    covers(drawn(chf))
    // The nine-glyph values set the width; no note questions them, so no letter shows, and a calculated one (free cash
    // flow) carries no dagger (D-061).
    expect(Math.max(...drawn(chf))).toBeCloseTo(kpiValueWidth('CHF\u00a059.9B'), 9)
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
    // Compact notation on every frame would show "CHF 999.9M" on the way to "CHF 22.8B", one glyph wider.
    expect(compactCurrencyCountUp(22_768_000_000, 'CHF')(999_900_000)).toBe('CHF\u00a01.0B')
  })

  it('remounts a card whose value changes, so its count starts from zero, not from a wider old value', () => {
    // A tween from $1.0B to $80.0M would pass "$999.9M", wider than the card sized for "$80.0M".
    const { container, rerender } = render(<KpiStrip dataset={dataset('USD', [5_000_000_000, 1_000_000_000])} />)
    const card = (label: string) => [...container.querySelectorAll('[data-analysis-kpi]')].find((item) => item.querySelector('dt')!.textContent === label)!
    const [revenue, income] = [card('revenue'), card('net_income')]
    rerender(<KpiStrip dataset={dataset('USD', [5_000_000_000, 80_000_000])} />)
    expect(card('revenue'), 'an unchanged value keeps its card').toBe(revenue)
    expect(card('net_income'), 'a changed value takes a new card').not.toBe(income)
  })
})
