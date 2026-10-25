import { expect, test, type Page } from '@playwright/test'
import type { AnalysisDataset } from '../../features/analysis/api/analysis-api'
import { openAnalysis, type AnalysisGeometryState, type AnalysisTheme } from './fixtures/analysisLayoutApi'

/**
 * The trend charts' spec renderer in a browser (NEXT_PUBLIC_CHARTS_V2, E192): the spec's DOM checks that need real text
 * metrics and layout (docs/design/analysis-trend-charts-spec-2026-10.md §6). tests/unit/trend-charts-v2.spec.tsx holds
 * the drawing to the engine's plan; this spec holds the plan to the page:
 * - D1: every text box lies inside the SVG;
 * - D2: no two text boxes intersect;
 * - D8: every string paints at Geist Mono's 0.6 em advance, so the planner's widths are the screen's;
 * - D9: a grid row's cards align, every card's plot is 320 px tall, and the page never scrolls sideways at 390 px;
 * - D10: no chart animates under reduced motion;
 * - M6 on the page: a plot fills its card, or is wider and scrolls inside it as a keyboard stop.
 * The expanded view is checked the same way. CI's e2e-charts-v2 job builds with the flag set; the main e2e job's build
 * has it unset, and these cases skip there, where one case holds that the flag-off route loads none of the renderer.
 */
const enabled = process.env.NEXT_PUBLIC_CHARTS_V2 === 'true'
const THEMES: AnalysisTheme[] = ['light', 'dark']
/** The planner's advance: Geist Mono is 0.6 em at 11 px (layout.ts ADVANCE). */
const ADVANCE = 0.6 * 11

const inSwissFrancs = (dataset: AnalysisDataset) => {
  for (const series of dataset.series) if (!series.percent) {
    series.unit = 'CHF'
    for (const point of series.points) point.unit = 'CHF'
  }
}
const CASES: Array<[string, number, AnalysisGeometryState, ((dataset: AnalysisDataset) => void) | undefined]> = [
  ['quarterly', 1280, 'captured', undefined],
  ['annual in CHF', 1280, 'annual', inSwissFrancs],
  ['quarterly', 390, 'captured', undefined],
  ['annual', 390, 'annual', undefined],
]

interface PlotReport {
  name: string
  height: number
  outside: string[]
  collisions: string[]
  advances: string[]
  animations: number
  svgWidth: number
  viewportWidth: number
  scrolls: boolean
  keyboardStop: boolean
}

/** One report per chart plot, measured in the page. */
async function measurePlots(page: Page): Promise<PlotReport[]> {
  return page.locator('[data-analysis-chart]').evaluateAll((plots, advance) => plots.map((plot) => {
    const svg = plot.querySelector('svg')!
    const [, , width, height] = svg.getAttribute('viewBox')!.split(' ').map(Number)
    const texts = [...svg.querySelectorAll('text')]
    const boxes = texts.map((text) => ({ text: text.textContent ?? '', box: text.getBBox() }))
    const where = ({ text, box }: { text: string; box: DOMRect }) => `"${text}" at ${box.x.toFixed(1)},${box.y.toFixed(1)} ${box.width.toFixed(1)}×${box.height.toFixed(1)}`
    const outside = boxes.filter(({ box }) => box.x < -0.01 || box.y < -0.01 || box.x + box.width > width + 0.01 || box.y + box.height > height + 0.01).map(where)
    const collisions: string[] = []
    boxes.forEach((a, i) => boxes.slice(i + 1).forEach((b) => {
      const x = Math.min(a.box.x + a.box.width, b.box.x + b.box.width) - Math.max(a.box.x, b.box.x)
      const y = Math.min(a.box.y + a.box.height, b.box.y + b.box.height) - Math.max(a.box.y, b.box.y)
      if (x > 0.01 && y > 0.01) collisions.push(`${where(a)} and ${where(b)}`)
    }))
    const advances = texts
      .flatMap((text) => (text.querySelector('tspan') ? [...text.querySelectorAll('tspan')] : [text]))
      .flatMap((node) => {
        const chars = [...(node.textContent ?? '')].length
        const painted = node.getComputedTextLength()
        return Math.abs(painted - advance * chars) > 0.5 ? [`"${node.textContent}" paints ${painted.toFixed(2)} px, not ${(advance * chars).toFixed(2)}`] : []
      })
    const viewport = plot.closest<HTMLElement>('[data-analysis-chart-scroll]')!
    return {
      name: plot.getAttribute('data-analysis-chart')!,
      height,
      outside,
      collisions,
      advances,
      // The plot's own; the card's controls keep the design system's colour transitions (DESIGN_SYSTEM.md §11).
      animations: plot.getAnimations({ subtree: true }).length,
      svgWidth: width,
      viewportWidth: viewport.clientWidth,
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
      keyboardStop: viewport.tabIndex === 0 && viewport.getAttribute('role') === 'region',
    }
  }), ADVANCE)
}

