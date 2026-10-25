import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CHART_TOKENS, type ChartTokens } from '@/features/analysis/lib/charts/theme'

/**
 * features/analysis/lib/charts/theme.ts is a colour mirror the raw-colour lint rule exempts, like components/ui/Chart.tsx,
 * but its dark tokens are new (spec §3.8, owner decision 3) and reach Tailwind only with the step-6 switch (E194), so
 * designTokenParity cannot hold it yet. This spec does: every token equals the spec's table, both themes, and every
 * value the design system already has equals its Tailwind token.
 */
const SPEC = readFileSync('../docs/design/analysis-trend-charts-spec-2026-10.md', 'utf8')
const section = SPEC.slice(SPEC.indexOf('### 3.8 Theme tokens'), SPEC.indexOf('### 3.9'))
const config = require('../../tailwind.config.js')
const colors = config.theme.extend.colors

/** The table's light and dark values for a token row (`grid`, `s1` …), read as written. */
function row(name: string): [string, string] {
  const line = section.split('\n').find((text) => text.startsWith(`| \`${name}\``))
  if (!line) throw new Error(`no §3.8 row for ${name}`)
  const cells = line.split('|').map((cell) => cell.trim())
  const value = (cell: string) => (cell.match(/#[0-9A-Fa-f]{6}|rgba\([^)]*\)/) ?? [''])[0]
  return [value(cells[3]), value(cells[5])]
}

/** The "HTML text in the chart card" table's light and dark hexes for a row. */
function htmlRow(label: string): [string, string] {
  const line = section.split('\n').find((text) => text.startsWith(`| ${label} |`))
  if (!line) throw new Error(`no §3.8 HTML row for ${label}`)
  const hexes = line.match(/#[0-9A-Fa-f]{6}/g) ?? []
  return [hexes[0], hexes[1]]
}

const both = (pick: (tokens: ChartTokens) => string) => [pick(CHART_TOKENS.light), pick(CHART_TOKENS.dark)]
const COLOUR = /#[0-9A-Fa-f]{6}\b|rgba\([^)]*\)/g

describe('the trend charts’ tokens are the spec’s (§3.8)', () => {
  it.each(['surface', 'grid', 'zero', 'tick', 'value', 'review', 'cursor'] as const)('%s', (name) => {
    expect(both((tokens) => tokens[name])).toEqual(row(name))
  })

  it('chart-1…6 in order', () => {
    for (let i = 0; i < 6; i++) expect(both((tokens) => tokens.series[i]), `s${i + 1}`).toEqual(row(`s${i + 1}`))
  })

  it('every colour theme.ts holds is in the spec’s tables, whatever field or export holds it', () => {
    // The lint rule exempts the file, so no other check reads a colour added outside the fields above.
    const source = readFileSync('features/analysis/lib/charts/theme.ts', 'utf8').replace(/\/\/.*$/gm, '')
    const tables = new Set((section.match(COLOUR) ?? []).map((value) => value.toUpperCase()))
    const held = source.match(COLOUR) ?? []
    expect(held.length).toBe(2 * (7 + 6 + 3))
    expect(held.filter((value) => !tables.has(value.toUpperCase()))).toEqual([])
  })

  it('the card’s HTML text', () => {
    expect(both((tokens) => tokens.note)).toEqual(htmlRow('Subtitle and footnotes'))
    expect(both((tokens) => tokens.name)).toEqual(htmlRow('Legend names'))
    expect(both((tokens) => tokens.figure)).toEqual(htmlRow('Legend values'))
  })
})

describe('the values the design system already has are its tokens', () => {
  it('the surface is the card’s panel colour, and the zero rule the chart reference line', () => {
    expect(both((tokens) => tokens.surface)).toEqual([colors.panel.light, colors.panel.dark])
    expect(both((tokens) => tokens.zero)).toEqual([colors.chart.ref.light, colors.chart.ref.dark])
  })

  it('light series are chart-1…6, and the light inks the text tokens', () => {
    expect(CHART_TOKENS.light.series).toEqual([1, 2, 3, 4, 5, 6].map((n) => colors.chart[n]))
    expect([CHART_TOKENS.light.tick, CHART_TOKENS.light.value, CHART_TOKENS.light.figure])
      .toEqual([colors.text.tertiary.light, colors.text.secondary.light, colors.text.primary.light])
    expect([CHART_TOKENS.light.review, CHART_TOKENS.dark.figure]).toEqual([colors.warning.light, colors.text.primary.dark])
    // The card's HTML inks: subtitle and footnotes in tertiary, legend names in secondary.
    expect([CHART_TOKENS.light.note, CHART_TOKENS.light.name]).toEqual([colors.text.tertiary.light, colors.text.secondary.light])
  })
})
