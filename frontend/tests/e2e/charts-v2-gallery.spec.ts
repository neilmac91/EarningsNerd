import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Locator, type Page } from '@playwright/test'
import type { AnalysisDataset } from '../../features/analysis/api/analysis-api'
import { layoutChart } from '../../features/analysis/lib/charts/layout'
import { buildChartModel, CHART_IDS, type ChartModel, type ChartView } from '../../features/analysis/lib/charts/model'
import { CHART_TOKENS } from '../../features/analysis/lib/charts/theme'
import { resolveDataNotes } from '../../features/analysis/lib/dataNotes'
import { selectHeadlineFigures } from '../../features/analysis/lib/reportPresentation'
import { plannedByRole, questioned } from '../unit/chartPlan'
import { datasetFixture, geometryDataset, openAnalysis, openDataset, type AnalysisTheme } from './fixtures/analysisLayoutApi'
import { expectInks, expectSound, hexOf, measurePlots, type Paint } from './fixtures/chartChecks'

/**
 * The trend charts' gallery (step 6 of the migration plan, E194): the production renderer on twelve
 * datasets chosen for their cases, in both themes, at 1280 and 390 px, card and expanded. Each chart is held to the plan
 * the engine makes at the width the page measured, its SVG's size and every text by role, and to the spec's DOM checks
 * (docs/design/analysis-trend-charts-spec-2026-10.md §6; fixtures/chartChecks.ts): D1, D2, D3, D5, D6 on the computed
 * colours (the card's text too), D8, D10, D14 and M6, A7's sticky gutter; D9 (each card keeps one height from the moment
 * it is drawn, a grid row's cards and plots line up, the page never scrolls sideways); and M19 (the legend wraps by whole
 * items). The unit fixtures (tests/unit/fixtures/chart-datasets.json) keep their values; the page receives each under its
 * own ticker (analysisLayoutApi's datasetFixture). D4, D7, D11, D12 and D13 run elsewhere: the first four on every fixture
 * in jsdom (trend-charts-v2.spec.tsx), D13 in charts-v2.spec.ts. CI's standard e2e-tests job runs the whole gallery.
 */
const THEMES: AnalysisTheme[] = ['light', 'dark']
const FIXTURE = JSON.parse(readFileSync(path.join(__dirname, '../unit/fixtures/chart-datasets.json'), 'utf8')) as {
  datasets: Record<string, { dataset: AnalysisDataset }>
}
const unit = (name: string) => structuredClone(FIXTURE.datasets[name].dataset)

/** The non-percent amounts in Swiss francs: a code-prefixed currency, the widest labels ("CHF 4.9B"). */
function inSwissFrancs(dataset: AnalysisDataset) {
  for (const series of dataset.series) if (!series.percent) {
    series.unit = 'CHF'
    for (const point of series.points) point.unit = 'CHF'
  }
  return dataset
}

/** name → the dataset as the page receives it, and why it is in the gallery. */
const GALLERY: Array<[string, () => AnalysisDataset | 'captured', string]> = [
  ['META quarterly', () => 'captured', 'the captured production dataset, its notes'],
  ['REGN annual in CHF', () => inSwissFrancs(unit('REGN_annual')), 'a code-prefixed currency: values that may not fit'],
  ['REGN annual, nine review notes', () => questioned(unit('REGNPN_annual')), 'the notes band in three charts, its letters in the note ink'],
  ['LCID annual', () => unit('LCID_annual'), 'off-scale margins, clipped growth, a 340× top-line range'],
  ['RIVN annual', () => unit('RIVN_annual'), 'a zero top line: n/m and gaps on the zero rule, growth of +2,915%'],
  ['PLUG annual', () => unit('PLUG_annual'), 'debt 119× below cash, near-zero equity labels'],
  ['PLUG quarterly', () => unit('PLUG_quarterly'), 'the widest phone plot'],
  ['BYND annual', () => unit('BYND_annual'), 'negative equity'],
  ['JPM annual', () => unit('JPM_annual'), 'a bank: net interest income, margins that do not apply, debt not in the dataset'],
  ['PGR quarterly', () => unit('PGR_quarterly'), 'an insurer: premiums earned, missing periods'],
  ['O annual', () => unit('O_annual'), 'a REIT: two charts that do not apply'],
  ['XOM quarterly', () => unit('XOM_quarterly'), 'a one-period window'],
]

