import { expect, test, type Page } from '@playwright/test'
import { EXPECTED_KPI_LETTERS, EXPECTED_KPI_VALUES, EXPECTED_NOTES, EXPECTED_TABLE_CELL_NOTES, EXPECTED_TABLE_COMPARISON_REVIEWS, EXPECTED_TABLE_REVIEWS, EXPECTED_TABLE_VALUE_DAGGERS, METRICS, PERIODS, UNAVAILABLE_CELLS, openAnalysis, type AnalysisState, type AnalysisTheme, type AnalysisGeometryState } from './fixtures/analysisLayoutApi'

/**
 * The one browser geometry gate for the analysis redesign (proposal Phase 1, item 10).
 * It exercises production React components and actual text ranges, not copies of CSS
 * or unit-test geometry. No backend, AI, stored credentials or new Playwright config.
 *
 * In particular, window.innerWidth is NOT an overflow oracle: mobile Chromium can
 * expand it to the overflowing document. Compare scrollWidth with document.clientWidth
 * AND the configured viewport. Off-screen sr-only text still counts in that check.
 * 200% text changes root font size; 200% zoom is explicitly viewport/DPR emulation.
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
      return { index, top: box.top, valueTop: value ? bounds(value).top : null, spills }
    })
    const rows: Array<{ top: number; valueTops: number[] }> = []
    for (const card of cards) {
      let row = rows.find(row => Math.abs(row.top - card.top) < 1)
      if (!row) { row = { top: card.top, valueTops: [] }; rows.push(row) }
      if (card.valueTop !== null) row.valueTops.push(card.valueTop)
    }
    return {
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      kpiWidth: document.querySelector('[data-analysis-kpi]')!.parentElement!.getBoundingClientRect().width,
      rootFontSize: parseFloat(getComputedStyle(document.documentElement).fontSize),
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
  await assertSourceControls(page, '[data-analysis-kpi]', 4)
  expect(geometry.scrollWidth, 'document must fit its layout viewport (including invisible positioned boxes)').toBeLessThanOrEqual(geometry.clientWidth + EPSILON)
  expect(geometry.scrollWidth, 'document must fit the configured viewport, even when innerWidth expands').toBeLessThanOrEqual(width + EPSILON)
  expect(geometry.clientWidth).toBeLessThanOrEqual(width)
  expect(geometry.rootFontSize).toBeCloseTo(16 * textScale, 1)
  expect(geometry.cards).toHaveLength(4)
  for (const card of geometry.cards) {
    expect(card.valueTop, `KPI ${card.index} has a measured value`).not.toBeNull()
    expect(card.spills, `KPI ${card.index} child/text containment`).toEqual([])
  }
  expect(geometry.rows.length).toBeGreaterThan(0)
  const columns = geometry.kpiWidth < 17 * geometry.rootFontSize ? 1 : width >= 1024 ? 4 : 2
  for (const row of geometry.rows) {
    expect(row.values, 'KPI count follows its own width at the active text size').toBe(columns)
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
      widths, clippedCells, lastColumnClipped, valueSpreads, rests, sticky, inset, initial, stops,
      scrollLeft: scroll.scrollLeft, maximum, viewport: scroll.clientWidth,
      role: scroll.getAttribute('role'), tabIndex: scroll.getAttribute('tabindex'), label: scroll.getAttribute('aria-label'),
    }
  })
}

async function assertTable(page: Page, expectedPeriods: string[], state: AnalysisState) {
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
  const window = expectedPeriods.length === 12 ? 'all' : expectedPeriods[0] === PERIODS[0] ? 'earliest' : 'newest'
  // Count value marks inside source controls separately from comparison marks below them.
  await expect(sourceControls.locator('[data-note-kind="review"]')).toHaveCount(EXPECTED_TABLE_REVIEWS[state][window])
  // Q4 header daggers cannot satisfy value-mark presence; count inside source buttons.
  await expect(sourceControls.locator('span').filter({ hasText: /^†$/ })).toHaveCount(EXPECTED_TABLE_VALUE_DAGGERS[window])
  await expect(table.locator('tbody [data-note-kind="review"]:not(button *)')).toHaveCount(EXPECTED_TABLE_COMPARISON_REVIEWS[state][window])
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
    charts: await page.locator('[data-analysis-chart]').evaluateAll(charts => charts.map(chart => ({
      name: chart.getAttribute('data-analysis-chart'),
      // Recharts renders tick lines and labels in separate layers. Inspect the painted
      // label layer: counting the line groups can pass with twelve empty strings.
      ticks: [...chart.querySelectorAll('.recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-label')].map(tick => {
        const glyphs = [...tick.querySelectorAll('text,tspan')].filter(glyph => glyph.textContent?.trim())
        return {
          text: tick.textContent?.replace(/\s/g, '') ?? '',
          painted: glyphs.length > 0 && glyphs.every(glyph => {
            const box = glyph.getBoundingClientRect()
            const style = getComputedStyle(glyph)
            return glyph.checkVisibility({ visibilityProperty: true, opacityProperty: true })
              && box.width > 0 && box.height > 0 && style.fill !== 'none' && Number(style.fillOpacity) > 0
          }),
        }
      }),
      // Rendered line/bar geometry makes this stronger than a period-count attribute.
      shapes: [...chart.querySelectorAll('.recharts-line-curve,.recharts-area-curve,.recharts-bar-rectangle path,.recharts-bar-rectangle rect')].map(shape => ['d', 'x', 'y', 'width', 'height'].map(attr => shape.getAttribute(attr))),
    }))),
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
    for (const state of STATES) test(`${state}: content stays readable across table windows`, async ({ page, baseURL }) => {
      test.setTimeout(60_000)
      const traffic = await openAnalysis(page, baseURL!, state, theme, profile.textScale ?? 1)
      await assertNotes(page, state)
      await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
      await expect(page.locator('[data-analysis-chart]')).toHaveCount(4)
      const baseline = await stableAnalysisOutsideTable(page)
      for (const chart of baseline.charts) {
        expect(chart.ticks.map(tick => tick.text), `${chart.name}: all twelve ordered chart periods`).toEqual(PERIODS.map(period => `${period.slice(4)}'${period.slice(2, 4)}`))
        for (const tick of chart.ticks) expect(tick.painted, `${chart.name}: ${tick.text} has visible glyphs`).toBe(true)
        expect(chart.shapes.length, `${chart.name}: actual plotted data`).toBeGreaterThan(0)
      }
      const section = page.locator('[data-analysis-metrics]')
      const window = section.getByRole('group', { name: 'Table window', exact: true })
      const selections = [
        { label: 'All 12', periods: PERIODS },
        { label: 'Newest 6', periods: PERIODS.slice(-6) },
        { label: 'Earliest 6', periods: PERIODS.slice(0, 6) },
        { label: 'All 12', periods: PERIODS },
      ]
      for (const [index, selection] of selections.entries()) {
        if (index > 0) await window.getByRole('button', { name: selection.label, exact: true }).click()
        await expect(window.getByRole('button', { name: selection.label, exact: true })).toHaveAttribute('aria-pressed', 'true')
        await expect(section.getByRole('status')).toHaveText(`Showing ${selection.periods.length} of 12 quarters`)
        if (index > 0) await expect(window.getByRole('button', { name: selection.label, exact: true })).toBeFocused()
        await assertTable(page, selection.periods, state)
        await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
        expect(await stableAnalysisOutsideTable(page), 'table windows do not change KPI, note totals, or chart data').toEqual(baseline)
      }
      // Disclosure content is also part of the responsive page, not an overflow escape hatch.
      await section.getByRole('button', { name: /^Review data notes/ }).focus()
      await page.keyboard.press('Enter')
      await expect(page.locator(`${NOTES} > details`)).toHaveAttribute('open', '')
      await expect(page.locator(`${NOTES} li`).first()).toBeFocused()
      await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
      expect(traffic.dataset, 'table windows reuse the selected dataset').toBe(1)
      expect(traffic.stream, 'table windows never regenerate analysis').toBe(1)
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
    await section.getByRole('button', { name: 'Earliest 6', exact: true }).focus()
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
    for (let index = 0; index < PERIODS.length * 2; index++) {
      await page.keyboard.press('Tab')
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
      expect(fraction, `Tab cell ${index} is fully visible after native snapping`).toBeGreaterThanOrEqual(0.99)
    }
    const source = sources.nth(PERIODS.length * 2 - 1)
    await source.evaluate(button => {
      button.addEventListener('keydown', event => {
        queueMicrotask(() => button.setAttribute('data-key-prevented', String(event.defaultPrevented)))
      })
    })
    const beforeChild = await settleTable(page)
    await page.keyboard.press('Home')
    await expect(source).toHaveAttribute('data-key-prevented', 'false')
    expect((await settleTable(page)).left, 'a child control retains its own Home key').toBe(beforeChild.left)

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
        await page.locator('[data-analysis-metrics]').getByRole('button', { name: 'Newest 6', exact: true }).click()
        await expect(page.getByRole('columnheader', { name: 'FY2016–FY2025 CAGR', exact: true })).toBeAttached()
        await expect(page.locator('[data-analysis-metrics]').getByRole('status')).toHaveText('Showing 6 of 10 years')
        await assertTableGeometry(page, 7)
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
