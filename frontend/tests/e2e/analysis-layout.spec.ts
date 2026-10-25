import { expect, test, type Page } from '@playwright/test'
import type { AnalysisDataset } from '../../features/analysis/api/analysis-api'
import { MIN_SLOT } from '../../features/analysis/lib/charts/layout'
import { KPI_FACE_GLYPHS, KPI_MISSING_GLYPHS } from '../../features/analysis/lib/kpiStripLayout'
import { EXPECTED_KPI_LETTERS, EXPECTED_KPI_VALUES, EXPECTED_NOTES, EXPECTED_TABLE_CELL_NOTES, EXPECTED_TABLE_COMPARISON_REVIEWS, EXPECTED_TABLE_REVIEWS, EXPECTED_TABLE_VALUE_DAGGERS, METRICS, PERIODS, UNAVAILABLE_CELLS, openAnalysis, type AnalysisState, type AnalysisTheme, type AnalysisGeometryState } from './fixtures/analysisLayoutApi'
import { CHARTS_V2, RECHARTS, drawnCharts, readAxes, readSlots, readTicksAndShapes, tickText } from './fixtures/trendChartDom'

/**
 * The one browser geometry gate for the analysis redesign (proposal Phase 1, item 10).
 * It exercises production React components and actual text ranges, not copies of CSS
 * or unit-test geometry. No backend, AI, stored credentials or new Playwright config.
 *
 * In particular, window.innerWidth is NOT an overflow oracle: mobile Chromium can
 * expand it to the overflowing document. Compare scrollWidth with document.clientWidth
 * AND the configured viewport. Off-screen sr-only text still counts in that check.
 * 200% text changes root font size; 200% zoom is explicitly viewport/DPR emulation.
 *
 * The trend charts are read through fixtures/trendChartDom.ts, from whichever renderer the build draws: today's
 * Recharts charts in the e2e-tests job, the spec renderer's (NEXT_PUBLIC_CHARTS_V2) in e2e-charts-v2, which runs this
 * file too (step 6 of the trend-chart migration, E194). Recharts' keyboard and notes case runs on Recharts alone;
 * charts-v2.spec.ts holds the renderer's, and step 7 (E195) retires it.
 */
const EPSILON = 1 // Fractional CSS-pixel rounding, never a visual overflow allowance.
const STATES: AnalysisState[] = ['clean', 'legacy', 'discrepancy']
const THEMES: AnalysisTheme[] = ['light', 'dark']
const PROFILES = [
  { name: '320px', width: 320, height: 800 },
  { name: '390px', width: 390, height: 844 },
  { name: '768px', width: 768, height: 1024 },
  { name: '1024px', width: 1024, height: 1000 },
  { name: '1480px', width: 1480, height: 1000 },
  { name: '200% text at 320px', width: 320, height: 1000, textScale: 2 },
  { name: '200% text at 390px', width: 390, height: 1000, textScale: 2 },
  { name: '200% text at 1480px', width: 1480, height: 1000, textScale: 2 },
  { name: '200% viewport/DPR zoom emulation', width: 740, height: 500, deviceScaleFactor: 2 },
]
const TABLE = '[data-analysis-metrics] table'
const NOTES = '[data-analysis-data-notes]'

// The suite's longest file. Run in order, its tests kept one worker busy for the whole e2e run while
// the other finished every other spec in a few minutes and then idled. They share nothing (each opens
// its own page through openAnalysis; no hooks, no mutable module state), so both workers take them.
test.describe.configure({ mode: 'parallel' })
// Full font hinting, headless Chrome's default (CI's) and some desktops': at 1x it snaps every glyph's advance to a
// whole pixel (14px for Geist Mono's 14.4 at 24px), so the KPI strip's budget, measured where it paints, is checked in
// the case where 0.6em would be wrong. The local browser's wrapper passes --font-render-hinting=none; the last flag
// wins (charts-v2.spec.ts pins it for the same reason).
test.use({ launchOptions: { args: ['--font-render-hinting=full'] } })

for (const theme of THEMES) for (const width of [390, 1480]) {
  test.describe(`analysis evidence / ${theme} / ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    test('keeps short evidence visible and restores disclosures after printing', async ({ page, baseURL }) => {
      test.setTimeout(60_000)
      await openAnalysis(page, baseURL!, 'legacy', theme, 1, true)
      const prose = page.locator('.markdown-body')
      const lists = prose.getByRole('list', { name: 'Figures behind this finding', includeHidden: true })
      await expect(lists).toHaveCount(3)
      for (const index of [0, 2]) {
        await expect(lists.nth(index)).toBeVisible()
        await expect(lists.nth(index).locator('button').first()).toBeVisible()
        expect(await lists.nth(index).evaluate(el => !!el.closest('details'))).toBe(false)
      }
      const fold = prose.locator('details')
      await expect(fold).toHaveCount(1)
      await expect(fold).not.toHaveAttribute('open')
      await expect(fold.locator('summary')).toContainText('Show the 20 source figures behind this · figures carry note a')
      const notes = page.locator(`${NOTES} > details`)
      await notes.locator(':scope > summary').click()
      const prior = await page.locator('[data-analysis-print-scope] details').evaluateAll(items => items.map(item => (item as HTMLDetailsElement).open))
      expect(prior).toContain(true)
      expect(prior).toContain(false)
      await page.evaluate(() => { window.dispatchEvent(new Event('beforeprint')); window.dispatchEvent(new Event('beforeprint')) })
      expect(await page.locator('[data-analysis-print-scope] details').evaluateAll(items => items.every(item => (item as HTMLDetailsElement).open))).toBe(true)
      await expect(lists.nth(1)).toBeVisible()
      await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
      expect(await page.locator('[data-analysis-print-scope] details').evaluateAll(items => items.map(item => (item as HTMLDetailsElement).open))).toEqual(prior)
    })
  })
}

async function pageAndCardGeometry(page: Page) {
  return page.evaluate(() => {
    const bounds = (el: Element) => el.getBoundingClientRect()
    // aria-hidden is not visually hidden: include the painted † and note letters.
    const visible = (el: Element) => el.checkVisibility({ visibilityProperty: true }) && !el.closest('.sr-only,[hidden]')
    const cards = [...document.querySelectorAll('[data-analysis-kpi]')].map((card, index) => {
      const box = bounds(card)
      const value = card.querySelector('[data-kpi-value]')
      const spills: Array<{ text: string; horizontal: number; vertical: number }> = []
      const record = (rect: DOMRect, text: string) => {
        const horizontal = Math.max(0, box.left - rect.left, rect.right - box.right)
        const vertical = Math.max(0, box.top - rect.top, rect.bottom - box.bottom)
        if (horizontal > 1 || vertical > 1) spills.push({ text: text.trim().slice(0, 100), horizontal, vertical })
      }
      for (const child of card.querySelectorAll('*')) {
        if (!visible(child)) continue
        record(bounds(child), child.textContent || '')
      }
      // A nowrap text node can overflow a correctly sized element. Element bounds alone
      // would miss exactly the KPI-label regression this gate must detect.
      const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.textContent?.trim() || !node.parentElement || !visible(node.parentElement)) continue
        const range = document.createRange(); range.selectNodeContents(node)
        for (const rect of range.getClientRects()) if (rect.width && rect.height) record(rect, node.textContent)
      }
      // The value's line, its figure and marks: the union of its painted glyphs.
      const glyphs: DOMRect[] = []
      const button = value?.querySelector('button')
      if (button) {
        const values = document.createTreeWalker(button, NodeFilter.SHOW_TEXT)
        for (let node = values.nextNode(); node; node = values.nextNode()) {
          if (!node.textContent?.trim() || !node.parentElement || node.parentElement.closest('.sr-only')) continue
          const range = document.createRange(); range.selectNodeContents(node)
          glyphs.push(...[...range.getClientRects()].filter(rect => rect.width))
        }
      }
      const style = getComputedStyle(card)
      const chrome = ['paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth'].reduce((sum, key) => sum + parseFloat(style[key as 'paddingLeft']), 0)
      const line = glyphs.length ? Math.max(...glyphs.map(rect => rect.right)) - Math.min(...glyphs.map(rect => rect.left)) : 0
      return { index, top: box.top, valueTop: value ? bounds(value).top : null, spills, line, chrome }
    })
    const rows: Array<{ top: number; valueTops: number[] }> = []
    for (const card of cards) {
      let row = rows.find(row => Math.abs(row.top - card.top) < 1)
      if (!row) { row = { top: card.top, valueTops: [] }; rows.push(row) }
      if (card.valueTop !== null) row.valueTops.push(card.valueTop)
    }
    const strip = document.querySelector('[data-analysis-kpi]')!.parentElement!
    const rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize)
    // The budget as the grid resolves it: a CSS max() over the values at the advances the strip measured.
    const ruler = strip.appendChild(document.createElement('div'))
    ruler.style.cssText = 'position:absolute;visibility:hidden;width:var(--kpi-value)'
    const kpiBudget = ruler.getBoundingClientRect().width
    ruler.remove()
    return {
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      kpiWidth: strip.getBoundingClientRect().width,
      kpiBudget,
      kpiGap: parseFloat(getComputedStyle(strip).columnGap),
      rootFontSize,
      cards,
      rows: rows.map(row => ({ values: row.valueTops.length, spread: Math.max(...row.valueTops) - Math.min(...row.valueTops) })),
    }
  })
}

async function assertPageAndCards(page: Page, width: number, textScale: number, state: AnalysisState) {
  const geometry = await pageAndCardGeometry(page)
  // Presence is independent of painting: omitted marks must not pass an empty loop.
  for (const [index, expected] of EXPECTED_KPI_VALUES.entries()) {
    const card = page.locator('[data-analysis-kpi]').nth(index)
    await expect(card.locator('dt')).toHaveText(expected.label)
    const source = card.locator('button[aria-label$="View source and calculation"]')
    await expect(source.locator('span').filter({ hasText: /^†$/ })).toHaveCount(expected.daggers)
    const letters = EXPECTED_KPI_LETTERS[state][index]
    for (const { scope, expectedLetters } of [
      { scope: source, expectedLetters: letters.value },
      { scope: card.locator('dd').last(), expectedLetters: letters.growth },
    ]) {
      const marks = scope.locator('[data-note-letter]')
      // Exact arrays enforce presence and identity, including no unexpected note kind.
      await expect(marks).toHaveText([...expectedLetters], { useInnerText: true })
      for (const [markIndex, letter] of expectedLetters.entries()) {
        await expect(marks.nth(markIndex)).toHaveAttribute('data-note-letter', letter)
        await expect(marks.nth(markIndex)).toHaveAttribute('data-note-kind', 'review')
      }
    }
  }
  await assertPaintedMarks(page, '[data-analysis-kpi]')
  expect(geometry.rootFontSize).toBeCloseTo(16 * textScale, 1)
  await assertKpiStrip(page, width, geometry)
  // The dollar fixtures' counts, pinned apart from the budget: two across at phone widths (decision 4, 320px
  // included) and on tablets, four from lg at ordinary text and at 1480px under 200% text, one on a phone under 200%.
  expect(geometry.rows[0].values, 'the dollar fixtures keep two cards below lg and four from lg').toBe(textScale > 1 && width < 1024 ? 1 : width >= 1024 ? 4 : 2)
}

/** The columns KpiStrip's grid gives (E197): auto-fill tracks of at least the widest card (its value plus padding and
 *  border), half the strip below lg, and from lg a column per tile, four at most, or half the strip once a card is
 *  wider than that, never three of four; one below 17em of its own text size. Each share keeps 0.5px back, as
 *  KpiStrip's do. The budget it starts from is checked against the painted values, and the dollar fixtures' counts are
 *  pinned apart from it (assertPageAndCards). */
function expectedKpiColumns(geometry: Awaited<ReturnType<typeof pageAndCardGeometry>>, width: number) {
  if (geometry.kpiWidth < 17 * geometry.rootFontSize) return 1
  const strip = geometry.kpiWidth, gap = geometry.kpiGap
  const card = geometry.kpiBudget + Math.max(...geometry.cards.map(item => item.chrome))
  const half = (strip - gap) / 2 - 0.5
  const tiles = Math.min(4, geometry.cards.length)
  const each = (strip - (tiles - 1) * gap) / tiles - 0.5
  const track = width >= 1024 ? Math.max(each, card, Math.min(half, each + (card - each) * 1e6)) : Math.max(card, half)
  return Math.min(geometry.cards.length, Math.max(1, Math.floor((strip + gap) / (track + gap))))
}

/** No KPI value leaves its card or wraps, the page does not scroll sideways, the strip's budget is its widest value as
 *  painted, and the columns are the most that value allows. */
async function assertKpiStrip(page: Page, width: number, measured?: Awaited<ReturnType<typeof pageAndCardGeometry>>) {
  const geometry = measured ?? await pageAndCardGeometry(page)
  await assertSourceControls(page, '[data-analysis-kpi]', 4)
  expect(geometry.scrollWidth, 'document must fit its layout viewport (including invisible positioned boxes)').toBeLessThanOrEqual(geometry.clientWidth + EPSILON)
  expect(geometry.scrollWidth, 'document must fit the configured viewport, even when innerWidth expands').toBeLessThanOrEqual(width + EPSILON)
  expect(geometry.clientWidth).toBeLessThanOrEqual(width)
  expect(geometry.cards).toHaveLength(4)
  for (const card of geometry.cards) {
    expect(card.valueTop, `KPI ${card.index} has a measured value`).not.toBeNull()
    expect(card.spills, `KPI ${card.index} child/text containment`).toEqual([])
  }
  // The budget is the widest value as painted: never under it, or a card would be too narrow for it, and within a pixel
  // over it, or the strip would give up a column it has room for.
  const widest = Math.max(...geometry.cards.map(card => card.line))
  expect(widest, 'a KPI value was measured').toBeGreaterThan(0)
  expect(geometry.kpiBudget - widest, `the strip's budget (${geometry.kpiBudget}px) against its widest value (${widest}px)`).toBeGreaterThanOrEqual(-0.5)
  expect(geometry.kpiBudget - widest, `the strip's budget (${geometry.kpiBudget}px) against its widest value (${widest}px)`).toBeLessThanOrEqual(1)
  expect(geometry.rows.length).toBeGreaterThan(0)
  const columns = expectedKpiColumns(geometry, width)
  for (const row of geometry.rows) {
    expect(row.values, 'KPI count follows its widest value and its own width at the active text size').toBe(columns)
    // Compare only cards in the same physical row; a phone's second row is independent.
    expect(row.values).toBeGreaterThan(0)
    expect(row.spread, 'numeric value tops align within each physical KPI row').toBeLessThanOrEqual(EPSILON)
  }
}

/** Pair text geometry with computed ink alpha; this is not a full pixel-paint oracle. */
async function assertPaintedMarks(page: Page, selector: string) {
  const marks = await page.locator(selector).evaluateAll(containers => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    const context = canvas.getContext('2d')!
    const inkAlpha = (parent: Element) => {
      const style = getComputedStyle(parent)
      // Chromium's text-fill can override color, including making opaque color invisible.
      const fill = style.getPropertyValue('-webkit-text-fill-color')
      const color = fill && fill !== 'currentcolor' ? fill : style.color
      context.clearRect(0, 0, 1, 1)
      context.fillStyle = 'transparent'
      context.fillStyle = color
      context.fillRect(0, 0, 1, 1)
      return context.getImageData(0, 0, 1, 1).data[3]
    }
    return containers.flatMap(container =>
      [...container.querySelectorAll('[data-note-letter], span')]
        .filter(mark => mark.hasAttribute('data-note-letter') || mark.textContent?.trim() === '†')
        .map(mark => {
          const visible = mark.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && !mark.closest('.sr-only,[hidden]')
          const glyphs: Array<{ width: number; height: number; inkAlpha: number }> = []
          const walker = document.createTreeWalker(mark, NodeFilter.SHOW_TEXT)
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const parent = node.parentElement
            if (!node.textContent?.trim() || !parent?.checkVisibility({ visibilityProperty: true, opacityProperty: true }) || parent.closest('.sr-only,[hidden]')) continue
            const alpha = inkAlpha(parent)
            const range = document.createRange(); range.selectNodeContents(node)
            for (const rect of range.getClientRects()) if (rect.width > 0 && rect.height > 0) glyphs.push({ width: rect.width, height: rect.height, inkAlpha: alpha })
          }
          return { text: mark.textContent?.trim(), kind: mark.getAttribute('data-note-kind'), visible, glyphs }
        })
    )
  })
  for (const mark of marks) {
    expect(mark.visible, `${mark.kind ?? 'calculated'} mark ${mark.text}: element is not hidden or zero-opacity`).toBe(true)
    // A legitimate superscript has line-height: 0. Its element box can have zero height;
    // use text ranges, never element height or Playwright's toBeVisible().
    expect(mark.glyphs.length, `${mark.kind ?? 'calculated'} mark ${mark.text}: nonzero text range`).toBeGreaterThan(0)
    for (const glyph of mark.glyphs) expect(glyph.inkAlpha, `${mark.kind ?? 'calculated'} mark ${mark.text}: computed text ink is not transparent`).toBeGreaterThan(0)
  }
}

