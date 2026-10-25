import { expect, test, type Locator, type Page } from '@playwright/test'
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
 * - M6 on the page: a plot fills its card, or is wider and scrolls inside it as a keyboard stop, opened at its newest
 *   period behind A7's sticky gutter, which repeats the y axis at the viewport's edge and passes D1, D2 and D8 itself;
 * - D9: a grid row's plots start at one height, whatever its legends wrap to (the cards' subgrid, E193);
 * - D13 and DESIGN_SYSTEM.md §10 (E193): one values stop a chart, the period walk with its tooltip and column wash in
 *   view, the pointer and touch, Escape, and the tooltip's contrast and reflow under 200% text.
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

interface TextReport {
  outside: string[]
  collisions: string[]
  advances: string[]
}

interface PlotReport extends TextReport {
  name: string
  height: number
  animations: number
  svgWidth: number
  viewportWidth: number
  scrolls: boolean
  /** How far the viewport sits from its newest period (0 there). */
  fromNewest: number
  keyboardStop: boolean
  /** A7's sticky gutter, while the plot's own has scrolled away: its text, and its left edge against the viewport's. */
  gutter: (TextReport & { offset: number; ticks: string[]; plotTicks: string[] }) | null
}

/** One report per chart plot, measured in the page. */
async function measurePlots(page: Page): Promise<PlotReport[]> {
  return page.locator('[data-analysis-chart]').evaluateAll((plots, advance) => plots.map((plot) => {
    // D1, D2 and D8 on one SVG's text.
    const textOf = (svg: SVGSVGElement) => {
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
      return { width, height, outside, collisions, advances }
    }
    const svg = plot.querySelector('svg')!
    const { width, height, ...text } = textOf(svg)
    const viewport = plot.closest<HTMLElement>('[data-analysis-chart-scroll]')!
    const overlay = viewport.querySelector<SVGSVGElement>('[data-chart-gutter] svg')
    const ticks = (root: SVGSVGElement) => [...root.querySelectorAll('text[text-anchor="end"]')].map((tick) => `${tick.textContent}@${tick.getAttribute('y')}`)
    return {
      name: plot.getAttribute('data-analysis-chart')!,
      height,
      ...text,
      // The plot's own; the card's controls keep the design system's colour transitions (DESIGN_SYSTEM.md §11).
      animations: plot.getAnimations({ subtree: true }).length,
      svgWidth: width,
      viewportWidth: viewport.clientWidth,
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
      fromNewest: viewport.scrollWidth - viewport.clientWidth - viewport.scrollLeft,
      keyboardStop: viewport.tabIndex === 0 && viewport.getAttribute('role') === 'region',
      gutter: overlay && {
        ...textOf(overlay),
        offset: overlay.getBoundingClientRect().left - viewport.getBoundingClientRect().left,
        ticks: ticks(overlay),
        plotTicks: ticks(svg),
      },
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
  // A plot that scrolls opens at its newest period, the one the legend and the metrics table quote, behind A7's sticky
  // gutter: at the viewport's left edge, its text sound, its tick labels the plot's own.
  if (!report.scrolls) {
    expect(report.gutter, `${name}: no gutter overlay on a plot that fits`).toBeNull()
    return
  }
  expect(report.fromNewest, `${name}: opens at its newest period`).toBeLessThanOrEqual(1)
  expect(report.gutter, `${name}: the sticky gutter repeats the y axis`).not.toBeNull()
  const gutter = report.gutter!
  expect(Math.abs(gutter.offset), `${name}: the gutter sticks to the viewport's left edge`).toBeLessThanOrEqual(0.5)
  expect(gutter.outside, `${name}: D1 in the gutter`).toEqual([])
  expect(gutter.collisions, `${name}: D2 in the gutter`).toEqual([])
  expect(gutter.advances, `${name}: D8 in the gutter`).toEqual([])
  expect(gutter.ticks, `${name}: the gutter's tick labels are the plot's`).toEqual(gutter.plotTicks)
}

test.describe.configure({ mode: 'parallel' })
// Full font hinting, headless Chrome's default (CI's) and some desktops': at 1x it snaps every advance to a whole
// pixel unless the SVG asks for geometric precision, so D1 and D8 run in the case that can break them. The local
// browser's wrapper passes --font-render-hinting=none; the last flag wins.
test.use({ launchOptions: { args: ['--font-render-hinting=full'] } })

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

test.describe('trend charts v2 when the renderer’s chunk fails to load', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('the grid says the charts could not be drawn, and the rest of the analysis stands', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    // A stale client after a deploy: every script that carries the renderer fails to arrive.
    const aborted: string[] = []
    await page.route('**/_next/static/**/*.js', async (route) => {
      const response = await route.fetch()
      const body = await response.text()
      if (body.includes('data-axis-domain')) {
        aborted.push(route.request().url())
        await route.abort('failed')
      } else {
        await route.fulfill({ response, body })
      }
    })
    await openAnalysis(page, baseURL!, 'captured', 'light')
    // The chunk loader retries once before it gives up, so the fallback takes a few seconds.
    await expect(page.getByText('These charts could not be drawn.')).toBeVisible({ timeout: 15_000 })
    expect(aborted.length, 'the renderer’s chunk was requested and refused').toBeGreaterThan(0)
    await expect(page.locator('[data-analysis-chart]')).toHaveCount(0)
    await expect(page.getByRole('heading', { level: 1, name: 'Multi-Period Analysis' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Metrics by period' })).toBeVisible()
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
      // D9: a grid row's plots start at one height, whatever its legends wrap to (the cards' subgrid).
      const plotTops = await cards.evaluateAll((sections) => sections.map((section) => [
        Math.round(section.getBoundingClientRect().top),
        section.querySelector('[data-analysis-chart-scroll]')!.getBoundingClientRect().top,
      ]))
      const tops = new Map<number, number[]>()
      for (const [row, top] of plotTops) tops.set(row, [...(tops.get(row) ?? []), top])
      for (const values of tops.values()) expect(Math.max(...values) - Math.min(...values), 'a grid row’s plots start at one height').toBeLessThanOrEqual(0.5)
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

/** WCAG's relative-luminance contrast of two computed colours ("rgb(…)"; an alpha ink is mixed over the ground). */
function contrast(ink: string, ground: string): number {
  const parse = (value: string) => value.match(/[\d.]+/g)!.map(Number)
  const [gr, gg, gb] = parse(ground)
  const [r, g, b, a = 1] = parse(ink)
  const mixed = [r * a + gr * (1 - a), g * a + gg * (1 - a), b * a + gb * (1 - a)]
  const luminance = ([x, y, z]: number[]) => {
    const [lx, ly, lz] = [x, y, z].map((channel) => {
      const c = channel / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * lx + 0.7152 * ly + 0.0722 * lz
  }
  const [hi, lo] = [luminance(mixed), luminance([gr, gg, gb])].sort((p, q) => q - p)
  return (hi + 0.05) / (lo + 0.05)
}

/** How far a box runs past the viewport's sides (0 or less when it lies inside). */
async function overrun(viewport: Locator, target: Locator) {
  const [frame, box] = await Promise.all([viewport.boundingBox(), target.boundingBox()])
  if (!frame || !box) return Number.POSITIVE_INFINITY
  return Math.max(frame.x - box.x, box.x + box.width - frame.x - frame.width)
}

for (const theme of THEMES) for (const width of [1280, 390]) {
  test.describe(`trend charts v2 / reading a chart / ${theme} / ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test('one values stop a chart: Tab enters, reads the newest period, leaves and returns, under the brand ring', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(90_000)
      await openAnalysis(page, baseURL!, 'captured', theme)
      for (const viewport of await page.locator('[data-analysis-chart-scroll]').all()) {
        const card = viewport.locator('xpath=ancestor::section[1]')
        const overflow = await viewport.evaluate((element) => element.scrollWidth > element.clientWidth + 1)
        if (overflow) {
          await expect(viewport).toHaveAttribute('role', 'region')
          await expect(viewport).toHaveAttribute('tabindex', '0')
          await expect(viewport).toHaveAccessibleName(/chart\. Scroll horizontally to view all periods\./)
        } else {
          await expect(viewport).not.toHaveAttribute('role')
          await expect(viewport).not.toHaveAttribute('tabindex')
        }
        const stop = card.getByRole('slider', { name: /chart values$/ })
        await expect(stop).toHaveCount(1)
        // The values stop is a layer over the viewport: its box is the viewport's, and nothing in the plot takes a Tab.
        expect(await viewport.locator('[tabindex]').count(), 'no Tab stop inside the plot').toBe(0)
        const [frame, layer] = await Promise.all([viewport.boundingBox(), stop.boundingBox()])
        expect(Math.max(Math.abs(frame!.x - layer!.x), Math.abs(frame!.width - layer!.width), Math.abs(frame!.y - layer!.y))).toBeLessThanOrEqual(0.5)
        const newest = await stop.getAttribute('aria-valuemax')
        await card.getByRole('button', { name: /^(Expand|Collapse) chart$/ }).focus()
        await page.keyboard.press('Tab')
        if (overflow) {
          await expect(viewport).toBeFocused()
          expect(await viewport.evaluate((element) => getComputedStyle(element).boxShadow), 'the region’s own ring').not.toBe('none')
          await page.keyboard.press('Tab')
        }
        await expect(stop).toBeFocused()
        await expect(stop).toHaveAttribute('aria-valuenow', newest!)
        expect(await stop.evaluate((element) => getComputedStyle(element).boxShadow), 'the stop’s brand ring, around the viewport').not.toBe('none')
        const tooltip = card.locator('[data-chart-tooltip]')
        await expect(tooltip).toBeVisible()
        await expect(tooltip).toHaveAttribute('aria-hidden', 'true')
        expect(await overrun(viewport, tooltip), 'the tooltip lies inside the viewport').toBeLessThanOrEqual(0.5)
        expect(await overrun(viewport, card.locator('[data-chart-wash]')), 'the period’s column lies inside the viewport').toBeLessThanOrEqual(0.5)
        await page.keyboard.press('Tab')
        expect(await page.evaluate(() => document.activeElement?.closest('[data-analysis-chart-scroll]') ?? null)).toBeNull()
        await expect(tooltip).toHaveCount(0)
        await page.keyboard.press('Shift+Tab')
        await expect(stop).toBeFocused()
        if (overflow) {
          await page.keyboard.press('Shift+Tab')
          await expect(viewport).toBeFocused()
        }
      }
    })

    test('the period walk keeps its column and tooltip in view; a pointer reads without scrolling; Escape in two steps', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(120_000)
      await openAnalysis(page, baseURL!, 'captured', theme)
      const card = page.locator('section:has([data-analysis-chart])').first()
      const viewport = card.locator('[data-analysis-chart-scroll]')
      const stop = card.getByRole('slider')
      const tooltip = card.locator('[data-chart-tooltip]')
      const wash = card.locator('[data-chart-wash]')
      const gutter = card.locator('[data-chart-gutter] svg')
      const last = Number(await stop.getAttribute('aria-valuemax'))
      const settle = () => viewport.evaluate(async (element) => {
        let previous = element.scrollLeft
        for (let stable = 0, frame = 0; frame < 90 && stable < 5; frame++) {
          await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
          stable = Math.abs(element.scrollLeft - previous) < 0.1 ? stable + 1 : 0
          previous = element.scrollLeft
        }
      })
      /** The column lies in the plot's visible part: inside the viewport and clear of the sticky gutter. */
      const columnInView = async () => {
        await settle()
        const [frame, column, axis] = await Promise.all([viewport.boundingBox(), wash.boundingBox(), gutter.count().then((n) => (n ? gutter.boundingBox() : null))])
        const covered = axis ? Number(await card.locator('[data-chart-gutter] rect').first().getAttribute('width')) : 0
        return Math.max(frame!.x + covered - column!.x, column!.x + column!.width - frame!.x - frame!.width)
      }
      await card.getByRole('button', { name: 'Expand chart', exact: true }).focus()
      await page.keyboard.press('Tab')
      if (await viewport.getAttribute('tabindex')) await page.keyboard.press('Tab')
      await expect(stop).toBeFocused()
      for (let index = last; index >= 0; index--) {
        if (index < last) await page.keyboard.press('ArrowLeft')
        await expect(stop).toHaveAttribute('aria-valuenow', String(index))
        const valueText = (await stop.getAttribute('aria-valuetext'))!
        const header = (await tooltip.locator('p').textContent())!
        // The value text speaks what the tooltip shows: its period first, the end date spelled out.
        expect(valueText.startsWith(header.split(' · ')[0])).toBe(true)
        expect(valueText).not.toMatch(/[·—−]|\d[KMBT]\b/)
        expect(await columnInView(), `period ${index}: its column lies in the visible plot`).toBeLessThanOrEqual(0.5)
        expect(await overrun(viewport, tooltip), `period ${index}: its tooltip lies inside the viewport`).toBeLessThanOrEqual(0.5)
      }
      await page.keyboard.press('ArrowLeft')
      await expect(card.getByRole('status')).toHaveText('Oldest period.')
      await page.keyboard.press('End')
      await expect(stop).toHaveAttribute('aria-valuenow', String(last))
      await page.keyboard.press('ArrowRight')
      await expect(card.getByRole('status')).toHaveText('Newest period.')
      await page.keyboard.press('Home')
      await expect(stop).toHaveAttribute('aria-valuenow', '0')
      // Leaving and returning after the viewport moved: the kept period is brought back into view.
      await page.keyboard.press('Tab')
      await viewport.evaluate((element) => { element.scrollLeft = element.scrollWidth })
      await page.keyboard.press('Shift+Tab')
      await expect(stop).toBeFocused()
      await expect(stop).toHaveAttribute('aria-valuenow', '0')
      expect(await columnInView(), 'the kept period, revealed on return').toBeLessThanOrEqual(0.5)

      // A pointer reads the period under it without moving focus or the scroll; resting on the tooltip keeps it. The
      // pointer comes in under the keyboard's tooltip, which a pointer resting on would keep.
      const header = () => tooltip.locator('p').textContent()
      const target = await viewport.evaluate((element) => {
        const frame = element.getBoundingClientRect()
        return { x: frame.right - 30, y: frame.top + 260, left: element.scrollLeft }
      })
      await page.mouse.move(target.x, target.y)
      const hovered = await header()
      await expect(stop).toBeFocused()
      await expect(stop).toHaveAttribute('aria-valuenow', '0')
      expect(hovered!.split(' · ')[0], 'the pointer’s period, not the keyboard’s').not.toBe((await stop.getAttribute('aria-valuetext'))!.split(',')[0])
      expect(Math.abs(await viewport.evaluate((element) => element.scrollLeft) - target.left), 'pointing never scrolls').toBeLessThanOrEqual(0.5)
      // Up the column to the tooltip's middle, then across onto it: the tooltip sits flush beside its column.
      const tip = (await tooltip.boundingBox())!
      await page.mouse.move(target.x, tip.y + tip.height / 2, { steps: 4 })
      expect(await header()).toBe(hovered)
      await page.mouse.move(tip.x + tip.width / 2, tip.y + tip.height / 2, { steps: 8 })
      expect(await header(), 'the tooltip is hoverable (WCAG 1.4.13)').toBe(hovered)
      // The next key resumes the keyboard's own period.
      await page.keyboard.press('ArrowRight')
      await expect(stop).toHaveAttribute('aria-valuenow', '1')
      await expect(tooltip.locator('p')).not.toHaveText(hovered!)
      // Escape dismisses the pointer's tooltip; in an expanded card it then collapses it and returns focus.
      await page.mouse.move(target.x, target.y + 10)
      await expect(tooltip).toBeVisible()
      await expect(tooltip.locator('p')).toHaveText(hovered!)
      await card.getByRole('button', { name: 'Expand chart', exact: true }).click()
      await expect(card.getByRole('button', { name: 'Collapse chart', exact: true })).toBeFocused()
      await page.mouse.move(0, 0)
      await page.keyboard.press('Tab')
      if (await viewport.getAttribute('tabindex')) await page.keyboard.press('Tab')
      await expect(stop).toBeFocused()
      await expect(tooltip).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(tooltip).toHaveCount(0)
      await expect(card.getByRole('button', { name: 'Collapse chart', exact: true }), 'the first Escape closes the tooltip alone').toBeVisible()
      await page.keyboard.press('Escape')
      const toggle = card.getByRole('button', { name: 'Expand chart', exact: true })
      await expect(toggle).toBeFocused()
      await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    })

    test('the tooltip’s text clears 4.5:1 on its surface, and under 200% text it stays inside the chart', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(90_000)
      await openAnalysis(page, baseURL!, 'captured', theme, 2)
      for (const viewport of await page.locator('[data-analysis-chart-scroll]').all()) {
        const card = viewport.locator('xpath=ancestor::section[1]')
        await card.getByRole('slider').focus()
        await card.getByRole('slider').press('Home')
        const tooltip = card.locator('[data-chart-tooltip]')
        await expect(tooltip).toBeVisible()
        expect(await overrun(viewport, tooltip), 'inside the viewport’s sides').toBeLessThanOrEqual(0.5)
        const inks = await tooltip.evaluate((element) => {
          const ground = getComputedStyle(element).backgroundColor
          return [...element.querySelectorAll('p, span')].filter((node) => node.childElementCount === 0 && node.textContent?.trim())
            .map((node) => [node.textContent!, getComputedStyle(node).color, ground])
        })
        for (const [text, ink, ground] of inks) expect(contrast(ink, ground), `"${text}" on the tooltip`).toBeGreaterThanOrEqual(4.5)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways').toBe(true)
    })
  })
}

test.describe('trend charts v2 / 900px: a card that scrolls, with an expanded view that fits', () => {
  test.use({ viewport: { width: 900, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('collapsing opens the card at its newest period again (spec §3.10)', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    await openAnalysis(page, baseURL!, 'captured', 'light')
    const card = page.locator('section:has([data-analysis-chart])').first()
    const viewport = card.locator('[data-analysis-chart-scroll]')
    const fromNewest = () => viewport.evaluate((element) => element.scrollWidth - element.clientWidth - element.scrollLeft)
    const overflows = () => viewport.evaluate((element) => element.scrollWidth > element.clientWidth + 1)
    expect(await overflows(), 'the two-column card scrolls').toBe(true)
    expect(await fromNewest()).toBeLessThanOrEqual(1)
    await viewport.evaluate((element) => { element.scrollLeft = 0 })
    await card.getByRole('button', { name: 'Expand chart', exact: true }).click()
    await expect.poll(overflows, { message: 'the expanded plot fits' }).toBe(false)
    await card.getByRole('button', { name: 'Collapse chart', exact: true }).click()
    await expect.poll(overflows).toBe(true)
    await expect.poll(fromNewest, { message: 'collapsed, at the newest period' }).toBeLessThanOrEqual(1)
  })
})

test.describe('trend charts v2 / a tap pins a tooltip', () => {
  test.use({ viewport: { width: 390, height: 900 }, hasTouch: true, isMobile: true, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('a tap shows its period’s tooltip, a second tap or a tap outside closes it', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    await openAnalysis(page, baseURL!, 'captured', 'light')
    const card = page.locator('section:has([data-analysis-chart])').first()
    const viewport = card.locator('[data-analysis-chart-scroll]')
    await viewport.scrollIntoViewIfNeeded()
    const tooltip = card.locator('[data-chart-tooltip]')
    const frame = (await viewport.boundingBox())!
    await page.touchscreen.tap(frame.x + frame.width - 24, frame.y + 120)
    await expect(tooltip).toBeVisible()
    await expect(card.locator('[data-chart-wash]')).toBeVisible()
    await page.touchscreen.tap(frame.x + frame.width - 24, frame.y + 120)
    await expect(tooltip).toHaveCount(0)
    await page.touchscreen.tap(frame.x + frame.width - 24, frame.y + 120)
    await expect(tooltip).toBeVisible()
    const heading = (await card.getByRole('heading', { level: 2 }).boundingBox())!
    await page.touchscreen.tap(heading.x + 4, heading.y + 4)
    await expect(tooltip).toHaveCount(0)
  })
})
