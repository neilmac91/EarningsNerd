import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import type { AnalysisDataset } from '../../features/analysis/api/analysis-api'
import { selectHeadlineFigures } from '../../features/analysis/lib/reportPresentation'
import { openDataset, type AnalysisTheme } from './fixtures/analysisLayoutApi'

/**
 * The later-filing evidence in the browser (MPA WP5a-F1): the page's readers on the shared fixture's planted payload
 * (backend/tests/fixtures/analysis_later_filings.json, REGN's own-report values), as the producer will send it. A figure
 * a later filing reports differently carries no mark and its n/m is read in words; the data notes' open detail names
 * those figures in one line; the dialog gives both filings; the chart's footnote names the n/m's cause. A sign flip, the
 * one later value that is also a note, keeps its letter inside its cell. Nothing scrolls sideways. CI boots next start
 * with no backend: every API path is answered by the layout fixture's router.
 */
const FIXTURE = JSON.parse(readFileSync(path.join(__dirname, '../../../backend/tests/fixtures/analysis_later_filings.json'), 'utf8')) as {
  cases: Array<{ name: string; dataset: AnalysisDataset }>
}
const planted = (name: string) => structuredClone(FIXTURE.cases.find((entry) => entry.name === name)!.dataset)
// The datasets the producer builds (backend/tests/unit/test_first_reports_wire.py keeps the file equal to its output).
const PRODUCED = JSON.parse(readFileSync(path.join(__dirname, '../../../backend/tests/fixtures/analysis_first_reports_produced.json'), 'utf8')) as {
  datasets: Record<string, AnalysisDataset>
}
const THEMES: AnalysisTheme[] = ['light', 'dark']
const LINE = '[data-analysis-later-filings]'

async function open(page: Page, baseURL: string, name: string, theme: AnalysisTheme) {
  const dataset = planted(name)
  await openDataset(page, baseURL, dataset, theme, selectHeadlineFigures(dataset).length)
}

/** The page's and the open dialog's sideways overflow, if any, in CSS pixels. */
const overflow = (page: Page) => page.evaluate(() => {
  const root = document.documentElement
  const panel = document.querySelector('[role="dialog"]')
  return { page: root.scrollWidth - root.clientWidth, dialog: panel ? panel.scrollWidth - panel.clientWidth : 0 }
})

test.describe.configure({ mode: 'parallel' })