/** Keep only a numeric source control on one line; row labels and captions may wrap. */
async function assertSourceControls(page: Page, selector: string, expected: number) {
  const controls = page.locator(`${selector} button[aria-label$="View source and calculation"]`)
  await expect(controls).toHaveCount(expected)
  const measured = await controls.evaluateAll(buttons => buttons.map(button => {
    const box = button.getBoundingClientRect()
    const glyphs: Array<{ text: string; mark: boolean; left: number; right: number; top: number; bottom: number }> = []
    const walker = document.createTreeWalker(button, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement
      if (!node.textContent?.trim() || !parent || !parent.checkVisibility({ visibilityProperty: true }) || parent.closest('.sr-only,[hidden]')) continue
      // aria-hidden affects the accessible name, not painting. Daggers and note letters
      // MUST participate: a wrapped/clipped mark changes the meaning of the number.
      const mark = !!parent.closest('sup,[data-note-letter]') || node.textContent.trim() === '†'
      const range = document.createRange(); range.selectNodeContents(node)
      for (const rect of range.getClientRects()) if (rect.width && rect.height) {
        glyphs.push({ text: node.textContent.trim(), mark, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom })
      }
    }
    const baseGlyphs = glyphs.filter(glyph => !glyph.mark)
    const lines: Array<{ top: number; bottom: number }> = []
    for (const glyph of baseGlyphs) {
      const line = lines.find(line => Math.min(line.bottom, glyph.bottom) > Math.max(line.top, glyph.top))
      if (line) { line.top = Math.max(line.top, glyph.top); line.bottom = Math.min(line.bottom, glyph.bottom) }
      else lines.push({ top: glyph.top, bottom: glyph.bottom })
    }
    const firstLine = lines[0]
    let previousRight = baseGlyphs.at(-1)?.right ?? box.left
    const detachedMarks = glyphs.filter(glyph => glyph.mark).filter(mark => {
      // Superscripts naturally rise above the numeric baseline. Require vertical contact
      // with its glyph band and monotonic inline placement after the value/previous mark;
      // a mark wrapped onto the next line moves left even if the superscript overlaps above.
      const detached = !firstLine || mark.left < previousRight - 1 || mark.top > firstLine.bottom + 1 || mark.bottom < firstLine.top - 1
      previousRight = mark.right
      return detached
    })
    const outsideControl = glyphs.filter(glyph => glyph.left < box.left - 1 || glyph.right > box.right + 1)
    return { name: button.getAttribute('aria-label'), baseText: baseGlyphs.map(glyph => glyph.text).join(''), baseGlyphCount: baseGlyphs.length, baseLines: lines.length, detachedMarks, outsideControl }
  }))
  for (const control of measured) {
    expect(control.baseGlyphCount, `${control.name}: actual numeric/unavailable glyphs measured`).toBeGreaterThan(0)
    expect(control.baseLines, `${control.name}: source value stays on one line`).toBe(1)
    expect(control.detachedMarks, `${control.name}: visible dagger/letter stays attached to its value`).toEqual([])
    expect(control.outsideControl, `${control.name}: visible glyphs fit their source control`).toEqual([])
    if (control.name?.includes(': unavailable')) expect(control.baseText, 'unavailable figures remain a visible dash, never zero').toBe('—')
  }
}