function expectSound(report: PlotReport) {
  const { name } = report
  expect(report.outside, `${name}: D1, text outside the SVG`).toEqual([])
  expect(report.collisions, `${name}: D2, text boxes that intersect`).toEqual([])
  expect(report.advances, `${name}: D8, text not at Geist Mono's advance`).toEqual([])
  expect(report.animations, `${name}: D10, animations under reduced motion`).toBe(0)
  // M6: the plot is laid out at its card's whole-pixel width, or at its wider minimum, and then scrolls in its card.
  expect(report.svgWidth, `${name}: the plot is at least its card's width`).toBeGreaterThanOrEqual(Math.floor(report.viewportWidth))
  expect(report.scrolls, `${name}: scrolls exactly when it is wider than its card`).toBe(report.svgWidth > report.viewportWidth + 1)
  expect(report.keyboardStop, `${name}: a scrolling plot is a keyboard stop, and only then`).toBe(report.scrolls)
}

test.describe.configure({ mode: 'parallel' })

test.describe('trend charts with the flag unset', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('today’s charts draw, and the route loads none of the spec renderer', async ({ page, baseURL }) => {
    test.skip(enabled, 'Run against a server built with the flag unset, as production is.')
    // The renderer is its own chunk (TrendCharts' next/dynamic import); its panel attribute names it.
    const scripts: Promise<[string, string]>[] = []
    page.on('response', (response) => {
      const url = response.url()
      if (url.includes('/_next/static/') && url.endsWith('.js')) scripts.push(response.text().then((body) => [url, body]))
    })
    await openAnalysis(page, baseURL!, 'captured', 'light')
    await expect(page.locator('[data-analysis-chart] svg.recharts-surface')).toHaveCount(4)
    await expect(page.locator('g[data-panel]')).toHaveCount(0)
    const loaded = await Promise.all(scripts)
    expect(loaded.length).toBeGreaterThan(0)
    expect(loaded.filter(([, body]) => body.includes('data-axis-domain')).map(([url]) => url), 'scripts carrying the spec renderer').toEqual([])
  })
})

for (const theme of THEMES) for (const [name, width, state, edit] of CASES) {
  test.describe(`trend charts v2 / ${theme} / ${width}px / ${name}`, () => {
    test.use({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test('every chart’s text sits inside its plot, apart, in Geist Mono, on aligned cards; expanded too', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(90_000)
      await openAnalysis(page, baseURL!, state, theme, 1, false, edit)
      const cards = page.locator('section:has([data-analysis-chart])')
      await expect(cards).toHaveCount(4)

      const reports = await measurePlots(page)
      for (const report of reports) {
        expect(report.height, `${report.name}: D9, a card's plot is 320 px tall`).toBe(320)
        expectSound(report)
      }
      // D9: the cards of a grid row are one height (two columns from md up, one on a phone).
      const boxes = await cards.evaluateAll((sections) => sections.map((section) => section.getBoundingClientRect()).map((box) => [Math.round(box.top), box.height]))
      const rows = new Map<number, number[]>()
      for (const [top, height] of boxes) rows.set(top, [...(rows.get(top) ?? []), height])
      expect(rows.size, 'two columns on a desktop, one on a phone').toBe(width >= 768 ? 2 : 4)
      for (const heights of rows.values()) expect(new Set(heights).size, 'a grid row’s cards are one height').toBe(1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways').toBe(true)
      if (edit) {
        // A code-prefixed currency's labels miss their tier on a desktop card, and the card says so (A4).
        await expect(cards.first().getByText('Values don’t fit at this width. The metrics table lists them.')).toBeVisible()
      }

      for (let index = 0; index < 4; index++) {
        const card = cards.nth(index)
        await card.getByRole('button', { name: 'Expand chart', exact: true }).click()
        await expect.poll(async () => Number(await card.locator('[data-analysis-chart] > svg').getAttribute('height'))).toBeGreaterThan(320)
        const expanded = (await measurePlots(page))[index]
        expect(expanded.height, `${expanded.name}: the expanded plot is 520 px, plus its strip`).toBeGreaterThanOrEqual(520)
        expectSound(expanded)
        await card.getByRole('button', { name: 'Collapse chart', exact: true }).click()
        await expect(card.locator('[data-analysis-chart] > svg')).toHaveAttribute('height', '320')
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways after expanding').toBe(true)
    })
  })
}
