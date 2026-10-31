import { test, expect, type Page } from '@playwright/test'

/**
 * The landing page's Financial highlights table (features/summaries/components/FinancialMetricsTable.tsx, fed four
 * live rows by EvidenceSection) laid out as the founder's review of 2026-10-22 asked (tasks/evidence-row-ux-plan-
 * 2026-10-22.md, R6), measured on the painted text wherever the table shows: the column headings share one bottom
 * edge; no heading or chip wraps (the date under each year is its second line by design); each figure starts on its
 * metric's line; the change glyphs share one left edge; the Change column keeps 40px from the takeaway; and each
 * metric is its row's header. Text inside .sr-only is not painted, so it is not measured. The landing switches the
 * cards for the table at the component's own width of 52rem (layoutBy="container"), so at 1024px, where the
 * label column leaves the content 42rem, the cards show: a table there squeezed each takeaway to a 100px ribbon.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md); the table is static sample content.
 */
type Theme = 'light' | 'dark'

async function openLanding(page: Page, theme: Theme, width: number) {
  await page.setViewportSize({ width, height: 900 })
  await page.addInitScript((theme: Theme) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/')
  await expect(page.locator('#evidence')).toBeVisible()
  return page.locator('#evidence [data-metrics-layout="table"] table')
}

async function openTable(page: Page, theme: Theme, width: number) {
  const table = await openLanding(page, theme, width)
  await expect(table).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await table.scrollIntoViewIfNeeded()
  return table
}

function measure(table: HTMLTableElement) {
  type Lines = { left: number; right: number; top: number; bottom: number; lines: number } | null
  // The painted text of an element: every visible text node's line boxes, skipping visually hidden text.
  const painted = (el: Element | null): Lines => {
    if (!el) return null
    const rects: DOMRect[] = []
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent?.trim() || node.parentElement?.closest('.sr-only')) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      rects.push(...[...range.getClientRects()].filter((r) => r.width > 0))
    }
    if (rects.length === 0) return null
    return {
      left: Math.min(...rects.map((r) => r.left)),
      right: Math.max(...rects.map((r) => r.right)),
      top: Math.min(...rects.map((r) => r.top)),
      bottom: Math.max(...rects.map((r) => r.bottom)),
      lines: new Set(rects.map((r) => Math.round(r.top))).size,
    }
  }
  const headers = [...table.querySelectorAll('thead th')].map((th) => ({
    text: (th as HTMLElement).innerText.replace(/\s+/g, ' ').trim(),
    // A period heading carries its end date as a second block line.
    expectedLines: th.querySelector('span.block') ? 2 : 1,
    text_box: painted(th),
  }))
  const rows = [...table.querySelectorAll('tbody tr')].map((tr) => {
    const field = (name: string) => tr.querySelector(`[data-metric-field="${name}"]`)
    const chip = field('name')?.querySelector('a,button') ?? null
    const takeawayChip = field('takeaway')?.querySelector('a,button') ?? null
    const name = field('name')?.querySelector('span') ?? null
    return {
      rowHeader: tr.firstElementChild?.tagName === 'TH' && tr.firstElementChild.getAttribute('scope') === 'row',
      name: painted(name),
      chip: painted(chip),
      takeawayChip: takeawayChip ? painted(takeawayChip) : null,
      current: painted(field('current')),
      prior: painted(field('prior')),
      change: painted(field('change')),
      glyphLeft: field('change')?.querySelector('svg')?.getBoundingClientRect().left ?? null,
      takeaway: painted(field('takeaway')),
    }
  })
  return { headers, rows }
}

// 900px: one column, the content 53.25rem wide; 1280px and 1440px: beside the label column, 58rem.
for (const [theme, width] of [['light', 900], ['light', 1280], ['light', 1440], ['dark', 1280]] as const) {
  test(`the landing highlights table lines up at ${width}px, ${theme} theme`, async ({ page }) => {
    const table = await openTable(page, theme, width)
    const { headers, rows } = await table.evaluate(measure)

    expect(rows).toHaveLength(4)
    const bottoms = headers.map((h) => h.text_box!.bottom)
    expect(Math.max(...bottoms) - Math.min(...bottoms), `header bottoms ${bottoms.join(', ')}`).toBeLessThanOrEqual(1)
    for (const h of headers) expect(h.text_box!.lines, `"${h.text}" wraps`).toBe(h.expectedLines)

    const glyphs = rows.map((r) => r.glyphLeft!)
    expect(Math.max(...glyphs) - Math.min(...glyphs), `change glyph lefts ${glyphs.join(', ')}`).toBeLessThanOrEqual(0.5)
    for (const [i, r] of rows.entries()) {
      const label = `row ${i + 1}`
      expect(r.rowHeader, `${label}: the metric is not the row's header`).toBe(true)
      expect(r.chip!.lines, `${label}: its chip wraps`).toBe(1)
      if (r.takeawayChip) expect(r.takeawayChip.lines, `${label}: its takeaway's chip wraps`).toBe(1)
      expect(Math.abs(r.current!.top - r.name!.top), `${label}: the current figure leaves its metric's line`).toBeLessThanOrEqual(2)
      expect(Math.abs(r.prior!.top - r.name!.top), `${label}: the prior figure leaves its metric's line`).toBeLessThanOrEqual(2)
      expect(r.takeaway!.left - r.change!.right, `${label}: the change crowds the takeaway`).toBeGreaterThanOrEqual(40)
    }
  })
}

test('at 1024px the content column is under 52rem, so the landing shows the cards, not the table', async ({ page }) => {
  const table = await openLanding(page, 'light', 1024)
  const cards = page.locator('#evidence [data-metrics-layout="cards"]')
  await expect(cards).toBeVisible()
  await expect(cards.locator('[data-metric-card]')).toHaveCount(4)
  await expect(table).toBeHidden()
})