async function tableGeometry(page: Page) {
  return page.locator(TABLE).evaluate(async (table) => {
    const rect = (el: Element) => el.getBoundingClientRect()
    let scroller: HTMLElement | null = table.parentElement
    while (scroller && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowX)) scroller = scroller.parentElement
    if (!scroller) throw new Error('Metrics table needs its own native horizontal scroll container')
    const scroll = scroller
    const rows = [...table.querySelectorAll('tr')]
    const textRects = (cell: Element) => {
      const texts: Array<{ text: string; left: number; right: number; clippedBy: string[] }> = []
      const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const parent = node.parentElement
        if (!node.textContent?.trim() || !parent || !parent.checkVisibility({ visibilityProperty: true }) || parent.closest('.sr-only,[hidden]')) continue
        const range = document.createRange(); range.selectNodeContents(node)
        for (const textBox of range.getClientRects()) {
          if (!textBox.width || !textBox.height) continue
          const clippedBy: string[] = []
          for (let ancestor: Element | null = parent; ancestor && ancestor !== cell.parentElement; ancestor = ancestor.parentElement) {
            const style = getComputedStyle(ancestor); const box = rect(ancestor)
            if ((/(hidden|clip)/.test(style.overflowX) && (textBox.left < box.left - 1 || textBox.right > box.right + 1)) ||
                (/(hidden|clip)/.test(style.overflowY) && (textBox.top < box.top - 1 || textBox.bottom > box.bottom + 1))) clippedBy.push(ancestor.tagName)
          }
          texts.push({ text: node.textContent.trim().slice(0, 90), left: textBox.left, right: textBox.right, clippedBy })
        }
      }
      return texts
    }
    const clippedCells = rows.flatMap((row, rowIndex) => [...row.children].flatMap((cell, column) => {
      const box = rect(cell)
      const style = getComputedStyle(cell)
      const outside = textRects(cell).filter(text => text.left < box.left + parseFloat(style.paddingLeft) - 1 || text.right > box.right - parseFloat(style.paddingRight) + 1 || text.clippedBy.length)
      return outside.length ? [{ row: rowIndex, column, outside }] : []
    }))
    const headers = [...table.querySelectorAll('thead th')]
    const widths = headers.slice(1).map(cell => rect(cell).width)
    const step = widths[0]
    const sticky = getComputedStyle(headers[0]).position === 'sticky'
    const inset = sticky ? rect(headers[0]).width : 0
    const maximum = scroll.scrollWidth - scroll.clientWidth
    const initial = scroll.scrollLeft
    const offset = sticky ? 0 : rect(headers[0]).width
    const stops = [0, ...widths.map((_, index) => offset + index * step)].filter(stop => stop <= maximum + 1)
    const targets = [...new Set([...stops, ...stops.map(stop => stop + step * 0.4), maximum])]
    const rests: Array<{ target: number; left: number; stable: boolean; partialColumns: number; visibleColumns: number }> = []
    const lastColumnClipped: Array<{ row: number; text: string }> = []
    const labelClippedAtHome: Array<{ row: number; text: string }> = []
    for (const target of targets) {
      scroll.scrollTo({ left: target, behavior: 'instant' })
      let stableFrames = 0, previous = -1, frame = 0
      while (stableFrames < 5 && frame++ < 120) {
        await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
        const next = scroll.scrollLeft
        stableFrames = Math.abs(next - previous) < 0.1 ? stableFrames + 1 : 0
        previous = next
      }
      const scrollBox = rect(scroll)
      const boundary = scrollBox.left + inset
      const partialColumns = headers.slice(1).filter(cell => {
        const box = rect(cell)
        return box.right > boundary + 1 && box.left < boundary - 1
      }).length
      const visibleColumns = headers.slice(1).filter(cell => {
        const box = rect(cell)
        return box.left >= boundary - 1 && box.right <= scrollBox.right + 1
      }).length
      rests.push({ target, left: scroll.scrollLeft, stable: stableFrames >= 5, partialColumns, visibleColumns })
      if (target === 0) for (const [rowIndex, row] of rows.entries()) {
        for (const text of textRects(row.firstElementChild!)) if (text.left < scrollBox.left - 1 || text.right > scrollBox.right + 1) {
          labelClippedAtHome.push({ row: rowIndex, text: text.text })
        }
      }
      if (target === maximum) for (const [rowIndex, row] of rows.entries()) {
        const cell = row.lastElementChild!
        for (const text of textRects(cell)) if (text.left < boundary - 1 || text.right > scrollBox.right + 1) {
          lastColumnClipped.push({ row: rowIndex, text: text.text })
        }
      }
    }
    const valueSpreads = rows.slice(1).map(row => {
      const tops = [...row.querySelectorAll('td')].map(cell => rect(cell.querySelector('button') ?? cell.firstElementChild!).top)
      return Math.max(...tops) - Math.min(...tops)
    })
    return {
      widths, clippedCells, lastColumnClipped, labelClippedAtHome, valueSpreads, rests, sticky, inset, initial, stops,
      scrollLeft: scroll.scrollLeft, maximum, viewport: scroll.clientWidth,
      role: scroll.getAttribute('role'), tabIndex: scroll.getAttribute('tabindex'), label: scroll.getAttribute('aria-label'),
    }
  })
}

async function assertTable(page: Page, state: AnalysisState) {
  // The table always holds every period: the 6-of-N window is retired.
  const expectedPeriods = PERIODS
  const table = page.locator(TABLE)
  const headers = table.locator('thead th')
  await expect(headers).toHaveCount(expectedPeriods.length + 1)
  await expect(table.locator('tbody tr')).toHaveCount(METRICS)
  const labels = await headers.evaluateAll(cells => cells.map(cell => (cell.querySelector('[data-period-label]') ?? cell).textContent ?? ''))
  expect(labels.slice(1).map(label => label.replace(/[\s†]/g, ''))).toEqual(expectedPeriods.map(period => `${period.slice(4)}’${period.slice(2, 4)}`))
  for (const [index, period] of expectedPeriods.entries()) await expect(headers.nth(index + 1)).toHaveAccessibleName(new RegExp(`^${period.slice(4)} ${period.slice(0, 4)}(?:,|$)`))
  for (const row of await table.locator('tbody tr').all()) await expect(row.locator(':scope > th, :scope > td')).toHaveCount(expectedPeriods.length + 1)
  const sourceControls = table.locator('tbody button[aria-label$="View source and calculation"]')
  let unavailableCount = 0
  for (const missing of UNAVAILABLE_CELLS) for (const period of missing.periods) {
    const column = expectedPeriods.indexOf(period)
    if (column < 0) continue
    unavailableCount++
    await expect(table.locator('tbody tr').nth(missing.row).locator('td').nth(column).locator('button')).toHaveAttribute('aria-label', /: unavailable/)
  }
  await expect(sourceControls.locator('[data-note-kind="unavailable"]')).toHaveCount(unavailableCount)
  await expect(table.locator('tbody button[aria-label*="\u003a unavailable"]')).toHaveCount(unavailableCount)
  // Count value marks inside source controls separately from comparison marks below them.
  await expect(sourceControls.locator('[data-note-kind="review"]')).toHaveCount(EXPECTED_TABLE_REVIEWS[state])
  // Q4 header daggers cannot satisfy value-mark presence; count inside source buttons.
  await expect(sourceControls.locator('span').filter({ hasText: /^†$/ })).toHaveCount(EXPECTED_TABLE_VALUE_DAGGERS)
  await expect(table.locator('tbody [data-note-kind="review"]:not(button *)')).toHaveCount(EXPECTED_TABLE_COMPARISON_REVIEWS[state])
  const expectedNotes = EXPECTED_TABLE_CELL_NOTES[state]
  const expectedCells = Array.from({ length: METRICS }, (_, row) => expectedPeriods.map(period => {
    const notes = (slots: typeof expectedNotes.value) => slots
      .filter(slot => slot.rows.includes(row) && slot.periods.includes(period))
      .map(({ letter, kind }) => ({ text: letter, letter, kind }))
    const unavailable = UNAVAILABLE_CELLS.some(slot => slot.row === row && slot.periods.some(key => key === period))
    return {
      value: unavailable ? [{ text: expectedNotes.unavailableLetter, letter: expectedNotes.unavailableLetter, kind: 'unavailable' }] : notes(expectedNotes.value),
      comparison: notes(expectedNotes.comparison),
    }
  }))
  const actualCells = await table.locator('tbody tr').evaluateAll(rows => rows.map(row =>
    [...row.querySelectorAll('td')].map(cell => {
      const marks = [...cell.querySelectorAll<HTMLElement>('[data-note-letter], [data-note-kind]')]
      const source = (mark: Element) => !!mark.closest('button[aria-label$="View source and calculation"]')
      const read = (mark: HTMLElement) => ({ text: mark.innerText.trim(), letter: mark.getAttribute('data-note-letter'), kind: mark.getAttribute('data-note-kind') })
      return { value: marks.filter(source).map(read), comparison: marks.filter(mark => !source(mark)).map(read) }
    })
  ))
  expect(actualCells, 'each financial cell retains its exact value/comparison note, including cells with no note').toEqual(expectedCells)
  const letters = [...new Set(expectedCells.flat().flatMap(cell => [...cell.value, ...cell.comparison].map(mark => mark.letter)))].sort()
  await expect(page.locator('[data-analysis-metrics]').getByRole('button', { name: `Review data notes ${letters.join(', ')}`, exact: true })).toBeVisible()
  await assertPaintedMarks(page, TABLE)
  await assertSourceControls(page, `${TABLE} tbody`, METRICS * expectedPeriods.length)
  await assertTableGeometry(page, expectedPeriods.length)
}

async function assertTableGeometry(page: Page, expectedColumns: number) {
  const geometry = await tableGeometry(page)
  expect(geometry.widths).toHaveLength(expectedColumns)
  expect(Math.min(...geometry.widths), 'period columns cannot collapse').toBeGreaterThan(0)
  expect(Math.max(...geometry.widths) - Math.min(...geometry.widths), 'every period receives the same width').toBeLessThanOrEqual(EPSILON)
  expect(geometry.clippedCells, 'actual glyph ranges fit every header and body cell, including hidden-by-overflow descendants').toEqual([])
  expect(geometry.labelClippedAtHome, 'every label glyph is readable at the Home stop').toEqual([])
  expect(geometry.maximum - geometry.scrollLeft, 'last period remains reachable at the far-right endpoint').toBeLessThanOrEqual(EPSILON)
  for (const rest of geometry.rests) {
    expect(rest.stable, `native snap settles after aiming at ${rest.target}`).toBe(true)
    expect(geometry.stops.some(stop => Math.abs(stop - rest.left) <= EPSILON), `rest ${rest.left} is a whole-column boundary`).toBe(true)
    expect(rest.partialColumns, `no period straddles the active sticky inset at ${rest.left}`).toBe(0)
    if (rest.left > 0 || geometry.sticky) expect(rest.visibleColumns, 'at least one entire period is visible').toBeGreaterThan(0)
  }
  expect(geometry.stops.some(stop => Math.abs(stop - geometry.maximum) <= EPSILON), 'the far endpoint is a real column stop').toBe(true)
  expect(geometry.lastColumnClipped, 'the complete last period remains readable at the far-right endpoint').toEqual([])
  for (const spread of geometry.valueSpreads) expect(spread, 'missing values and mixed-height growth rows share the value top').toBeLessThanOrEqual(EPSILON)
  if (geometry.sticky) expect(geometry.viewport - geometry.inset).toBeGreaterThanOrEqual(geometry.widths[0] - EPSILON)
  expect(geometry.role).toBe(geometry.maximum > 0 ? 'region' : null)
  expect(geometry.tabIndex).toBe(geometry.maximum > 0 ? '0' : null)
  if (geometry.maximum > 0) expect(geometry.label).toContain('Metrics by period')
  else expect(geometry.label).toBeNull()

  // A correctly positioned sticky label can still leak scrolled text through a
  // translucent hover background. Measure its actual painted background, not a class.
  const rowHeader = page.locator(`${TABLE} tbody th[scope="row"]`).first()
  if (!geometry.sticky) return
  await rowHeader.hover()
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  await expect.poll(async () => rowHeader.evaluate(cell => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    const context = canvas.getContext('2d')!
    context.fillStyle = getComputedStyle(cell).backgroundColor
    context.fillRect(0, 0, 1, 1)
    return context.getImageData(0, 0, 1, 1).data[3]
  }), { message: 'hovered sticky row labels stay opaque over scrolled financial values' }).toBe(255)
}

async function stableAnalysisOutsideTable(page: Page) {
  return {
    kpis: await page.locator('[data-analysis-kpi]').allTextContents(),
    notes: await page.locator(`${NOTES} > details > summary`).innerText(),
    charts: await page.locator('[data-analysis-chart]').evaluateAll(readTicksAndShapes, CHARTS_V2),
  }
}

