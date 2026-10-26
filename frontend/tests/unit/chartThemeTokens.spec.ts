import { createRequire } from 'node:module'
import { describe, expect, it } from 'vitest'

import { chartTheme } from '@/components/ui/Chart'

/**
 * chartTheme (components/ui/Chart.tsx) hands SVG and canvas the hexes CSS variables cannot reach, so each of its inks is
 * a copy of a tailwind.config.js token, and a copy drifts unless something holds it (CLAUDE.md rule 12). When the dark
 * secondary ink rose to gray-300, the tooltip's series names were a bare literal no test read, and the change had to be
 * found by hand. Every mirrored ink is held here to the token it copies, per theme; the bar-cursor wash and the
 * tooltip's border and shadow have no token and are not read.
 */
type Tree = Record<string, Record<string, string | Record<string, string>>>
const colors = (createRequire(import.meta.url)('../../tailwind.config.js') as { theme: { extend: { colors: Tree } } }).theme.extend.colors
const chart = colors.chart as Record<string, Record<string, string>>
const text = colors.text as Record<string, Record<string, string>>
const tone = (name: 'gain' | 'loss' | 'flat') => colors[name] as Record<string, string>

describe('chartTheme mirrors the tokens it copies', () => {
  it.each([['light', false], ['dark', true]] as const)('%s', (theme, dark) => {
    const t = chartTheme(dark)
    expect({ grid: t.grid, axis: t.axis, label: t.label, crosshair: t.crosshair, ref: t.ref, tipBg: t.tipBg }).toEqual({
      grid: chart.grid[theme], axis: chart.axis[theme], label: chart.label[theme], crosshair: chart.crosshair[theme], ref: chart.ref[theme], tipBg: chart.tip[theme],
    })
    expect({ nameInk: t.nameInk, valueInk: t.valueInk }).toEqual({ nameInk: text.secondary[theme], valueInk: text.primary[theme] })
    expect({ gain: t.gain, loss: t.loss, flat: t.flat }).toEqual({ gain: tone('gain')[theme], loss: tone('loss')[theme], flat: tone('flat')[theme] })
    // Direction text: the 700 level on the light ground, the -dark pair on the dark one.
    expect({ gainText: t.gainText, lossText: t.lossText }).toEqual(dark
      ? { gainText: tone('gain').dark, lossText: tone('loss').dark }
      : { gainText: tone('gain').text, lossText: tone('loss').text })
  })
})