/** D9's record: every height each card has had since it was inserted, by chart. */
function recordCardHeights() {
  const heights: Record<string, number[]> = {}
  ;(window as unknown as { __trendCardHeights: typeof heights }).__trendCardHeights = heights
  const observer = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const chart = (entry.target as HTMLElement).dataset.trendChart!
      ;(heights[chart] ??= []).push(Math.round(entry.target.getBoundingClientRect().height * 10) / 10)
    }
  })
  const seen = new WeakSet<Element>()
  new MutationObserver(() => {
    for (const card of document.querySelectorAll('section[data-trend-chart]')) if (!seen.has(card)) {
      seen.add(card)
      observer.observe(card)
    }
  }).observe(document, { childList: true, subtree: true })
}

/** One drawn chart in `view`: the plan at its measured width, the DOM checks, and D6 on the card's computed colours. */
async function expectChart(card: Locator, model: ChartModel, view: ChartView, theme: AnalysisTheme) {
  const tokens = CHART_TOKENS[theme]
  const [report] = await measurePlots(card)
  const name = `${model.title} (${view})`
  const plan = layoutChart(model, report.measured, view)
  expect([report.svgWidth, report.height], `${name}: the plan's size at the card's width`).toEqual([plan.width, plan.height])
  expect(report.texts, `${name}: every text is the plan's, by role and ink`).toEqual(plannedByRole(model, plan, tokens))
  await expect(card.locator('[data-chart-text="fit"]'), `${name}: says its values don't fit exactly when they don't`).toHaveCount(plan.valuesDontFit ? 1 : 0)
  expectSound({ ...report, name })
  await expectCardInks(card, model, name, theme, report.paints)
}

/** D6 on a card: its HTML text (subtitle, legend, footnotes, "Values don't fit", a chart's not-applicable sentence) and
 *  any plot paints, each against the card's computed background, itself the chart surface. */
async function expectCardInks(card: Locator, model: ChartModel, name: string, theme: AnalysisTheme, paints: Paint[]) {
  // The colour check reads what carries data-chart-text, so each piece the model prints must carry it.
  const count = (role: string) => card.locator(`[data-chart-text="${role}"]`).count()
  expect(await count('subtitle'), `${name}: the subtitle is read`).toBe(1)
  expect(await count('name'), `${name}: every legend name is read`).toBe(model.legend.length)
  expect(await count('figure'), `${name}: every legend value is read`).toBe(model.legend.filter((item) => item.value).length)
  expect(await count('footnote'), `${name}: every footnote is read`).toBe(model.footnotes.length)
  expect(await count('unavailable'), `${name}: a chart that does not apply says so`).toBe(model.unavailable ? 1 : 0)
  const ground = await card.evaluate((section) => getComputedStyle(section).backgroundColor)
  expect(hexOf(ground), `${name}: the card is the chart surface`).toBe(CHART_TOKENS[theme].surface)
  const html = await card.locator('[data-chart-text]').evaluateAll((nodes) => nodes.map((node) => ({
    what: `${node.getAttribute('data-chart-text')} "${node.textContent}"`,
    floor: node.getAttribute('data-chart-text') === 'figure' ? 'values' as const : 'text' as const,
    colour: getComputedStyle(node).color,
  })))
  expectInks(name, [...paints, ...html] as Paint[], ground)
}

test.describe.configure({ mode: 'parallel' })
// Full font hinting, headless Chrome's default (CI's) and some desktops': D1 and D8 run in the case that can break them.
test.use({ launchOptions: { args: ['--font-render-hinting=full'] } })