async function assertNotes(page: Page, state: AnalysisState) {
  const expected = EXPECTED_NOTES[state]
  const summary = page.locator(`${NOTES} > details > summary`)
  await expect(summary).toContainText(`${expected.unavailable} unavailable`)
  await expect(summary).toContainText(`${expected.calculated} calculated`)
  if (state === 'clean') {
    await expect(summary).toContainText(`No figures need review · ${expected.passed} checked`)
    await expect(summary).toContainText(`${expected.unavailable} unavailable (a)`)
  } else {
    await expect(summary).toContainText(`${expected.reviewValues} figures need review (a)`)
    await expect(summary).toContainText(`${expected.reviewComparisons} comparisons carry note a`)
    await expect(summary).toContainText(`${expected.unavailable} unavailable (b)`)
    await expect(summary).not.toContainText('No figures need review')
  }
  await expect(summary).not.toContainText('passed automated checks')
  await expect(summary).not.toContainText('no validation record')
}

for (const theme of THEMES) for (const profile of PROFILES) {
  test.describe(`analysis layout / ${theme} / ${profile.name}`, () => {
    test.use({ viewport: { width: profile.width, height: profile.height }, deviceScaleFactor: profile.deviceScaleFactor ?? 1, isMobile: profile.width <= 390, hasTouch: profile.width <= 390, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    for (const state of STATES) test(`${state}: content stays readable with every period in the table`, async ({ page, baseURL }) => {
      test.setTimeout(60_000)
      const traffic = await openAnalysis(page, baseURL!, state, theme, profile.textScale ?? 1)
      await assertNotes(page, state)
      await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
      await drawnCharts(page)
      const baseline = await stableAnalysisOutsideTable(page)
      for (const chart of baseline.charts) {
        expect(chart.ticks.map(tick => tick.text), `${chart.name}: all twelve ordered chart periods`).toEqual(PERIODS.map(period => tickText(period, CHARTS_V2)))
        for (const tick of chart.ticks) expect(tick.painted, `${chart.name}: ${tick.text} has visible glyphs`).toBe(true)
        expect(chart.shapes.length, `${chart.name}: actual plotted data`).toBeGreaterThan(0)
      }
      const section = page.locator('[data-analysis-metrics]')
      // Every period, always: the 6-of-N window is retired, so no control can narrow the table.
      await expect(section.getByRole('group', { name: 'Table window', exact: true })).toHaveCount(0)
      await assertTable(page, state)
      await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
      expect(await stableAnalysisOutsideTable(page), 'the table leaves KPI, note totals and chart data alone').toEqual(baseline)
      // Disclosure content is also part of the responsive page, not an overflow escape hatch.
      await section.getByRole('button', { name: /^Review data notes/ }).focus()
      await page.keyboard.press('Enter')
      await expect(page.locator(`${NOTES} > details`)).toHaveAttribute('open', '')
      await expect(page.locator(`${NOTES} li`).first()).toBeFocused()
      await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
      expect(traffic.dataset, 'the report reads its dataset once').toBe(1)
      expect(traffic.stream, 'the report never regenerates analysis').toBe(1)
      expect(traffic.unexpectedApi).toEqual([])
    })
  })
}

async function settleTable(page: Page) {
  return page.locator(TABLE).evaluate(async table => {
    const scroll = table.parentElement!
    let stable = 0, previous = -1
    for (let frame = 0; stable < 5 && frame < 120; frame++) {
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      stable = Math.abs(scroll.scrollLeft - previous) < 0.1 ? stable + 1 : 0
      previous = scroll.scrollLeft
    }
    return { left: scroll.scrollLeft, max: scroll.scrollWidth - scroll.clientWidth, y: window.scrollY }
  })
}

for (const theme of THEMES) for (const profile of [
  { width: 390, textScale: 1 }, { width: 1024, textScale: 1 }, { width: 320, textScale: 2 },
]) test.describe(`analysis keyboard / ${theme} / ${profile.width}px / text ${profile.textScale}`, () => {
  test.use({ viewport: { width: profile.width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
  test('keeps native table keys and every tabbed period inside the active scrollport', async ({ page, baseURL }) => {
    test.setTimeout(90_000)
    await openAnalysis(page, baseURL!, 'legacy', theme, profile.textScale)
    const initial = await settleTable(page)
    if (profile.width < 640) expect(initial.max - initial.left, 'phones initially show the newest period').toBeLessThanOrEqual(EPSILON)
    const section = page.locator('[data-analysis-metrics]')
    const region = section.getByRole('region', { name: /Metrics by period/ })
    const assertEarlierHint = async (left: number) => {
      const hint = section.getByText('← Earlier quarters', { exact: true })
      if (profile.width < 640 && left > EPSILON) {
        await expect(hint).toBeVisible()
        await expect(region).toHaveAccessibleDescription('← Earlier quarters')
      } else {
        await expect(hint).toBeHidden()
        await expect(region).not.toHaveAttribute('aria-describedby')
      }
    }
    await assertEarlierHint(initial.left)
    // The scroll region is the next Tab stop after the card's last heading control (Export Excel on the Pro surface).
    const exportButton = section.getByRole('button', { name: 'Export Excel', exact: true })
    await (await exportButton.count() ? exportButton : section.getByRole('button', { name: /^Review data notes/ })).focus()
    await page.keyboard.press('Tab')
    await expect(region).toBeFocused()
    const baseline = await settleTable(page)
    for (const key of ['Home', 'ArrowRight', 'ArrowLeft', 'End', 'PageUp', 'PageDown']) {
      const before = await settleTable(page)
      await page.keyboard.press(key)
      const after = await settleTable(page)
      await assertEarlierHint(after.left)
      expect(after.y, `${key} belongs to the table, not the page`).toBe(baseline.y)
      if (key === 'Home' || key === 'ArrowLeft') expect(after.left).toBe(0)
      else if (key === 'End' || key === 'PageDown') expect(after.left).toBeCloseTo(after.max, 0)
      else if (key === 'ArrowRight') expect(after.left).toBeGreaterThan(before.left)
      else expect(after.left).toBeLessThan(before.left)
    }
    await page.keyboard.press('Home')
    // Start from the scroll region and follow the browser's actual Tab sequence across
    // two whole rows, including the wrap from the final period back to the earliest.
    const sources = section.locator('tbody button[aria-label$="View source and calculation"]')
    const forward = Array.from({ length: PERIODS.length * 2 }, (_, index) => ({ index, key: 'Tab' }))
    const backward = forward.slice(0, -1).reverse().map(step => ({ ...step, key: 'Shift+Tab' }))
    for (const { index, key } of [...forward, ...backward]) {
      await page.keyboard.press(key)
      await expect(sources.nth(index)).toBeFocused()
      await settleTable(page)
      const fraction = await sources.nth(index).evaluate(button => {
        const cell = button.closest('td')!
        const scroll = button.closest('table')!.parentElement!
        const box = cell.getBoundingClientRect(), viewport = scroll.getBoundingClientRect()
        const header = cell.parentElement!.firstElementChild!
        const inset = getComputedStyle(header).position === 'sticky' ? header.getBoundingClientRect().width : 0
        return Math.max(0, Math.min(box.right, viewport.right) - Math.max(box.left, viewport.left + inset)) / box.width
      })
      expect(fraction, `${key} cell ${index} is fully visible after native snapping`).toBeGreaterThanOrEqual(0.99)
    }
    const source = sources.first()
    await source.evaluate(button => {
      button.addEventListener('keydown', event => {
        queueMicrotask(() => button.setAttribute('data-key-prevented', String(event.defaultPrevented)))
      })
    })
    const beforeChild = await settleTable(page)
    await page.keyboard.press('Home')
    await expect(source).toHaveAttribute('data-key-prevented', 'false')
    expect((await settleTable(page)).left, 'a child control retains its own Home key').toBe(beforeChild.left)

    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    const close = dialog.getByRole('button', { name: 'Close', exact: true })
    await expect(close).toBeFocused()
    const technical = dialog.locator('summary').last()
    await expect(technical).toHaveText('Technical source details')
    await page.keyboard.press('Shift+Tab')
    await expect(technical, 'the last technical disclosure participates in the dialog trap').toBeFocused()
    await page.keyboard.press('Tab')
    await expect(close, 'Tab wraps from the last disclosure to Close').toBeFocused()
    await page.keyboard.press('Shift+Tab')
    const portalled = await settleTable(page)
    for (const key of ['Home', 'End', 'ArrowLeft', 'ArrowRight']) {
      await page.keyboard.press(key)
      expect((await settleTable(page)).left, `${key} in a portalled dialog cannot move its table`).toBe(portalled.left)
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(source).toBeFocused()

    // Preserve the same leading period as the viewport and actual text size change.
    await region.focus()
    await page.keyboard.press('Home')
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('ArrowRight')
    await settleTable(page)
    const leading = () => region.evaluate(scroll => {
      const headers = [...scroll.querySelectorAll('thead th')]
      const inset = getComputedStyle(headers[0]).position === 'sticky' ? headers[0].getBoundingClientRect().width : 0
      const left = scroll.getBoundingClientRect().left + inset
      return headers.slice(1).find(header => Math.abs(header.getBoundingClientRect().left - left) < 1)?.textContent
    })
    const prior = await leading()
    expect(prior).toBeTruthy()
    await page.setViewportSize({ width: profile.width === 1024 ? 768 : 390, height: 1000 })
    await settleTable(page)
    expect(await leading()).toBe(prior)
    await page.evaluate(() => { document.documentElement.style.fontSize = '32px' })
    await settleTable(page)
    expect(await leading()).toBe(prior)
    const pad = await region.evaluate(scroll => scroll.style.paddingInlineEnd)
    await page.evaluate(() => window.dispatchEvent(new Event('resize')))
    await settleTable(page)
    expect(await region.evaluate(scroll => scroll.style.paddingInlineEnd)).toBe(pad)
  })
})

for (const theme of THEMES) for (const state of ['captured', 'edge', 'annual'] as AnalysisGeometryState[]) {
  test.describe(`analysis geometry fixtures / ${theme} / ${state}`, () => {
    test.use({ viewport: { width: 320, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    test('keeps captured and edge-case values whole at enlarged phone text', async ({ page, baseURL }) => {
      test.setTimeout(90_000)
      await openAnalysis(page, baseURL!, state, theme, 2)
      const geometry = await pageAndCardGeometry(page)
      expect(geometry.scrollWidth).toBeLessThanOrEqual(320 + EPSILON)
      expect(geometry.cards).toHaveLength(4)
      for (const card of geometry.cards) expect(card.spills).toEqual([])
      for (const row of geometry.rows) expect(row.values).toBe(1)
      const columns = state === 'annual' ? 11 : 12
      await assertTableGeometry(page, columns)
      const count = await page.locator(`${TABLE} tbody button[aria-label$="View source and calculation"]`).count()
      expect(count).toBeGreaterThanOrEqual(METRICS * (state === 'annual' ? 10 : 12))
      await assertSourceControls(page, `${TABLE} tbody`, count)
      await assertPaintedMarks(page, TABLE)
      if (state === 'annual') {
        await expect(page.getByRole('columnheader', { name: 'FY2016–FY2025 CAGR', exact: true })).toBeAttached()
      }
      if (state === 'edge') {
        await expect(page.locator(`${TABLE} [data-note-letter="aa"]`).first()).toHaveAttribute('data-note-kind', 'review')
        await expect(page.locator(`${TABLE} tbody`)).toContainText('n/m')
        await expect(page.getByRole('rowheader', { name: 'EPS (diluted) CAD per share' })).toBeAttached()
        await expect(page.locator('[data-analysis-kpi]').filter({ hasText: 'Free cash flow' })).toContainText('latest available')
        const fallback = page.getByRole('button', { name: /EPS \(diluted\) \(CAD per share\), Q3 2023:/ }).locator('xpath=ancestor::td')
        await expect(fallback).toContainText('YoY')
        expect(await fallback.getByText('YoY', { exact: true }).evaluate(label => {
          const value = label.nextElementSibling!
          return label.getBoundingClientRect().bottom <= value.getBoundingClientRect().top + 1
        }), 'the fallback basis has its own line above the complete change token').toBe(true)
      }
    })
  })
}

for (const theme of THEMES) test.describe(`analysis heading rail / ${theme}`, () => {
  test.use({ viewport: { width: 1440, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
  test('a figure reached by Shift+Tab lands below the heading rail, never under it', async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, 'legacy', theme, 1)
    const rows = page.locator(`${TABLE} tbody tr`)
    // Put row 8's top just under the site header, past the table's own heading row, so the rail shows over it.
    await rows.nth(8).evaluate(row => {
      const header = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
      window.scrollTo(0, row.getBoundingClientRect().top + window.scrollY - header - 8)
    })
    const rail = page.locator('[data-table-header-rail] > div')
    await expect(rail).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue('--table-rail-h'))).toMatch(/^\d+px$/)
    const covered = await page.evaluate(() => {
      const rail = document.querySelector('[data-table-header-rail] > div')!.getBoundingClientRect()
      const row = document.querySelectorAll('[data-analysis-metrics] table tbody tr')[8].getBoundingClientRect()
      return row.top < rail.bottom
    })
    expect(covered, 'the planted row starts under the rail').toBe(true)
    // A click on the rail, over a figure it covers, opens nothing: the rail lets the pointer through (for wheels and
    // swipes), and the table drops a press or click in the rail's band.
    const point = await page.evaluate(() => {
      const band = document.querySelector('[data-table-header-rail] > div')!.getBoundingClientRect()
      const covered = [...document.querySelectorAll<HTMLElement>('[data-analysis-metrics] tbody button')].map((button) => button.getBoundingClientRect())
        .find((box) => box.top < band.bottom - 2 && box.bottom > band.top + 2 && box.width > 4)!
      const x = covered.left + covered.width / 2
      const y = Math.max(covered.top, band.top) + 1
      return { x, y, under: !!document.elementFromPoint(x, y)?.closest('tbody button') }
    })
    expect(point.under, 'the point lies over a figure the rail covers').toBe(true)
    await page.mouse.click(point.x, point.y)
    await expect(page.getByRole('dialog'), 'a click on the rail opens no hidden figure').toHaveCount(0)
    expect(await page.evaluate(() => !!document.activeElement?.closest('[data-analysis-metrics] tbody')), 'nor focuses it').toBe(false)
    // The press still reaches outside-press listeners: an open header menu closes on a press in the band.
    // Pressed where it is, as a reader would: the locator's own click scrolls a header control "into view" first.
    const bell = page.getByRole('button', { name: 'Notifications', exact: true })
    const bellBox = (await bell.boundingBox())!
    await page.mouse.click(bellBox.x + bellBox.width / 2, bellBox.y + bellBox.height / 2)
    await expect(bell).toHaveAttribute('aria-expanded', 'true')
    const left = await page.evaluate(() => { const band = document.querySelector('[data-table-header-rail] > div')!.getBoundingClientRect(); return { x: band.left + 24, y: band.top + band.height / 2 } })
    await page.mouse.click(left.x, left.y)
    await expect(bell, 'a press in the rail band closes the open menu').toHaveAttribute('aria-expanded', 'false')
    // Tab into the row below, then back up: focus lands on row 8's last figure, which the page must scroll clear.
    await rows.nth(9).locator('button[aria-label$="View source and calculation"]').first().focus()
    await page.keyboard.press('Shift+Tab')
    const focused = page.locator(':focus')
    await expect(focused).toHaveAttribute('aria-label', /View source and calculation$/)
    const place = await focused.evaluate(button => {
      const top = button.getBoundingClientRect().top
      const header = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
      const rail = document.querySelector('[data-table-header-rail] > div')?.getBoundingClientRect().bottom ?? 0
      return { top, clear: Math.max(header, rail) }
    })
    expect(place.top, 'the focused figure clears the site header and the rail').toBeGreaterThanOrEqual(place.clear - 1)
  })

  test('a figure focused while the rail is hidden lands below the band the rail then takes', async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, 'legacy', theme, 1)
    // A last row taller than the heading row, its figure under the site header while the rail is hidden. Chromium
    // centres an obscured focus target, but an engine (or a script) that scrolls it to the nearest edge aligns it to
    // the scroll padding; the rest of the row then brings the rail back, so the padding must already hold the rail.
    const placed = await page.evaluate(() => {
      const table = document.querySelector('[data-analysis-metrics] table')!
      const header = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
      const head = table.querySelector('thead')!.getBoundingClientRect().height
      const row = table.querySelector<HTMLTableRowElement>('tbody tr:last-child')!
      for (const cell of row.cells) cell.style.height = `${header / 2 + head - 4}px`
      // Room below the table to place it, and its bottom 4px inside the heading row's height under the header.
      document.body.style.paddingBottom = '150vh'
      window.scrollTo(0, table.getBoundingClientRect().bottom + window.scrollY - header - head + 4)
      return { rail: !!document.querySelector('[data-table-header-rail] > div'), bottom: table.getBoundingClientRect().bottom - header - head }
    })
    expect(placed.rail, 'the rail is hidden before the focus moves').toBe(false)
    // The reserve follows the scroll a frame later; the focus move waits for it, as a reader's key press would.
    await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue('--table-rail-h'))).toMatch(/^\d+px$/)
    const figure = page.locator(`${TABLE} tbody tr:last-child button[aria-label$="View source and calculation"]`).last()
    await figure.evaluate((button: HTMLElement) => {
      button.focus({ preventScroll: true })
      button.scrollIntoView({ block: 'nearest' })
    })
    await expect(page.locator('[data-table-header-rail] > div'), 'the tall row brings the rail back').toBeVisible()
    await expect.poll(() => figure.evaluate(button => {
      const rail = document.querySelector('[data-table-header-rail] > div')!.getBoundingClientRect().bottom
      return button.getBoundingClientRect().top >= rail - 1
    }), 'the focused figure clears the rail').toBe(true)
  })

  test('a figure focused earlier stays put when the reader scrolls the rail over it', async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, 'legacy', theme, 1)
    const rows = page.locator(`${TABLE} tbody tr`)
    // Focus a figure while the table's own heading row is in view, then scroll with no focus move until the rail
    // covers that figure's row: the page stays where the reader put it.
    await rows.nth(8).locator('button[aria-label$="View source and calculation"]').first().evaluate((button: HTMLElement) => button.focus({ preventScroll: true }))
    await page.waitForTimeout(1200)
    const target = await rows.nth(8).evaluate(row => {
      const header = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
      const y = Math.round(row.getBoundingClientRect().top + window.scrollY - header - 8)
      window.scrollTo(0, y)
      return y
    })
    await expect(page.locator('[data-table-header-rail] > div')).toBeVisible()
    await page.waitForTimeout(300)
    expect(await page.evaluate(() => Math.round(window.scrollY)), 'the page did not jump back to the focused figure').toBe(target)
  })

  test('the landing demo, in a frame that clips overflow, never shows the rail nor reserves its padding', async ({ page }) => {
    test.setTimeout(60_000)
    await page.addInitScript((theme) => {
      localStorage.setItem('theme', theme)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z' }))
    }, theme)
    await page.goto('/')
    const demo = page.locator('[data-capture="multi-period-analysis"]')
    await demo.locator('table').scrollIntoViewIfNeeded()
    // Its heading row just past the header line, the rest of the table below: where the analysis page shows the rail.
    const passed = await demo.locator('table').evaluate(table => {
      const line = parseFloat(getComputedStyle(table.closest('[data-capture]')!.querySelector('[data-table-header-rail]')!).top)
      window.scrollTo(0, table.querySelector('thead')!.getBoundingClientRect().top + window.scrollY - line + 12)
      const head = table.querySelector('thead')!.getBoundingClientRect()
      return head.top < line && table.getBoundingClientRect().bottom > line + head.height
    })
    expect(passed, 'the demo table sits where a page rail would show').toBe(true)
    await page.waitForTimeout(200)
    await expect(demo.locator('[data-table-header-rail] > div')).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.style.getPropertyValue('--table-rail-h'))).toBe('')
  })
})

