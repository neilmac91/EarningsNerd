import { createRequire } from 'node:module'
import { render } from '@testing-library/react'
import { createElement } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { chartTheme, gridProps, seriesColor, xAxisProps } from '@/components/ui/Chart'
import RevenueBars from '@/features/marketing/components/RevenueBars'
import { apcaLc, over } from './apca'

/**
 * chartTheme (components/ui/Chart.tsx) hands SVG and canvas the hexes CSS variables cannot reach, so each of its inks is
 * a copy of a tailwind.config.js token, and a copy drifts unless something holds it (CLAUDE.md rule 12). When the dark
 * secondary ink rose to gray-300, the tooltip's series names were a bare literal no test read, and the change had to be
 * found by hand. Every mirrored ink is held here to the token it copies, per theme, the series included (chart-N and,
 * since E195's token fold, chart-N-dark); the bar-cursor wash and the tooltip's border and shadow have no token and are
 * not read.
 */
type Tree = Record<string, Record<string, string | Record<string, string>>>
const colors = (createRequire(import.meta.url)('../../tailwind.config.js') as { theme: { extend: { colors: Tree } } }).theme.extend.colors
const chart = colors.chart as Record<string, Record<string, string>>
const palette = colors.chart as Record<string, string>
const text = colors.text as Record<string, Record<string, string>>
const tone = (name: 'gain' | 'loss' | 'flat') => colors[name] as Record<string, string>

describe('chartTheme mirrors the tokens it copies', () => {
  it.each([['light', false], ['dark', true]] as const)('%s', (theme, dark) => {
    const t = chartTheme(dark)
    expect({ grid: t.grid, label: t.label, crosshair: t.crosshair, ref: t.ref, tipBg: t.tipBg }).toEqual({
      grid: chart.grid[theme], label: chart.label[theme], crosshair: chart.crosshair[theme], ref: chart.ref[theme], tipBg: chart.tip[theme],
    })
    expect({ nameInk: t.nameInk, valueInk: t.valueInk }).toEqual({ nameInk: text.secondary[theme], valueInk: text.primary[theme] })
    expect({ gain: t.gain, loss: t.loss, flat: t.flat }).toEqual({ gain: tone('gain')[theme], loss: tone('loss')[theme], flat: tone('flat')[theme] })
    // Direction text: the 700 level on the light ground, the -dark pair on the dark one.
    expect({ gainText: t.gainText, lossText: t.lossText }).toEqual(dark
      ? { gainText: tone('gain').dark, lossText: tone('loss').dark }
      : { gainText: tone('gain').text, lossText: tone('loss').text })
    // The series in order, each in the theme's half.
    expect([0, 1, 2, 3, 4, 5].map((i) => seriesColor(i, dark))).toEqual([1, 2, 3, 4, 5, 6].map((n) => palette[dark ? `${n}-dark` : n]))
  })
})

describe('seriesColor', () => {
  it.each([['light', false], ['dark', true]] as const)('wraps the %s sequence both ways', (_, dark) => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect([6, -1].map((i) => seriesColor(i, dark))).toEqual([seriesColor(0, dark), seriesColor(5, dark)])
    expect(warn).toHaveBeenCalledOnce() // index 6: more series than colours, the dev warning
    warn.mockRestore()
  })
})

/**
 * Recharts draws a gridline at each edge of the plot and the x-axis line over the bottom one, so the baseline is that
 * line, composited over the gridline when it is translucent. In the hairline #E5E7EB (Lc 8.8 on the light card) the
 * light baseline would be the quietest rule in the chart once the gridlines take chart.grid's 16.8 (E195's token fold).
 */
describe('the Recharts baseline is no quieter than its gridlines', () => {
  const card = colors.panel as Record<string, string>
  it.each([['light', false], ['dark', true]] as const)('%s', (theme, dark) => {
    const grid = gridProps(dark).stroke
    const contrast = (paint: string) => Math.abs(apcaLc(paint, card[theme]))
    const { axisLine } = xAxisProps(dark) as { axisLine: false | { stroke: string } }
    const baseline = !axisLine ? grid : axisLine.stroke.startsWith('rgba') ? over(axisLine.stroke, grid) : axisLine.stroke
    expect(contrast(baseline)).toBeGreaterThanOrEqual(contrast(grid))
  })
})

/**
 * The landing page's revenue bars draw their own rules, one per $100B and the baseline, in plain DOM. They are the
 * homepage's gridlines, so they take the product's gridline ink, chart.grid, in both themes (chief design on #1771): in
 * the retired hairline the dark rules sat under APCA's low clip on their card.
 */
describe("the landing page's revenue bars rule their ticks in chart.grid", () => {
  it('in both themes, every rule', () => {
    const points = [{ period: 'FY2024', value: 391e9 }, { period: 'FY2025', value: 416e9 }]
    const { container } = render(createElement(RevenueBars, { points }))
    const rules = [...container.querySelectorAll('span.border-t')]
    expect(rules).toHaveLength(7) // $0 to $600B, one per $100B: the axis tops out a full tick above $416B
    const inks = (rule: Element) => [...rule.classList].filter((name) => /^(dark:)?border-(?!t$)/.test(name))
    expect(rules.map(inks)).toEqual(rules.map(() => ['border-chart-grid-light', 'dark:border-chart-grid-dark']))
  })
})