for (const [name, source, why] of GALLERY) for (const theme of THEMES) for (const width of [1280, 390]) {
  test.describe(`trend charts v2 gallery / ${name} / ${theme} / ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test(`every chart draws its plan and passes the DOM checks, card and expanded (${why})`, async ({ page, baseURL }) => {
      test.setTimeout(150_000)
      await page.addInitScript(recordCardHeights)
      const picked = source()
      let dataset: AnalysisDataset
      if (picked === 'captured') {
        dataset = geometryDataset('captured')
        await openAnalysis(page, baseURL!, 'captured', theme)
      } else {
        dataset = datasetFixture(picked).fixture.dataset
        await openDataset(page, baseURL!, picked, theme, selectHeadlineFigures(dataset).length)
      }
      const notes = resolveDataNotes(dataset)
      const models = CHART_IDS.map((chart) => buildChartModel(chart, dataset, notes))
      const cards = page.locator('section[data-trend-chart]')
      await expect(cards).toHaveCount(CHART_IDS.length)
      await expect(page.locator('[data-analysis-chart] > svg'), 'every chart that applies is drawn').toHaveCount(models.filter((model) => !model.unavailable).length)

      for (const [index, model] of models.entries()) {
        const card = cards.nth(index)
        await expect(card).toHaveAttribute('data-trend-chart', CHART_IDS[index])
        if (model.unavailable) {
          await expect(card.locator('[data-chart-text="unavailable"]')).toHaveText(model.unavailable)
          await expectCardInks(card, model, `${model.title} (does not apply)`, theme, [])
        } else await expectChart(card, model, 'card', theme)
      }

      // D9: each card has kept one height since it was drawn, a grid row's cards are one height and its plots start at
      // one height (the cards' subgrid), and the page does not scroll sideways.
      const heights = await page.evaluate(() => (window as unknown as { __trendCardHeights: Record<string, number[]> }).__trendCardHeights)
      for (const chart of CHART_IDS) expect(new Set(heights[chart]), `${chart}: one height since the card was drawn`).toEqual(new Set([heights[chart]?.[0]]))
      const boxes = await cards.evaluateAll((sections) => sections.map((section) => {
        const box = section.getBoundingClientRect()
        const plot = section.querySelector('[data-analysis-chart-scroll], [data-chart-text="unavailable"]')!.getBoundingClientRect()
        return { row: Math.round(box.top), height: box.height, plot: plot.top }
      }))
      const rows = new Map<number, typeof boxes>()
      for (const box of boxes) rows.set(box.row, [...(rows.get(box.row) ?? []), box])
      expect(rows.size, 'two columns on a desktop, one on a phone').toBe(width >= 768 ? 2 : 4)
      for (const row of rows.values()) {
        expect(new Set(row.map((box) => box.height)).size, 'a grid row’s cards are one height').toBe(1)
        expect(Math.max(...row.map((box) => box.plot)) - Math.min(...row.map((box) => box.plot)), 'a grid row’s plots start at one height').toBeLessThanOrEqual(0.5)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways').toBe(true)
      await expectLegendsWrapWhole(page)

      for (const [index, model] of models.entries()) {
        if (model.unavailable) continue
        const card = cards.nth(index)
        await card.getByRole('button', { name: 'Expand chart', exact: true }).click()
        await expect.poll(async () => Number(await card.locator('[data-analysis-chart] > svg').getAttribute('height'))).toBeGreaterThan(320)
        await expectChart(card, model, 'expanded', theme)
        await expectLegendsWrapWhole(page)
        await card.getByRole('button', { name: 'Collapse chart', exact: true }).click()
        await expect(card.locator('[data-analysis-chart] > svg')).toHaveAttribute('height', '320')
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways after expanding').toBe(true)
    })
  })
}

/**
 * M19: the legend wraps by whole items. An item breaks inside only when it is wider than its legend's whole line, the one
 * case no wrapping can avoid without the page scrolling sideways (200% text, CLAUDE.md rule 11); and no item reaches past
 * its legend's edge.
 */
async function expectLegendsWrapWhole(page: Page) {
  const items = await page.locator('section[data-trend-chart] ul[aria-label="Series"] > li').evaluateAll((list) => list.map((item) => {
    const legend = item.parentElement!
    const probe = item.cloneNode(true) as HTMLElement
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;width:max-content'
    legend.appendChild(probe)
    const natural = probe.getBoundingClientRect().width
    probe.remove()
    const box = item.getBoundingClientRect()
    return {
      text: item.textContent,
      lines: Math.round(box.height / parseFloat(getComputedStyle(item).lineHeight)),
      natural,
      room: legend.clientWidth,
      overrun: box.right - legend.getBoundingClientRect().right,
    }
  }))
  expect(items.length, 'the gallery’s legends').toBeGreaterThan(0)
  expect(items.filter((item) => item.lines > 1 && item.natural <= item.room).map((item) => `"${item.text}" breaks over ${item.lines} lines, ${item.natural.toFixed(1)} px wide in a ${item.room} px legend`), 'M19: an item that fits a line keeps to one').toEqual([])
  expect(items.filter((item) => item.overrun > 0.5).map((item) => `"${item.text}" runs ${item.overrun.toFixed(1)} px past its legend`)).toEqual([])
}