test.describe('analysis heading rail / 1024px', () => {
  test.use({ viewport: { width: 1024, height: 800 }, reducedMotion: 'reduce', serviceWorkers: 'block' })
  test('a horizontal wheel over the rail still moves the table under it', async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, 'legacy', 'light', 1)
    const scroller = page.locator(`${TABLE}`).locator('xpath=ancestor::*[@role="region"][1]')
    expect(await scroller.evaluate(el => el.scrollWidth > el.clientWidth + 1), 'the table overflows at 1024px').toBe(true)
    await page.locator(`${TABLE} tbody tr`).nth(8).evaluate(row => {
      const header = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
      window.scrollTo(0, row.getBoundingClientRect().top + window.scrollY - header - 8)
    })
    const rail = page.locator('[data-table-header-rail] > div')
    await expect(rail).toBeVisible()
    const band = (await rail.boundingBox())!
    const before = await scroller.evaluate(el => el.scrollLeft)
    await page.mouse.move(band.x + band.width * 0.6, band.y + band.height / 2)
    await page.mouse.wheel(before > 0 ? -400 : 400, 0)
    await expect.poll(() => scroller.evaluate(el => el.scrollLeft), 'the wheel reached the table through the rail').not.toBe(before)
  })
})

/** Three whole periods beside the metric names on a phone, 375px included: the 2px each mark keeps grew a phone column to
 *  4.375rem, so below md, in the band where that cost the third period, the metric column gives up to 6px (MetricsTable).
 *  A period counts only inside the scroll box and beside a label that is itself in view, so an unstuck label column
 *  cannot pass it with the columns scrolled off to the left. */
