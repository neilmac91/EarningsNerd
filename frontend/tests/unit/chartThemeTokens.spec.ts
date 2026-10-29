import { createRequire } from 'node:module'
import { describe, expect, it, vi } from 'vitest'

import { chartTheme, gridProps, seriesColor, xAxisProps } from '@/components/ui/Chart'
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
 * line, composited over the gridline when it is translucent. In the hairline (chart.axis, Lc 8.8 on the light card) the
 * light baseline was the quietest rule in the chart once the gridlines took chart.grid's 16.8 (E195's token fold).
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