for (const theme of THEMES) for (const width of [390, 1480]) test.describe(`analysis later filings / ${theme} / ${width}px`, () => {
  test.use({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('a later filing’s value: no mark, n/m in words, the line, both filings in the dialog, the chart’s cause', async ({ page, baseURL }) => {
    test.setTimeout(90_000)
    await open(page, baseURL!, 'regn_own_reports_beside_later_comparatives', theme)
    const table = page.locator('[data-analysis-metrics] table')
    const control = table.getByRole('button', { name: /^Revenue, FY2018: \$5\.1B/ })
    const cell = control.locator('xpath=ancestor::td[1]')
    // Evidence, not a note (D-061): no letter on the figure or its change, and the n/m is read as words.
    await expect(cell.locator('[data-note-letter]')).toHaveCount(0)
    await expect(cell.getByText('n/m', { exact: true })).toHaveAttribute('aria-hidden', 'true')
    await expect(cell.getByText('not meaningful', { exact: true })).toHaveClass(/\bsr-only\b/)
    await expect(page.getByText('n/m means not meaningful.')).toBeVisible()

    // The data notes' line, in the open detail only.
    const notes = page.locator('[data-analysis-data-notes]')
    await expect(notes.locator(LINE)).toBeHidden()
    await notes.locator(':scope > details > summary').click()
    await expect(notes.locator(LINE)).toHaveText('A later filing reports a different value for 3 figures (Revenue FY2018, FY2019; Total assets FY2018); select one to see both filings. Growth across the change reads n/m (Revenue FY2018, FY2019, FY2020; Net margin FY2018, FY2019, FY2020).')
    await expect(notes.locator(':scope > details > summary')).toContainText('No figures need review')

    // The chart's footnote names this n/m's cause, never the sign change's.
    const topline = page.locator('section[data-trend-chart="topline"]')
    const footnotes = topline.locator('[data-chart-text="footnote"]')
    await expect(footnotes.filter({ hasText: 'Not meaningful: a later filing reports a different value for one or both years (FY2018–FY2020).' })).toHaveCount(1)
    await expect(footnotes.filter({ hasText: 'zero or of the opposite sign' })).toHaveCount(0)

    // The dialog gives both filings, and the growth as first reported under the n/m's cause.
    await control.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('heading', { name: 'Source filings' })).toBeVisible()
    await expect(dialog).toContainText('First reported as $6.7B in its own annual report (10-K, filed 7 Feb 2019). A later filing (filed 8 Feb 2021) reports $5.1B, shown here.')
    await expect(dialog.getByRole('link', { name: 'Open its own annual report on SEC.gov (10-K, filed 7 Feb 2019) for Revenue, FY2018' })).toHaveText('Open its own annual report on SEC.gov')
    await expect(dialog.getByRole('link', { name: 'Open the later filing on SEC.gov (10-K, filed 8 Feb 2021) for Revenue, FY2018' })).toHaveText('Open the later filing on SEC.gov')
    // The "As filed" pair: each value takes its row's right edge, so the two values' digit groups stand under each other.
    const edges = await dialog.locator('p', { hasText: /^As filed in / }).evaluateAll((rows) => rows.map((row) => Math.round(row.lastElementChild!.getBoundingClientRect().right)))
    expect(edges).toHaveLength(2)
    expect(Math.abs(edges[0] - edges[1]), 'the two values end on one edge').toBeLessThanOrEqual(1)
    await expect(dialog).toContainText('Not meaningful: a later filing reports a different value for one or both of the two years.')
    await expect(dialog).toContainText('As first reported: +14.3%')
    await expect(dialog.locator('[data-note-letter]')).toHaveCount(0)
    expect(await overflow(page), 'nothing scrolls sideways, page or dialog').toEqual({ page: 0, dialog: 0 })
  })

  test('a sign flip and a factor of 1,000: the note’s letter inside its cell, the finding in the dialog', async ({ page, baseURL }) => {
    test.setTimeout(90_000)
    await open(page, baseURL!, 'a_sign_flip_and_a_scale_factor_count_as_figures', theme)
    const control = page.locator('[data-analysis-metrics] table').getByRole('button', { name: /^Financing cash flow, FY2020: / })
    const cell = control.locator('xpath=ancestor::td[1]')
    await expect(control.locator('[data-note-letter]')).toHaveText('a')
    const inside = await cell.evaluate((td) => {
      const box = td.getBoundingClientRect()
      const mark = td.querySelector('[data-note-letter]')!.getBoundingClientRect()
      return mark.left >= box.left - 1 && mark.right <= box.right + 1
    })
    expect(inside, 'the letter stays inside its cell').toBe(true)
    await control.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('A later filing reports the opposite sign.')
    await expect(dialog).toContainText('As first reported: n/m')
    await expect(dialog).toContainText('Needs review · Note a')
    expect(await overflow(page), 'nothing scrolls sideways, page or dialog').toEqual({ page: 0, dialog: 0 })
  })
})

/** A KPI change line's letter where the change fills the card (E289): the producer marks the net margin over its slipped
 *  revenue input, so its window change across the slipped year, -36,374.6pp, takes note a. At 320px the line breaks after
 *  its label, never between the change and its letter (chief design's probe on #1951 found the letter alone on a line). */
for (const theme of THEMES) test.describe(`analysis KPI change line / ${theme} / 320px`, () => {
  test.use({ viewport: { width: 320, height: 1000 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('a long change keeps its letter on its line', async ({ page, baseURL }) => {
    test.setTimeout(90_000)
    const dataset = structuredClone(PRODUCED.datasets['an-inputs-finding FY2018..FY2021'])
    await openDataset(page, baseURL!, dataset, theme, selectHeadlineFigures(dataset).length)
    const card = page.locator('[data-analysis-kpi]').filter({ has: page.getByRole('term').filter({ hasText: /^Net margin$/ }) })
    const change = card.locator('[data-kpi-change]')
    await expect(change.locator('[data-note-letter]')).toHaveText('a')
    const geometry = await change.evaluate((pair) => {
      const glyphs: Array<{ left: number; right: number; top: number; bottom: number }> = []
      const range = document.createRange()
      const walker = document.createTreeWalker(pair, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (node.parentElement!.closest('[data-note-letter]') || !node.textContent!.trim()) continue
        range.selectNodeContents(node)
        for (const rect of range.getClientRects()) if (rect.width && rect.height) glyphs.push({ left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom })
      }
      const mark = pair.querySelector('[data-note-letter]')!.getBoundingClientRect()
      const box = pair.closest('[data-analysis-kpi]')!.getBoundingClientRect()
      return { glyphs, mark: { left: mark.left, right: mark.right, top: mark.top }, box: { left: box.left, right: box.right } }
    })
    expect(new Set(geometry.glyphs.map((glyph) => Math.round(glyph.top))).size, 'the change keeps one line').toBe(1)
    const end = geometry.glyphs.at(-1)!
    // Wrapped onto a line of its own, the letter would start at the card's inset, left of its change's end.
    expect(geometry.mark.left, 'the letter follows its change').toBeGreaterThanOrEqual(end.right - 0.5)
    expect(geometry.mark.top, 'the letter sits on its change line, raised').toBeLessThan(end.bottom)
    expect(geometry.mark.right, 'the letter stays inside its card').toBeLessThanOrEqual(geometry.box.right)
    expect(await overflow(page), 'nothing scrolls sideways').toEqual({ page: 0, dialog: 0 })
  })
})