for (const width of [375, 390]) test.describe(`analysis table periods / ${width}px`, () => {
  test.use({ viewport: { width, height: 812 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce', serviceWorkers: 'block' })
  test('three whole periods sit beside the metric names at rest', async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, 'legacy', 'light', 1)
    const table = page.locator(TABLE)
    await expect.poll(() => table.evaluate(element => {
      const region = element.closest('[role="region"]')!
      const box = region.getBoundingClientRect()
      const heads = [...element.querySelectorAll('thead th')].map(th => th.getBoundingClientRect())
      const label = heads[0]
      if (label.left < box.left - 0.5 || label.right > box.right + 0.5) return -1
      return heads.slice(1).filter(r => r.left >= label.right - 0.5 && r.left >= box.left - 0.5 && r.right <= box.right + 0.5).length
    }), 'whole period columns beside the metric names in view').toBeGreaterThanOrEqual(3)
  })
})

/** The band stops at md. At 200% text an 816px screen's card has a 19.4375rem content box, inside the band, and there it
 *  would cut the 8.25rem metric column to about 5.2rem, too narrow for its names (MetricsTable). */
test.describe('analysis table periods / 816px at 200% text', () => {
  test.use({ viewport: { width: 816, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })
  test('md keeps its full metric column where a phone would give up 6px', async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, 'legacy', 'light', 2)
    const geometry = await page.locator(TABLE).evaluate(element => {
      const root = parseFloat(getComputedStyle(document.documentElement).fontSize)
      const card = element.closest('[class~="[container-type:inline-size]"]') as HTMLElement
      const style = getComputedStyle(card)
      const content = (card.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)) / root
      const metric = element.querySelector('thead th')!.getBoundingClientRect().width / root
      const overflowing = [...element.querySelectorAll('tbody th')].filter(th => th.scrollWidth > th.clientWidth + 1).length
      return { root, content, metric, overflowing }
    })
    expect(geometry.root, 'the text is at 200%').toBeCloseTo(32, 1)
    expect(geometry.content, 'the card\'s content box sits in the band').toBeGreaterThanOrEqual(19.25)
    expect(geometry.content, 'the card\'s content box sits in the band').toBeLessThan(19.625)
    expect(geometry.metric, 'the metric column, in rem').toBeCloseTo(8.25, 2)
    expect(geometry.overflowing, 'metric names wider than their cells').toBe(0)
  })
})

