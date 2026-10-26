/**
 * The trend charts' tokens, chart scope (docs/design/analysis-trend-charts-spec-2026-10.md §3.8). Every value is a
 * literal hex or rgba string, so no var(--…) reaches an SVG attribute and serialising the SVG for the PNG export
 * cannot lose a colour. Only the spec renderer reads these. They mirror Tailwind's `chart.s1…s6`,
 * `chart.tick`, `chart.value`, `chart.gridline` and `chart.review` pairs and the text and surface tokens (step 6,
 * E194); the Recharts charts elsewhere (Fundamentals, Peers) keep components/ui/Chart.tsx's chartTheme, so the new dark
 * tokens reach no other chart until E195's token fold. designTokenParity holds every hex here to a token and keeps the pairs' own hexes out of
 * every other mirror, tests/unit/chart-theme.spec.ts holds each field to the spec's table and its own token and keeps
 * the pairs out of every class, and tests/unit/chart-apca.spec.ts holds each to its contrast floor. Pure and SSR-safe.
 */
export interface ChartTokens {
  /** Plot background, marker rings, break marks, export fill: the card's panel colour. */
  surface: string
  /** Non-zero gridlines, 1 px. */
  grid: string
  /** The zero tick's gridline, every panel, 1 px. */
  zero: string
  /** Tick and x labels, captions, "—", "n/m", "Notes", strip names, the off-scale edge rule,
   *  the absent series' swatch. */
  tick: string
  /** Bar labels, near-zero labels, off-scale values, strip cells. */
  value: string
  /** Review-kind band letters until E194: since D-061 no chart text takes it, and E195's token fold retires it. */
  review: string
  /** chart-1…6, taken in order over the series present (A8). */
  series: readonly [string, string, string, string, string, string]
  /** The hover and focus column wash (TrendChartPlot, E193). */
  cursor: string
  /** The card's HTML text (subtitle and footnotes), the notes band's letters and the tooltip's. */
  note: string
  name: string
  figure: string
}

const LIGHT: ChartTokens = {
  surface: '#FBFAF6',
  grid: '#DCD9D0', // Lc 16.8
  zero: '#6B7280', // Lc 70.5
  tick: '#636A77', // Lc 74.1
  value: '#374151', // Lc 90.9
  review: '#92400E', // Lc 80.9
  series: ['#3E8E84', '#B8812F', '#5B7CC0', '#CF7159', '#6E7E9C', '#8B7BC0'], // Lc 63.0, 58.0, 65.2, 58.2, 65.1, 61.4
  cursor: 'rgba(62,142,132,.08)',
  note: '#636A77', // Lc 74.1
  name: '#374151', // Lc 90.9
  figure: '#1A1A17', // Lc 101.3
}

const DARK: ChartTokens = {
  surface: '#1F2937',
  grid: '#525C6B', // Lc −15.0
  zero: '#9CA3AF', // Lc −48.6
  tick: '#B8BEC7', // Lc −63.6 (the DS's #9CA3AF is −48.6, under 60 for 11 px text)
  value: '#EAECEF', // Lc −91.8 (−88.5 under the wash): the figure ink, as the legend values' (D-063)
  review: '#FBBF24', // Lc −70.2 (the DS's #F59E0B is −56.9)
  series: ['#62B2A6', '#D3A55C', '#8CA6E3', '#E8927C', '#97A6C2', '#AFA2DE'], // Lc −49.7, −54.2, −50.9, −51.9, −50.1, −52.8
  cursor: 'rgba(62,142,132,.16)',
  note: '#B8BEC7', // Lc −63.6
  name: '#D1D5DB', // Lc −77.3: the DS text.secondary.dark since #1606, as light's names take text.secondary (E194)
  figure: '#EAECEF', // Lc −91.8: the DS text.primary.dark since #1606 (was #D7DADC, −80.3)
}

export const CHART_TOKENS = { light: LIGHT, dark: DARK } as const

export const chartTokens = (dark: boolean): ChartTokens => (dark ? DARK : LIGHT)
