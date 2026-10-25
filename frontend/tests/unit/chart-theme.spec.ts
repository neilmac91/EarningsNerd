import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CHART_TOKENS, type ChartTokens } from '@/features/analysis/lib/charts/theme'

/**
 * features/analysis/lib/charts/theme.ts is a colour mirror the raw-colour lint rule exempts, like components/ui/Chart.tsx.
 * Its dark tokens are new (spec §3.8, owner decision 3) and live in Tailwind as the spec renderer's own pairs
 * (`chart.s1…s6`, `chart.tick`, `chart.gridline`, `chart.review`; E194), so no production chart takes them before F66.
 * designTokenParity holds every hex the file holds to a token; this spec holds each field to the spec's table and to its
 * own named token in both themes, which a hex found anywhere in the config cannot. tests/unit/chart-apca.spec.ts holds
 * each to its contrast floor.
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

describe('every token is a named Tailwind token, both themes (E194)', () => {
  const pair = (token: { light: string; dark: string }) => [token.light, token.dark]

  it('the surface is the card’s panel, the zero rule the chart reference line, the grid its own gridline', () => {
    expect(both((tokens) => tokens.surface)).toEqual(pair(colors.panel))
    expect(both((tokens) => tokens.zero)).toEqual(pair(colors.chart.ref))
    expect(both((tokens) => tokens.grid)).toEqual(pair(colors.chart.gridline))
  })

  it('the series are chart.s1…s6, whose light halves are today’s chart-1…6', () => {
    for (let i = 0; i < 6; i++) {
      expect(both((tokens) => tokens.series[i]), `s${i + 1}`).toEqual(pair(colors.chart[`s${i + 1}`]))
      expect(colors.chart[`s${i + 1}`].light, `s${i + 1} light`).toBe(colors.chart[i + 1])
    }
  })

  it('the inks: tick and the card’s subtitle in chart.tick, values in the text inks, review letters in chart.review', () => {
    expect(both((tokens) => tokens.tick)).toEqual(pair(colors.chart.tick))
    expect(both((tokens) => tokens.note)).toEqual(pair(colors.chart.tick))
    expect(colors.chart.tick.light, 'the light tick ink is the tertiary text ink').toBe(colors.text.tertiary.light)
    expect(both((tokens) => tokens.value)).toEqual([colors.text.secondary.light, colors.text.primary.dark])
    expect(both((tokens) => tokens.review)).toEqual(pair(colors.chart.review))
    expect(colors.chart.review.light, 'the light review ink is the warning ink').toBe(colors.warning.light)
    // The card's legend: names in the secondary ink on light and chart.tick on dark (§3.8), values in the primary ink.
    expect(both((tokens) => tokens.name)).toEqual([colors.text.secondary.light, colors.chart.tick.dark])
    expect(both((tokens) => tokens.figure)).toEqual(pair(colors.text.primary))
  })

  it('the column wash is chart-1’s teal at 8% and 16%, as Chart.tsx’s bar cursor', () => {
    const teal = [1, 3, 5].map((at) => parseInt(colors.chart[1].slice(at, at + 2), 16)).join(',')
    expect(both((tokens) => tokens.cursor)).toEqual([`rgba(${teal},.08)`, `rgba(${teal},.16)`])
  })
})