// At 360px the KPI strip carries a code-prefixed calculated value, "CA$968.0M†", whose dagger wrapped below it two up
// (E197); the fixtures' dollar values fit there.
for (const theme of THEMES) for (const width of [390, 360] as const) test.describe(`analysis phone marks / ${theme}${width === 360 ? ' / 360px' : ''}`, () => {
  test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
  for (const state of ['legacy', 'edge'] as const) test(`${state}: a figure's marks share its line and its cell at ${width}px, in the figure face`, async ({ page, baseURL }) => {
    test.setTimeout(60_000)
    await openAnalysis(page, baseURL!, state, theme, 1, false, width === 360 ? withCanadianFreeCashFlow : undefined)
    if (width === 360) await expect(page.locator('[data-analysis-kpi] button').filter({ hasText: /^CA\$968\.0M†/ })).toHaveCount(1)
    expect(await page.evaluate(async () => { await document.fonts.ready; return document.fonts.check('12px "EN Figure Minus"', '-') }), 'the minus face draws the hyphen-minus').toBe(true)
    // The stylesheet the build emits (E199): the data face falls back to a monospace one, with no metric-matched Arial.
    const mono = await page.evaluate(() => ({
      stack: getComputedStyle(document.documentElement).getPropertyValue('--font-geist-mono').trim(),
      metricFallback: [...document.fonts].some(face => face.family.replace(/["']/g, '') === 'Geist Mono Fallback'),
    }))
    expect(mono.stack, 'the data face falls back to a monospace one').toMatch(/^["']Geist Mono["'],\s*ui-monospace,\s*SFMono-Regular,\s*Menlo,\s*monospace$/)
    expect(mono.metricFallback, 'no metric-matched Arial face for Geist Mono').toBe(false)
    const selector = `[data-analysis-kpi] button[aria-label$="View source and calculation"], ${TABLE} tbody button[aria-label$="View source and calculation"]`
    const controls = await page.locator(selector).evaluateAll(buttons => buttons.map(button => {
      const cell = button.closest('td, [data-analysis-kpi]')!
      const style = getComputedStyle(cell)
      const box = cell.getBoundingClientRect()
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize)
      const glyphs: Array<{ mark: string | null; display: string; left: number; right: number; top: number; bottom: number }> = []
      let face = ''
      const walker = document.createTreeWalker(button, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const parent = node.parentElement!
        if (!node.textContent?.trim() || parent.closest('.sr-only')) continue
        const range = document.createRange(); range.selectNodeContents(node)
        const mark = parent.closest('[data-note-letter]') ? 'letter' : node.textContent.trim() === '†' ? 'dagger' : null
        if (!mark && !face) face = `${getComputedStyle(parent).fontFamily}|${getComputedStyle(parent).fontVariantNumeric}`
        const display = getComputedStyle(parent).display
        for (const r of range.getClientRects()) if (r.width && r.height) glyphs.push({ mark, display, left: r.left, right: r.right, top: r.top, bottom: r.bottom })
      }
      return {
        name: button.getAttribute('aria-label')!, text: button.textContent!, table: cell.tagName === 'TD', face, rem,
        underlined: getComputedStyle(button).textDecorationLine.includes('underline'),
        left: box.left + parseFloat(style.paddingLeft), right: box.right - parseFloat(style.paddingRight), glyphs,
      }
    }))
    expect(controls.filter(control => control.table).length).toBeGreaterThanOrEqual(METRICS * 10)
    expect(controls.filter(control => !control.table)).toHaveLength(4)
    const problems: string[] = []
    for (const control of controls) {
      const figure = control.glyphs.filter(glyph => !glyph.mark)
      const [family, numeric] = control.face.split('|')
      if (figure.length && (!family.startsWith('"EN Figure Minus"') || !/tabular-nums/.test(numeric) || !/lining-nums/.test(numeric))) problems.push(`${control.name}: not in the figure face (${control.face})`)
      if (new Set(figure.map(glyph => Math.round(glyph.top))).size > 1) problems.push(`${control.name}: the figure wraps`)
      const line = figure[0]
      const end = figure.at(-1)?.right ?? -Infinity
      const marks = control.glyphs.filter(glyph => glyph.mark)
      for (const [index, mark] of marks.entries()) {
        if (line && (mark.top > line.bottom || mark.bottom < line.top)) problems.push(`${control.name}: a mark left the figure's line`)
        if (mark.left < end - 1) problems.push(`${control.name}: a mark sits before the figure's end`)
        // The first mark keeps 2px from its figure: set flush, readers dropped "$4.1B†a"'s dagger at 1x in dark.
        if (index === 0 && figure.length && mark.left - end < 0.125 * control.rem - 0.5) problems.push(`${control.name}: a mark touches its figure`)
        // A letter after † keeps 2px (0.125rem): set flush, the pair read as one glyph at 1x (the study's readout).
        if (mark.mark === 'letter' && marks[index - 1]?.mark === 'dagger' && mark.left - marks[index - 1].right < 0.125 * control.rem - 0.5) problems.push(`${control.name}: a letter touches its dagger`)
        // A staircase: a letter after † stands above it. Level, "†a" read as one mark at 1x in dark (the readout).
        if (mark.mark === 'letter' && marks[index - 1]?.mark === 'dagger' && mark.top > marks[index - 1].top - 1) problems.push(`${control.name}: a letter is not above its dagger`)
        // The control's dotted underline skips an inline-block, but a flex item is blockified (display: block) and the
        // underline reaches it, drawn again under the mark at its raised baseline.
        if (control.underlined && mark.display !== 'inline-block') problems.push(`${control.name}: a ${mark.mark} is a ${mark.display} box under the control's underline`)
      }
      // The table's figures carry no underline: under every value it parted values from their change lines, and readers
      // gave a period with no change the next column's (the readout, dark at 1x). The KPI value keeps its.
      if (control.table === control.underlined) problems.push(`${control.name}: ${control.table ? 'a table figure is underlined' : 'the KPI value lost its underline'}`)
      if (control.table) for (const glyph of control.glyphs) if (glyph.left < control.left - 1 || glyph.right > control.right + 1) problems.push(`${control.name}: ${glyph.mark ? 'a mark' : 'the figure'} leaves its cell`)
    }
    expect(problems).toEqual([])
    expect(controls.some(control => control.glyphs.some((glyph, index, all) => glyph.mark === 'letter' && all[index - 1]?.mark === 'dagger')), 'a dagger and a letter are measured together').toBe(true)
    // A change line's letter keeps 2px from its change too. The change sits outside the figure's source button, so it is
    // measured from its own line: the change's glyphs (n/m's visible abbreviation included), then the letter.
    const changeLines = await page.locator(`${TABLE} tbody td`).evaluateAll(cells => cells.flatMap(cell => [...cell.querySelectorAll('[data-note-letter]')]
      .filter(mark => !mark.closest('button'))
      .map(mark => {
        const line = mark.parentElement!
        const rem = parseFloat(getComputedStyle(document.documentElement).fontSize)
        const glyphs: Array<{ mark: boolean; left: number; right: number }> = []
        const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT)
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          const parent = node.parentElement!
          if (!node.textContent?.trim() || parent.closest('.sr-only')) continue
          const range = document.createRange(); range.selectNodeContents(node)
          for (const r of range.getClientRects()) if (r.width && r.height) glyphs.push({ mark: !!parent.closest('[data-note-letter]'), left: r.left, right: r.right })
        }
        const style = getComputedStyle(cell)
        const box = cell.getBoundingClientRect()
        return { name: `${cell.closest('tr')?.querySelector('th')?.textContent?.trim()} · ${line.textContent?.trim()}`, rem, glyphs, left: box.left + parseFloat(style.paddingLeft), right: box.right - parseFloat(style.paddingRight) }
      })))
    const changeProblems: string[] = []
    for (const line of changeLines) {
      const end = Math.max(...line.glyphs.filter(glyph => !glyph.mark).map(glyph => glyph.right))
      const first = line.glyphs.find(glyph => glyph.mark)!
      if (first.left - end < 0.125 * line.rem - 0.5) changeProblems.push(`${line.name}: a change line's letter touches its change`)
      // Right-justified, a line too wide for its cell runs out at the left.
      if (line.glyphs.some(glyph => glyph.left < line.left - 1 || glyph.right > line.right + 1)) changeProblems.push(`${line.name}: a change line leaves its cell`)
    }
    expect(changeProblems).toEqual([])
    expect(changeLines.length, 'a change line with a letter is measured').toBeGreaterThan(0)
    if (state === 'edge') {
      // The planted figures fill their column's whole budget with their marks (nine glyphs: the figure, the dagger and
      // a two-letter note), the sign the ASCII hyphen-minus.
      for (const [name, figure] of [[/^Working capital, Q4 2023: /, '$92.2M'], [/^Financing cash flow, Q4 2025: /, '-$922M']] as const) {
        const control = controls.find(item => name.test(item.name))
        expect(control?.text, `${name}`).toMatch(new RegExp(`^${figure.replace(/[$.]/g, '\\$&')}†[a-z]{2}$`))
      }
      expect(controls.map(control => control.text).join('')).not.toContain('−')
      // n/m stays visible and is read as words.
      const tbody = page.locator(`${TABLE} tbody`)
      await expect(tbody.getByText('n/m', { exact: true }).first()).toHaveAttribute('aria-hidden', 'true')
      await expect(tbody.getByText('not meaningful', { exact: true }).first()).toHaveClass(/\bsr-only\b/)
    }
  })
})

/** Every amount in Swiss francs: a currency code makes the longest tick labels ("CHF 150B"). */
const inSwissFrancs = (dataset: AnalysisDataset) => {
  for (const series of dataset.series) if (!series.percent) {
    series.unit = 'CHF'
    for (const point of series.points) point.unit = 'CHF'
  }
}

/** Canadian Pacific's quarterly free cash flow on the latest point the series has: "CA$968.0M†", calculated. */
const withCanadianFreeCashFlow = (dataset: AnalysisDataset) => {
  const series = dataset.series.find(item => item.concept === 'free_cash_flow')!
  series.unit = 'CAD'
  for (const point of series.points) point.unit = 'CAD'
  series.points.findLast(point => point.value != null)!.value = 968_000_000
}

/** E197: a code-prefixed value that two cards cannot hold puts the strip in one column instead of leaving its card
 *  ("CHF 22.8B†" ran 18px past it at 320px) or wrapping its dagger ("CA$968.0M†" at 360px); from 375px both fit two up,
 *  and under 200% text from lg the strip takes two cards where four cannot hold them. */
// Geometry only, so one theme: the inks are the phone marks' and the text floors' to check.
test.describe('analysis KPI strip, long values', () => {
  const theme = 'light' as const
  for (const [name, state, edit, value] of [
    ['annual in CHF', 'annual', inSwissFrancs, 'CHF\u00a022.8B'], ['quarterly in CA$', 'legacy', withCanadianFreeCashFlow, 'CA$968.0M'],
  ] as const) for (const [width, textScale, columns] of [[320, 1, 1], [360, 1, 1], [375, 1, 2], [390, 1, 2], [1024, 2, 2], [1480, 2, 2]] as const) {
    test.describe(`${name} at ${width}px${textScale > 1 ? ' and 200% text' : ''}`, () => {
      test.use({ viewport: { width, height: 900 }, isMobile: width <= 390, hasTouch: width <= 390, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
      test(`its widest value stays in its card on one line, ${columns === 1 ? 'one card' : 'two cards'} across`, async ({ page, baseURL }) => {
        test.setTimeout(60_000)
        await openAnalysis(page, baseURL!, state, theme, textScale, false, edit)
        await expect(page.locator('[data-analysis-kpi] [data-kpi-value] button').filter({ hasText: value }).first()).toBeVisible()
        const geometry = await pageAndCardGeometry(page)
        await assertKpiStrip(page, width, geometry)
        expect(geometry.rows[0].values, 'cards across').toBe(columns)
      })
    })
  }
  test.describe('a text size set after the strip mounts', () => {
    test.use({ viewport: { width: 390, height: 900 }, isMobile: true, hasTouch: true, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    // The probes are measured again whenever they resize (KpiStrip's ResizeObserver), so a text size changed after the
    // strip mounts gives it advances at that size; measured once, the budget would keep the old size's pixels.
    test('measures its advances again, and its budget stays the widest value as painted', async ({ page, baseURL }) => {
      test.setTimeout(60_000)
      await openAnalysis(page, baseURL!, 'legacy', theme, 1)
      const advance = () => page.locator('[data-analysis-kpi]').first().evaluate(card => parseFloat(card.closest('dl')!.style.getPropertyValue('--kpi-figure')))
      const before = await advance()
      expect(before, 'the strip measured its advance').toBeGreaterThan(0)
      await page.evaluate(async () => {
        document.documentElement.style.fontSize = '32px'
        await document.fonts.ready
        await new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))
      })
      await expect.poll(advance, { message: 'the advance at a 32px root' }).toBeGreaterThan(1.9 * before)
      const geometry = await pageAndCardGeometry(page)
      expect(geometry.rootFontSize).toBe(32)
      await assertKpiStrip(page, 390, geometry)
    })
  })
  test.describe('the figure face', () => {
    test.use({ viewport: { width: 390, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    // kpiValueGlyphs counts ASCII and KPI_FACE_GLYPHS at the face's one advance, which the strip measures as painted
    // (0.6em, or whole pixels where the browser snaps glyphs), and anything else at 1.25em. Each glyph is measured in
    // the value's own faces with a serif after them, not the monospace fallback, so a glyph Geist Mono lacks cannot pass
    // at a fallback's advance; KPI_MISSING_GLYPHS shows the probe tells the two apart.
    test('draws ASCII and every glyph the width counts as its own at the one advance the strip measures', async ({ page, baseURL }) => {
      test.setTimeout(60_000)
      await openAnalysis(page, baseURL!, 'annual', theme, 1)
      const ascii = Array.from({ length: 95 }, (_, index) => String.fromCharCode(32 + index)).join('')
      const measure = (glyphs: string) => page.locator('[data-analysis-kpi] [data-kpi-value]').first().evaluate(async (value, glyphs) => {
        const style = getComputedStyle(value)
        const faces = '"EN Figure Minus", "Geist Mono"'
        await document.fonts.load(`${style.fontWeight} ${style.fontSize} ${faces}`, glyphs)
        await document.fonts.ready
        const probe = value.appendChild(document.createElement('span'))
        probe.style.cssText = `position:absolute;white-space:pre;font-family:${faces},serif`
        const measured = [...glyphs].map(glyph => {
          probe.textContent = glyph.repeat(10)
          return { glyph: `U+${glyph.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')}`, px: Math.round(probe.getBoundingClientRect().width / 10 * 1000) / 1000 }
        })
        probe.remove()
        const strip = value.closest('dl')!
        return { size: parseFloat(style.fontSize), advance: parseFloat(strip.style.getPropertyValue('--kpi-figure')), measured }
      }, glyphs)
      const own = await measure(ascii + KPI_FACE_GLYPHS)
      expect(own.measured).toHaveLength(95 + [...KPI_FACE_GLYPHS].length)
      // The strip measured its advance, within a pixel's rounding of the face's 0.6em.
      expect(Math.abs(own.advance - 0.6 * own.size), `the strip's advance (${own.advance}px) at ${own.size}px`).toBeLessThanOrEqual(0.5)
      expect(own.measured.filter(({ px }) => Math.abs(px - own.advance) > 0.01), `glyphs the width counts at the strip's advance (${own.advance}px), off it`).toEqual([])
      // The control depends on the fallback: where glyphs snap, a serif glyph within half a pixel of the advance would
      // round to it. Liberation Serif's ₩ (1em) and ₫ (0.51em) and Chromium's 0.3em narrow space are far from it.
      const missing = await measure(KPI_MISSING_GLYPHS)
      expect(missing.measured.filter(({ px }) => Math.abs(px - own.advance) <= 0.01), 'glyphs Geist Mono lacks, measured at its advance').toEqual([])
    })
  })
})

for (const theme of THEMES) {
  test.describe(`analysis chart axes / ${theme}`, () => {
    test.use({ viewport: { width: 1280, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    // TrendCharts sizes each value axis from its tick labels. A label wider than its axis runs into the chart's margin
    // (8 px left, 16 px right) and then out of the SVG, where it is cut; one Recharts breaks at a space reads as two.
    // Wider axes must not make a chart at its card's full desktop width scroll. The spec renderer sets each label 8 px
    // left of its plot, from a gutter sized to its widest label (D5). It scrolls a chart only where the plan is wider
    // than its card (M6), and these plans fit a desktop card.
    for (const [name, state, edit] of [
      ['quarterly', 'captured', undefined], ['quarterly in CHF', 'captured', inSwissFrancs], ['annual in CHF', 'annual', inSwissFrancs],
    ] as const) {
      test(`${name}: every y tick label is painted on one line inside its axis, and no chart scrolls`, async ({ page, baseURL }) => {
        await openAnalysis(page, baseURL!, state, theme, 1, false, edit)
        const charts = await (await drawnCharts(page)).evaluateAll(readAxes, CHARTS_V2)
        for (const chart of charts) {
          expect(chart.labels.length, `${chart.name}: its y ticks are drawn`).toBeGreaterThan(2)
          expect(chart.outside, `${chart.name}: y tick labels outside their axis`).toEqual([])
          expect(chart.broken, `${chart.name}: y tick labels drawn on more than one line`).toEqual([])
          expect(chart.scrolls, `${chart.name}: scrolls at its card's full width`).toBe(false)
        }
        if (edit) expect(charts.flatMap(chart => chart.labels).some(label => /^CHF\s\d{3}B$/.test(label)), 'a code-prefixed label is drawn').toBe(true)
      })
    }
  })
}

for (const theme of THEMES) {
  test.describe(`analysis chart quarters / ${theme} / 390px`, () => {
    test.use({ viewport: { width: 390, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    // On a phone a quarterly plot keeps 28 px a quarter past its axes (the spec renderer MIN_SLOT's 36), however wide
    // they are, and scrolls inside its card.
    for (const [name, edit] of [['dollars', undefined], ['Swiss francs', inSwissFrancs]] as const) {
      test(`quarterly in ${name}: each quarter keeps its slot, and the chart scrolls inside its card`, async ({ page, baseURL }) => {
        await openAnalysis(page, baseURL!, 'captured', theme, 1, false, edit)
        const charts = await (await drawnCharts(page)).evaluateAll(readSlots, { v2: CHARTS_V2, periods: PERIODS.length })
        for (const chart of charts) {
          // Recharts keeps 28 px a quarter; the spec renderer's slot is at least MIN_SLOT (M6).
          expect(chart.ticks, `${chart.name}: a printed tick a quarter`).toBe(PERIODS.length)
          expect(chart.slot, `${chart.name}: px a quarter`).toBeGreaterThanOrEqual((CHARTS_V2 ? MIN_SLOT : 28) - 0.01)
          expect(chart.scrolls, `${chart.name}: scrolls inside its card`).toBe(true)
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways').toBe(true)
      })
    }
  })
}

for (const theme of THEMES) for (const width of [390, 1480]) {
  test.describe(`analysis chart notes / ${theme} / ${width}px`, () => {
    test.use({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    test('keeps filled bars and legible notes with named keyboard values and scrolling', async ({ page, baseURL }, testInfo) => {
      test.skip(CHARTS_V2, 'Today’s Recharts keyboard and notes contract: charts-v2.spec.ts holds the spec renderer’s (D13), and step 7 (E195) retires this case.')
      test.setTimeout(60_000)
      await openAnalysis(page, baseURL!, 'discrepancy', theme)
      const plots = page.locator('[data-analysis-chart]')
      await expect(plots).toHaveCount(4)
      const assertViewport = async () => {
        for (const viewport of await page.locator('[data-analysis-chart-scroll]').all()) {
          const overflow = await viewport.evaluate(element => element.scrollWidth > element.clientWidth + 1)
          if (overflow) {
            await expect(viewport).toHaveAttribute('role', 'region')
            await expect(viewport).toHaveAttribute('tabindex', '0')
            await expect(viewport).toHaveAccessibleName(/chart\. Scroll horizontally to view all periods\./)
          } else {
            await expect(viewport).not.toHaveAttribute('role')
            await expect(viewport).not.toHaveAttribute('tabindex')
          }
          const values = viewport.getByRole('application', { name: /chart values\. Use Left and Right arrows to inspect periods\./ })
          await expect(values).toHaveCount(1)
          await expect(values).toHaveAttribute('tabindex', '0')
          expect(await viewport.locator('[tabindex]').evaluateAll(elements =>
            elements.filter(element => (element as HTMLElement).tabIndex >= 0).length
          ), 'each chart has one named value-navigation stop').toBe(1)
          // Start before the chart and enter with a real Tab. Programmatic focus after a
          // pointer download deliberately does not acquire the browser's :focus-visible.
          await viewport.locator('xpath=ancestor::section[1]').getByRole('button', { name: /^(Expand|Collapse) chart$/ }).focus()
          await page.keyboard.press('Tab')
          if (overflow) {
            await expect(viewport).toBeFocused()
            await page.keyboard.press('Tab')
          }
          await expect(values).toBeFocused()
          expect(await viewport.evaluate(element => getComputedStyle(element).boxShadow)).not.toBe('none')
          await page.keyboard.press('Tab')
          expect(await page.evaluate(() => document.activeElement?.closest('[data-analysis-chart-scroll]'))).toBeNull()
          await page.keyboard.press('Shift+Tab')
          await expect(values).toBeFocused()
          if (overflow) {
            await page.keyboard.press('Shift+Tab')
            await expect(viewport).toBeFocused()
          }
        }
      }
      await assertViewport()
      const revenue = plots.first()
      const viewport = revenue.locator('..')
      const allBars = revenue.locator(RECHARTS.bars)
      await expect(allBars).toHaveCount(12)
      const revenueValues = revenue.getByRole('application', { name: 'Revenue & growth chart values. Use Left and Right arrows to inspect periods.' })
      await revenueValues.focus()
      const tooltip = revenue.locator(RECHARTS.tooltip).getByRole('status')
      const settleViewport = async () => {
        const settled = await viewport.evaluate(async element => {
          let previous = element.scrollLeft
          let stable = 0
          for (let frame = 0; frame < 90 && stable < 5; frame++) {
            await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
            stable = Math.abs(element.scrollLeft - previous) < 0.1 ? stable + 1 : 0
            previous = element.scrollLeft
          }
          return stable >= 5
        })
        expect(settled, 'keyboard scrolling settles before checking the selected period').toBe(true)
      }
      const assertPeriodVisible = async (index: number) => {
        await expect(tooltip).toContainText(PERIODS[index].replace(/^(\d{4})(Q\d)$/, '$2 $1'))
        await settleViewport()
        // DOM text alone does not prove keyboard access: the selected mark and its tooltip
        // must remain inside the horizontal viewport in both directions and after re-entry.
        await expect.poll(async () => {
          const [frame, tip, bar] = await Promise.all([viewport.boundingBox(), tooltip.boundingBox(), allBars.nth(index).boundingBox()])
          if (!frame || !tip || !bar) return Number.POSITIVE_INFINITY
          return Math.max(frame.x - tip.x, tip.x + tip.width - frame.x - frame.width,
            frame.x - bar.x, bar.x + bar.width - frame.x - frame.width)
        }, { message: `${PERIODS[index]} value and tooltip stay inside the chart viewport` }).toBeLessThanOrEqual(EPSILON)
      }
      for (let index = 1; index < PERIODS.length; index++) {
        await page.keyboard.press('ArrowRight')
        await assertPeriodVisible(index)
      }
      await expect(tooltip).toContainText('Q2 2026')
      await expect(tooltip).toContainText('YoY growth')
      await expect(tooltip).toContainText('28.0%')
      // The quarterly metrics table uses QoQ here; these YoY values need the chart's own path.
      // Leave at the newest period, then return after the outer viewport has moved. Recharts
      // retains its index on blur; the next arrow must reveal the expected adjacent period.
      await page.keyboard.press('Tab')
      if (width === 390) {
        await viewport.evaluate(element => { element.scrollLeft = 24 })
        expect(await viewport.evaluate(element => element.scrollLeft)).toBeGreaterThan(0)
      }
      await page.keyboard.press('Shift+Tab')
      await expect(revenueValues).toBeFocused()
      for (let index = PERIODS.length - 2; index >= 0; index--) {
        await page.keyboard.press('ArrowLeft')
        await assertPeriodVisible(index)
        if (index === PERIODS.length - 2) await expect(tooltip).toContainText('33.1%')
      }
      // Moving the pointer does not blur the SVG. Hover a different period near a clipped
      // edge, then return to the retained keyboard index without moving the pointer away.
      const hover = await viewport.evaluate((element, bars) => {
        const bar = element.querySelectorAll(bars)[8]
        const frame = element.getBoundingClientRect()
        if (element.scrollWidth > element.clientWidth + 1) {
          const before = bar.getBoundingClientRect()
          const centerInContent = before.x + before.width / 2 - frame.x + element.scrollLeft
          element.scrollLeft = centerInContent - element.clientWidth + 4
        }
        const target = bar.getBoundingClientRect()
        return { x: target.x + target.width / 2, y: frame.y + 80, left: element.scrollLeft }
      }, RECHARTS.bars)
      await page.mouse.move(hover.x, hover.y)
      await expect(revenueValues).toBeFocused()
      await expect(tooltip).toContainText('Q3 2025')
      await settleViewport()
      expect(Math.abs(await viewport.evaluate(element => element.scrollLeft) - hover.left),
        'pointer inspection cannot scroll a still-focused chart').toBeLessThanOrEqual(EPSILON)
      await page.keyboard.press('ArrowRight')
      await assertPeriodVisible(1)
      await page.keyboard.press('ArrowLeft')
      await assertPeriodVisible(0)
      const cleanFill = await allBars.first().getAttribute('fill')
      const affectedBar = revenue.locator('g[aria-label="Data note a"] path')
      await expect(affectedBar).toHaveCount(1)
      await expect(affectedBar).toHaveAttribute('fill', cleanFill!)
      await expect(affectedBar).not.toHaveAttribute('stroke-dasharray')
      const letters = page.locator('[data-analysis-chart] g[aria-label^="Data note "] text')
      expect(await letters.count()).toBeGreaterThan(0)
      const panel = await revenue.evaluate(element => getComputedStyle(element.closest('section')!).backgroundColor)
      for (const letter of await letters.all()) {
        await expect(letter).toHaveAttribute('stroke-width', '3')
        await expect(letter).toHaveAttribute('paint-order', 'stroke')
        expect(await letter.evaluate(element => getComputedStyle(element).stroke)).toBe(panel)
        expect(await letter.evaluate(element => {
          const bounds = (element as SVGGraphicsElement).getBBox()
          return bounds.width > 0 && bounds.height > 0 && getComputedStyle(element).fill !== 'none'
        })).toBe(true)
      }
      if (width === 390) {
        await viewport.focus()
        await page.keyboard.press('ArrowRight')
        await expect.poll(() => viewport.evaluate(element => element.scrollLeft)).toBeGreaterThan(0)
      }
      const downloadPromise = page.waitForEvent('download')
      await revenue.locator('xpath=ancestor::section[1]').getByRole('button', { name: 'Download chart as PNG' }).click()
      const download = await downloadPromise
      expect(download.suggestedFilename()).toMatch(/\.png$/)
      await download.saveAs(testInfo.outputPath(`revenue-notes-${theme}-${width}.png`))
      await page.setViewportSize({ width: width === 390 ? 1480 : 390, height: 1000 })
      await expect.poll(() => viewport.evaluate(element => element.hasAttribute('tabindex'))).toBe(width !== 390)
      await assertViewport()
    })
  })
}

for (const theme of THEMES) for (const width of [320, 390, 1480]) for (const textScale of [1, 2]) {
  test.describe(`analysis period controls / ${theme} / ${width}px / ${textScale * 100}% text`, () => {
    test.use({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    test('keeps range changes readable and explains unavailable modes in the Tab order', async ({ page, baseURL }) => {
      await openAnalysis(page, baseURL!, 'clean', theme, textScale)
      const from = page.getByRole('combobox', { name: 'From', exact: true })
      const to = page.getByRole('combobox', { name: 'To', exact: true })
      await from.selectOption('2022Q1')
      await expect(to).toHaveValue('2024Q4')
      await expect(page.getByRole('status').filter({ hasText: 'To moved' })).toHaveText('To moved to Q4 2024 to keep at most 12 quarters.')
      await expect(page.getByText('Q1 2022–Q4 2024 · 12 quarters', { exact: true })).toBeVisible()
      for (const select of [from, to]) {
        const geometry = await select.evaluate((element) => {
          const field = element as HTMLSelectElement
          const style = getComputedStyle(field)
          const box = field.getBoundingClientRect()
          const canvas = document.createElement('canvas')
          const context = canvas.getContext('2d')!
          context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
          return { left: box.left, right: box.right, font: style.fontFamily, available: field.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight), selectedWidth: context.measureText(field.selectedOptions[0].text).width }
        })
        expect(geometry.font).toMatch(/geist.?mono/i)
        expect(geometry.left).toBeGreaterThanOrEqual(0)
        expect(geometry.right).toBeLessThanOrEqual(width + EPSILON)
        expect(geometry.selectedWidth, 'the full selected period token fits beside the native chevron').toBeLessThanOrEqual(geometry.available + EPSILON)
      }
      for (const preset of await page.getByRole('group', { name: 'Recent period presets' }).getByRole('button').all()) {
        await expect(preset).not.toHaveAttribute('aria-pressed')
      }
      await page.route('**/api/analysis/META/coverage', route => route.fulfill({ json: {
        ticker: 'META', company_name: 'Meta Platforms, Inc.', supported: true, reason: null, syncing: false, synced_at: null,
        limits: { annual: 10, quarterly: 12 },
        annual: [{ key: 'FY2025', fiscal_year: 2025, period_end: '2025-12-31', has_core: true }], quarterly: [],
      }, headers: { 'access-control-allow-origin': new URL(baseURL!).origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,OPTIONS' } }))
      await page.reload()
      const annual = page.getByRole('button', { name: 'Annual', exact: true })
      const quarterly = page.getByRole('button', { name: 'Quarterly', exact: true })
      await expect(quarterly).toHaveAttribute('aria-disabled', 'true')
      await expect(quarterly).toHaveJSProperty('disabled', false)
      await expect(quarterly).toHaveAccessibleDescription("Quarterly data isn't available for this company.")
      await annual.focus()
      await page.keyboard.press('Tab')
      await expect(quarterly).toBeFocused()
      await page.keyboard.press('Enter')
      await page.keyboard.press('Space')
      await expect(annual).toHaveAttribute('aria-pressed', 'true')
      const focus = await quarterly.evaluate(element => ({ opacity: getComputedStyle(element).opacity, shadow: getComputedStyle(element).boxShadow }))
      expect(focus.opacity).toBe('1')
      expect(focus.shadow).not.toBe('none')
    })
  })
}
