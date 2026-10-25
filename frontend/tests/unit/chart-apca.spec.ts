/* =============================================================================
   chart-apca.spec.ts — the trend charts' inks clear their contrast floors (E194)
   -----------------------------------------------------------------------------
   docs/design/analysis-trend-charts-spec-2026-10.md §3.8 writes the spec renderer's colours with their APCA Lc on the
   card, and the floors each kind of paint must clear: data marks and the zero rule 45, must-read text 60, printed
   values 75, gridlines 10–25 (visible, quieter than the zero rule). features/analysis/lib/charts/theme.ts holds the
   tokens; this spec measures each one in both themes against the card's surface and against the column wash that a
   hover, a tap or the values stop paints under a period (TrendChartPlot), with the APCA-W3 formula in ./apca, itself
   held to apca-w3's published results. Every Lc the spec's tables print is recomputed, so the tables cannot drift
   from the hexes they describe. D6 in a browser (the computed colours on the page) is the gallery's (E194).
============================================================================= */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CHART_TOKENS, type ChartTokens } from '@/features/analysis/lib/charts/theme'
import { apcaLc, over } from './apca'

const SPEC = readFileSync('../docs/design/analysis-trend-charts-spec-2026-10.md', 'utf8')
const section = SPEC.slice(SPEC.indexOf('### 3.8 Theme tokens'), SPEC.indexOf('### 3.9'))
const rows = (start: string) => section.split('\n').filter((line) => line.startsWith(start)).map((line) => line.split('|').map((cell) => cell.trim()))
const HEX = /#[0-9A-Fa-f]{6}/
const lc = (cell: string) => Number(cell.split('/')[0].trim().replace('−', '-'))
const round = (value: number) => Math.round(value * 10) / 10

describe('the APCA formula is apca-w3’s (0.0.98G-4g)', () => {
  it.each([
    ['#888888', '#FFFFFF', 63.056],
    ['#FFFFFF', '#888888', -68.541],
    ['#000000', '#FFFFFF', 106.041],
    ['#FFFFFF', '#000000', -107.885],
    ['#FFFFFF', '#FFFFFF', 0],
  ])('%s on %s → %d', (text, ground, expected) => {
    expect(apcaLc(text, ground)).toBeCloseTo(expected, 3)
  })

  it('composites a wash over its ground as the browser does, to 8-bit', () => {
    expect(over('rgba(62,142,132,.08)', '#FBFAF6')).toBe('#ECF1ED')
    expect(over('rgba(62,142,132,.16)', '#1F2937')).toBe('#243943')
  })
})

describe('every Lc the spec’s §3.8 tables print is the formula’s on the card', () => {
  const token = rows('| `').filter((cells) => HEX.test(cells[3]) && /\d/.test(cells[4]))
  it('reads the token table', () => expect(token.map((cells) => cells[1])).toEqual(
    ['`grid`', '`zero`', '`tick`', '`value`', '`review`', '`s1` teal', '`s2` honey', '`s3` cornflower', '`s4` coral', '`s5` slate-blue', '`s6` periwinkle'],
  ))
  it.each(token.map((cells) => [cells[1], cells]))('%s', (_, cells) => {
    const [light, dark] = [cells[3], cells[5]].map((cell) => HEX.exec(cell)![0])
    expect(round(apcaLc(light, CHART_TOKENS.light.surface))).toBe(lc(cells[4]))
    expect(round(apcaLc(dark, CHART_TOKENS.dark.surface))).toBe(lc(cells[6]))
  })

  const html = rows('| ').filter((cells) => cells.length === 7 && HEX.test(cells[2]))
  it('reads the card’s HTML text table', () => expect(html.map((cells) => cells[1])).toEqual(['Subtitle and footnotes', 'Legend names', 'Legend values']))
  it.each(html.map((cells) => [cells[1], cells]))('%s', (_, cells) => {
    expect(round(apcaLc(HEX.exec(cells[2])![0], CHART_TOKENS.light.surface))).toBe(lc(cells[3]))
    expect(round(apcaLc(HEX.exec(cells[4])![0], CHART_TOKENS.dark.surface))).toBe(lc(cells[5]))
  })

  // The Source column's figures for what each token replaces, on the dark card: a hex it names ("DS `#F59E0B` is
  // −56.9"), or today's dark series, which is its light hex ("today's dark −32.0").
  const sources = token.flatMap((cells) => [...cells[7].matchAll(/(?:`(#[0-9A-Fa-f]{6})` is|today's dark) (−?\d+\.\d)/g)]
    .map((match) => [`${cells[1]}: ${match[0]}`, match[1] ?? HEX.exec(cells[3])![0], match[2]] as const))
  it('reads the Source column’s figures', () => expect(sources).toHaveLength(8))
  it.each(sources)('%s', (_, hex, printed) => {
    expect(round(apcaLc(hex, CHART_TOKENS.dark.surface))).toBe(lc(printed))
  })
})

/** The spec's floors, read from its thresholds table. */
const floor = (start: string) => {
  const cells = section.split('\n').find((line) => line.startsWith(`| ${start}`))?.split('|').map((cell) => cell.trim())
  if (!cells) throw new Error(`no §3.8 threshold row for ${start}`)
  const [low, high] = cells[2].match(/\d+/g)!.map(Number)
  return { low, high: start === 'Gridlines' ? high : Infinity }
}
const MARKS = floor('Data marks')
const TEXT = floor('Must-read')
const VALUES = floor('Printed values')
const GRID = floor('Gridlines')

/** Each token's floor; the wash and the surface are grounds, not paints. */
const FLOORS: Record<Exclude<keyof ChartTokens, 'surface' | 'cursor'>, { low: number; high: number }> = {
  grid: GRID,
  zero: MARKS,
  series: MARKS,
  tick: TEXT,
  review: TEXT,
  note: TEXT,
  name: TEXT,
  value: VALUES,
  figure: VALUES,
}

describe('every ink clears its floor in both themes, on the card and on the column wash', () => {
  it('the floors are the spec’s, and every token has one', () => {
    expect([MARKS, TEXT, VALUES, GRID]).toEqual([{ low: 45, high: Infinity }, { low: 60, high: Infinity }, { low: 75, high: Infinity }, { low: 10, high: 25 }])
    expect(Object.keys(FLOORS).sort()).toEqual(Object.keys(CHART_TOKENS.light).filter((key) => key !== 'surface' && key !== 'cursor').sort())
  })

  const cases = (['light', 'dark'] as const).flatMap((theme) => {
    const tokens = CHART_TOKENS[theme]
    return [['card', tokens.surface], ['wash', over(tokens.cursor, tokens.surface)]].flatMap(([ground, colour]) =>
      Object.entries(FLOORS).flatMap(([key, bounds]) => {
        const paints = key === 'series' ? tokens.series.map((paint, i) => [`s${i + 1}`, paint]) : [[key, tokens[key as keyof ChartTokens] as string]]
        return paints.map(([name, paint]) => [`${theme} ${name} on the ${ground}`, theme, paint, colour, bounds] as const)
      }))
  })
  it.each(cases)('%s', (_, theme, paint, ground, { low, high }) => {
    const value = apcaLc(paint, ground)
    // Dark ink on the light card reads positive, light ink on the dark card negative.
    expect(Math.sign(value), 'polarity').toBe(theme === 'light' ? 1 : -1)
    expect(Math.abs(value)).toBeGreaterThanOrEqual(low)
    expect(Math.abs(value)).toBeLessThanOrEqual(high)
  })
})
