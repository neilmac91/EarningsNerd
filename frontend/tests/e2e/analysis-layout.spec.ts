import { expect, test, type Page } from '@playwright/test'
import { EXPECTED_KPI_LETTERS, EXPECTED_KPI_VALUES, EXPECTED_NOTES, EXPECTED_TABLE_CELL_NOTES, EXPECTED_TABLE_COMPARISON_REVIEWS, EXPECTED_TABLE_REVIEWS, EXPECTED_TABLE_VALUE_DAGGERS, METRICS, PERIODS, UNAVAILABLE_CELLS, openAnalysis, type AnalysisState, type AnalysisTheme } from './fixtures/analysisLayoutApi'

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
  for (const row of geometry.rows) {
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
      const outside = textRects(cell).filter(text => text.left < box.left - 1 || text.right > box.right + 1 || text.clippedBy.length)
      return outside.length ? [{ row: rowIndex, column, outside }] : []
    }))
    const widths = [...table.querySelectorAll('thead th')].slice(1).map(cell => rect(cell).width)
    scroll.scrollTo({ left: scroll.scrollWidth, behavior: 'instant' })
    let stableFrames = 0, previous = -1, frame = 0
    while (stableFrames < 5 && frame++ < 120) {
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      const next = scroll.scrollLeft
      stableFrames = Math.abs(next - previous) < 0.1 ? stableFrames + 1 : 0
      previous = next
    }
    const scrollBox = rect(scroll)
    const partialColumns: Array<{ row: number; column: number; left: number; stickyRight: number }> = []
    const occludedText: Array<{ row: number; column: number; text: string }> = []
    const lastColumnClipped: Array<{ row: number; text: string }> = []
    for (const [rowIndex, row] of rows.entries()) {
      const cells = [...row.children]
      const sticky = cells[0]
      if (!sticky) continue
      if (getComputedStyle(sticky).position !== 'sticky') throw new Error('The metric labels must remain sticky while periods scroll')
      const boundary = Math.max(scrollBox.left, rect(sticky).right)
      for (let column = 1; column < cells.length; column++) {
        const cell = cells[column]; const box = rect(cell)
        if (box.right > boundary + 1 && box.left < boundary - 1 && box.left < scrollBox.right - 1) partialColumns.push({ row: rowIndex, column, left: box.left, stickyRight: boundary })
        for (const text of textRects(cell)) {
          if (text.left < boundary - 1 && text.right > boundary + 1) occludedText.push({ row: rowIndex, column, text: text.text })
          if (column === cells.length - 1 && (text.left < boundary - 1 || text.right > scrollBox.right + 1)) lastColumnClipped.push({ row: rowIndex, text: text.text })
        }
      }
    }
    return {
      widths, clippedCells, partialColumns, occludedText, lastColumnClipped,
      stable: stableFrames >= 5, scrollLeft: scroll.scrollLeft, maximum: scroll.scrollWidth - scroll.clientWidth,
      role: scroll.getAttribute('role'), tabIndex: scroll.tabIndex, label: scroll.getAttribute('aria-label'),
    }
  })
}

async function assertTable(page: Page, expectedPeriods: string[], state: AnalysisState) {
  const table = page.locator(TABLE)
  const headers = table.locator('thead th')
  await expect(headers).toHaveCount(expectedPeriods.length + 1)
  await expect(table.locator('tbody tr')).toHaveCount(METRICS)
  const labels = await headers.allTextContents()
  expect(labels.slice(1).map(label => label.replace(/[\s†]/g, ''))).toEqual(expectedPeriods.map(period => `${period.slice(4)}’${period.slice(2, 4)}`))
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
  await assertPaintedMarks(page, TABLE)
  const geometry = await tableGeometry(page)
  await assertSourceControls(page, `${TABLE} tbody`, METRICS * expectedPeriods.length)
  expect(geometry.widths).toHaveLength(expectedPeriods.length)
  expect(Math.min(...geometry.widths), 'period columns cannot collapse').toBeGreaterThan(0)
  expect(Math.max(...geometry.widths) - Math.min(...geometry.widths), 'every period receives the same width').toBeLessThanOrEqual(EPSILON)
  expect(geometry.clippedCells, 'actual glyph ranges fit every header and body cell, including hidden-by-overflow descendants').toEqual([])
  expect(geometry.stable, 'wait for native snap to settle before evaluating the far-right endpoint').toBe(true)
  expect(geometry.maximum - geometry.scrollLeft, 'last period remains reachable at the far-right endpoint').toBeLessThanOrEqual(EPSILON)
  expect(geometry.partialColumns, 'no partly visible period sits beneath the sticky metric column at rest').toEqual([])
  expect(geometry.occludedText, 'no actual text straddles the sticky boundary in any row').toEqual([])
  expect(geometry.lastColumnClipped, 'the complete last period remains readable at the far-right endpoint').toEqual([])
  expect(geometry.role).toBe('region')
  expect(geometry.tabIndex).toBe(0)
  expect(geometry.label).toContain('Metrics by period')

  // A correctly positioned sticky label can still leak scrolled text through a
  // translucent hover background. Measure its actual painted background, not a class.
  const rowHeader = page.locator(`${TABLE} tbody th[scope="row"]`).first()
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
        await expect(section.getByText(`Showing ${selection.periods.length} of 12 quarters`, { exact: true })).toBeVisible()
        await assertTable(page, selection.periods, state)
        await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
        expect(await stableAnalysisOutsideTable(page), 'table windows do not change KPI, note totals, or chart data').toEqual(baseline)
      }
      // Disclosure content is also part of the responsive page, not an overflow escape hatch.
      await page.locator(`${NOTES} > details > summary`).click()
      await expect(page.locator(`${NOTES} > details`)).toHaveAttribute('open', '')
      await assertPageAndCards(page, profile.width, profile.textScale ?? 1, state)
      expect(traffic.dataset, 'table windows reuse the selected dataset').toBe(1)
      expect(traffic.stream, 'table windows never regenerate analysis').toBe(1)
      expect(traffic.unexpectedApi).toEqual([])
    })
  })
}

for (const theme of THEMES) for (const width of [390, 1480]) for (const textScale of [1, 2]) {
  test.describe(`analysis period controls / ${theme} / ${width}px / ${textScale * 100}% text`, () => {
    test.use({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })
    test('keeps range changes readable and explains unavailable modes in the Tab order', async ({ page, baseURL }) => {
      await openAnalysis(page, baseURL!, 'clean', theme, textScale)
      const from = page.getByLabel('From', { exact: true })
      const to = page.getByLabel('To', { exact: true })
      await from.selectOption('2022Q1')
      await expect(to).toHaveValue('2024Q4')
      await expect(page.getByRole('status').filter({ hasText: 'To moved' })).toHaveText('To moved to Q4 2024 to keep at most 12 quarters.')
      await expect(page.getByText('Q1 2022 – Q4 2024 · 12 quarters', { exact: true })).toBeVisible()
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
        expect(geometry.selectedWidth).toBeLessThanOrEqual(geometry.available + EPSILON)
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
      await expect(quarterly).not.toBeDisabled()
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
