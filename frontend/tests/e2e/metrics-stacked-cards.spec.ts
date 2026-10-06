import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Locator, type Page } from '@playwright/test'

/**
 * EN-03: below md (768px) each financial metric is one stacked card; at/above md the DataTable is
 * unchanged. Both presentations are in the DOM, switched by CSS, so this spec proves in a real
 * Chromium what jsdom cannot (tests/unit/FinancialMetricsCards.spec.tsx covers content parity):
 *
 *   - exactly one layout is rendered at every width, and the switch is at 767 → 768 with no mixed state;
 *   - the inactive layout contributes nothing to the accessibility tree (aria snapshot), takes no Tab
 *     stop, and the page carries no duplicate ids;
 *   - the caption / accessible name is exposed by whichever layout is active;
 *   - for the fixture at 390x844 the Total net sales value, change, takeaway and its provenance chip are
 *     visible in one viewport with no horizontal scrolling inside the card and no blank run taller than
 *     64px; the card's text computes no ellipsis, line clamp, nowrap or clipping height;
 *   - 320px wide and a 125% root font size reflow without horizontal overflow or clipping;
 *   - the landing page's sample table (the non-bare caller) stacks the same way.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside
 * the browser with page.route; the summary fixture is a trimmed copy of the public Apple FY2025 10-K
 * example (two metric rows). DOM, computed-style and keyboard probes only: this is not a screen-reader
 * test.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const SUMMARY = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-summary.json'), 'utf8')) as {
  rendered_sections: { id: string; blocks: { kind: string; metric_rows?: { metric: string; change_display?: string; commentary?: string }[] }[] }[]
}
const METRIC_ROWS = SUMMARY.rendered_sections.flatMap((s) => s.blocks).find((b) => b.kind === 'metrics')!.metric_rows!
const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const FILING = {
  id: 3,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  accession_number: '0000320193-25-000079',
  document_url: `${FOLDER}aapl-20250927.htm`,
  sec_url: FOLDER,
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
}
const SECTION = '#results-that-matter'
const CARDS = `${SECTION} [data-metric-cards]`
const CARD = `${SECTION} [data-metric-card]`
const TABLE = `${SECTION} [data-metric-table]`
const CAPTION = 'Financial highlights: current period, prior period, change, and investor takeaway per metric'

type Theme = 'light' | 'dark'
type Rect = { x: number; y: number; w: number; h: number }

async function answerApi(page: Page, baseURL: string) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (pathname) {
      case '/api/filings/3':
        return json(200, FILING)
      case '/api/summaries/filing/3':
        return json(200, SUMMARY)
      case '/api/filings/3/content':
        return json(200, { filing_id: 3, has_content: false, markdown_content: null })
      case '/api/auth/me':
        return json(401, { detail: 'Not authenticated' })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}

/** Anonymous reader, consent stored and the first-run nudge seen, so no chrome sits over the summary. */
async function openFiling(page: Page, baseURL: string, theme: Theme = 'light') {
  await answerApi(page, baseURL)
  await page.addInitScript((theme: Theme) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      localStorage.setItem('en:copilot-coachmark-v1', '1')
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  await expect(page.locator(SECTION)).toBeVisible()
}

const rectOf = (loc: Locator): Promise<Rect> =>
  loc.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { x: r.x, y: r.y, w: r.width, h: r.height }
  })
const viewport = (page: Page) => page.evaluate(() => ({ w: window.innerWidth, h: window.innerHeight }))
/** Inside the viewport AND below the sticky site header (content under the header is not visible). */
const inside = (r: Rect, vp: { w: number; h: number; top?: number }) =>
  r.x >= 0 && r.y >= (vp.top ?? 0) - 0.5 && r.x + r.w <= vp.w + 0.5 && r.y + r.h <= vp.h + 0.5
const headerBottom = (page: Page) => page.locator('header').first().evaluate((el) => el.getBoundingClientRect().bottom)

/** Exactly one of the two layouts is rendered (display) at the current width. */
async function expectSingleLayout(page: Page, active: 'cards' | 'table') {
  const shown = await page.evaluate(
    ({ CARDS, TABLE }) => ({
      cards: getComputedStyle(document.querySelector(CARDS)!).display,
      table: getComputedStyle(document.querySelector(TABLE)!).display,
    }),
    { CARDS, TABLE },
  )
  if (active === 'cards') {
    expect(shown.cards).not.toBe('none')
    expect(shown.table).toBe('none')
    await expect(page.locator(CARDS)).toBeVisible()
    await expect(page.locator(TABLE)).toBeHidden()
  } else {
    expect(shown.table).not.toBe('none')
    expect(shown.cards).toBe('none')
    await expect(page.locator(`${TABLE} table`)).toBeVisible()
    await expect(page.locator(CARDS)).toBeHidden()
  }
}

/** The aria snapshot of the section names the active layout with the caption and omits the other. */
async function expectAccessibleLayout(page: Page, active: 'cards' | 'table') {
  const snapshot = await page.locator(SECTION).ariaSnapshot()
  const hasList = new RegExp(`list "${CAPTION}"`).test(snapshot)
  const hasTable = new RegExp(`table "${CAPTION}"`).test(snapshot)
  expect(hasList, `a list named by the caption in the aria snapshot:\n${snapshot}`).toBe(active === 'cards')
  expect(hasTable, `a table named by the caption in the aria snapshot:\n${snapshot}`).toBe(active === 'table')
  // the hidden layout contributes none of its own nodes: the cards' sentence-case labels and
  // definition terms, or the table's column headers and cells
  if (active === 'cards') {
    expect(snapshot, `no table nodes while the cards are active:\n${snapshot}`).not.toMatch(/columnheader|- cell|- row /)
    expect(snapshot).toMatch(/- term: Current/)
  } else {
    expect(snapshot, `no card nodes while the table is active:\n${snapshot}`).not.toMatch(/- term|- definition/)
    expect(snapshot).toMatch(/columnheader "Current Period"/)
  }
}

/** Tab through the section from its first control: every stop belongs to the active layout, and the walk covers it. */
async function expectTabStopsOnlyIn(page: Page, active: 'cards' | 'table') {
  const activeSel = active === 'cards' ? CARDS : TABLE
  const inactiveSel = active === 'cards' ? TABLE : CARDS
  const expected = await page.locator(`${activeSel} a, ${activeSel} button`).count()
  expect(expected).toBeGreaterThan(0)
  await page.locator(`${activeSel} a, ${activeSel} button`).first().focus()
  const stops: string[] = []
  for (let i = 0; i < expected + 2; i++) {
    const where = await page.evaluate(
      ({ activeSel, inactiveSel, SECTION }) => {
        const el = document.activeElement
        if (!el || el === document.body) return 'body'
        if (el.closest(inactiveSel)) return 'INACTIVE'
        if (el.closest(activeSel)) return 'active'
        return el.closest(SECTION) ? 'section' : 'outside'
      },
      { activeSel, inactiveSel, SECTION },
    )
    stops.push(where)
    if (where === 'outside' || where === 'body') break
    // On a fine pointer a focused chip opens its evidence popover and Tab would enter it (a portal
    // outside the section): close it first so the walk moves chip to chip. Escape is a no-op otherwise.
    if (where === 'active') await page.keyboard.press('Escape')
    await page.keyboard.press('Tab')
  }
  expect(stops, 'no Tab stop may land in the inactive layout').not.toContain('INACTIVE')
  expect(stops.filter((s) => s === 'active'), 'every control of the active layout is reached').toHaveLength(expected)
}

const duplicateIds = (page: Page) =>
  page.evaluate(() => {
    const seen = new Map<string, number>()
    for (const el of Array.from(document.querySelectorAll('[id]'))) seen.set(el.id, (seen.get(el.id) ?? 0) + 1)
    return Array.from(seen).filter(([, n]) => n > 1).map(([id]) => id)
  })

/** Computed-style facts for every text node holder in a card. */
const cardTextStyles = (card: Locator) =>
  card.evaluate((root) => {
    const out: { tag: string; text: string; whiteSpace: string; textOverflow: string; lineClamp: string; overflowY: string; clipped: boolean; fontSize: number; floor: number }[] = []
    for (const el of Array.from(root.querySelectorAll<HTMLElement>('*'))) {
      if (el.closest('svg') || el.closest('a, button')) continue // the provenance chips keep their own (text-data-xs) type
      const ownText = Array.from(el.childNodes).some((n) => n.nodeType === Node.TEXT_NODE && (n.textContent ?? '').trim())
      if (!ownText) continue
      const cs = getComputedStyle(el)
      // labels (dt) and the per-ADS annotation (PerAdsNote, text-xs by design) are 12px; everything else is the table's 14px body
      const annotation = el.tagName === 'DT' || !!el.closest('[title]')
      // inline boxes report no scroll size; clipping is a block-level fact
      const block = cs.display !== 'inline'
      out.push({
        tag: el.tagName.toLowerCase(),
        text: (el.textContent ?? '').trim().slice(0, 30),
        whiteSpace: cs.whiteSpace,
        textOverflow: cs.textOverflow,
        lineClamp: cs.webkitLineClamp,
        overflowY: cs.overflowY,
        clipped: block && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1),
        fontSize: parseFloat(cs.fontSize),
        floor: annotation ? 12 : 14,
      })
    }
    return out
  })

/** The three `<dl>` groups of a card (Current / Prior / Change) sit on one line: equal tops. */
const groupTops = (card: Locator) => card.locator('dl > div').evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().top)))

/** No run of blank space taller than 64px between the card's visible blocks, and none inside its padding. */
const blankRuns = (card: Locator) =>
  card.evaluate((root) => {
    const r = root.getBoundingClientRect()
    const blocks = Array.from(root.children).map((c) => c.getBoundingClientRect()).filter((b) => b.height > 0)
    const gaps: number[] = []
    gaps.push(blocks[0].top - r.top)
    for (let i = 1; i < blocks.length; i++) gaps.push(blocks[i].top - blocks[i - 1].bottom)
    gaps.push(r.bottom - blocks[blocks.length - 1].bottom)
    return { gaps: gaps.map((g) => Math.round(g)), height: Math.round(r.height), hScroll: root.scrollWidth > root.clientWidth + 1 }
  })

for (const theme of ['light', 'dark'] as const) {
  test.describe(`phone 390x844, ${theme}`, () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

    test('one card per metric; Total net sales is fully in one viewport; nothing clipped, forced onto a line or scrolled sideways', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, theme)
      await expectSingleLayout(page, 'cards')
      await expect(page.locator(CARD)).toHaveCount(METRIC_ROWS.length)

      const first = page.locator(CARD).first()
      await first.scrollIntoViewIfNeeded()
      // settle the card just under the sticky header, then measure against the header's bottom edge
      await page.evaluate(() => window.scrollBy({ top: -80, behavior: 'instant' }))
      const vp = { ...(await viewport(page)), top: await headerBottom(page) }
      const cardRect = await rectOf(first)
      expect(inside(cardRect, vp), 'the whole first card fits one viewport').toBe(true)
      // the named fixture's Current / Prior / Change row is one line at 390px
      const tops = await groupTops(first)
      expect(tops, 'Current / Prior / Change on one line').toHaveLength(3)
      expect(new Set(tops).size, `the value row wrapped: tops ${tops}`).toBe(1)
      // value, change, takeaway and its chip, each inside the viewport at once
      const value = first.locator('dd').first()
      const change = first.getByText(METRIC_ROWS[0].change_display!)
      const takeaway = first.locator('p')
      const chip = first.getByRole('button', { name: /Verified in filing/ })
      for (const [label, loc] of [['value', value], ['change', change], ['takeaway', takeaway], ['chip', chip]] as const) {
        await expect(loc).toBeVisible()
        expect(inside(await rectOf(loc), vp), `${label} inside the viewport`).toBe(true)
      }
      await expect(takeaway).toHaveText(METRIC_ROWS[0].commentary!)
      expect(await first.getByText('Current', { exact: true }).count()).toBe(1)
      expect(await first.getByText('Prior', { exact: true }).count()).toBe(1)
      expect(await first.getByText('Change', { exact: true }).count()).toBe(1)

      // no blank run > 64px, no horizontal scrolling inside any card or the section
      for (const card of await page.locator(CARD).all()) {
        const runs = await blankRuns(card)
        expect(runs.hScroll, 'card scrolls sideways').toBe(false)
        for (const g of runs.gaps) expect(g, `blank run in a card: ${runs.gaps}`).toBeLessThanOrEqual(64)
        for (const s of await cardTextStyles(card)) {
          expect(s.whiteSpace, `${s.tag} "${s.text}" white-space`).not.toMatch(/nowrap|pre$/)
          expect(s.textOverflow, `${s.tag} "${s.text}" text-overflow`).not.toBe('ellipsis')
          expect(s.lineClamp, `${s.tag} "${s.text}" line-clamp`).toBe('none')
          expect(s.clipped, `${s.tag} "${s.text}" is clipped`).toBe(false)
          expect(s.fontSize, `${s.tag} "${s.text}" font-size`).toBeGreaterThanOrEqual(s.floor)
        }
      }
      const section = await page.locator(SECTION).evaluate((el) => ({ sw: el.scrollWidth, cw: el.clientWidth }))
      expect(section.sw).toBeLessThanOrEqual(section.cw + 1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true)

      await expectAccessibleLayout(page, 'cards')
      await expectTabStopsOnlyIn(page, 'cards')
      expect(await duplicateIds(page)).toEqual([])
    })
  })
}

test.describe('the switch is at 767 → 768 with no mixed state', () => {
  test.use({ viewport: { width: 767, height: 1024 } })

  test('cards at 767, the unchanged table at 768, with the same text in both', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await expectSingleLayout(page, 'cards')
    await expectAccessibleLayout(page, 'cards')
    await expectTabStopsOnlyIn(page, 'cards')
    const cardText = await page.locator(CARDS).evaluate((el) => (el.textContent ?? '').replace(/\s+/g, ' ').trim())

    await page.setViewportSize({ width: 768, height: 1024 })
    await expectSingleLayout(page, 'table')
    await expectAccessibleLayout(page, 'table')
    await expectTabStopsOnlyIn(page, 'table')
    expect(await duplicateIds(page)).toEqual([])
    const table = page.locator(`${TABLE} table`)
    await expect(table.locator('thead th')).toHaveText(['Metric', 'Current Period', 'Prior Period', 'Change', 'Investor Takeaway'])
    await expect(table.locator('tbody tr')).toHaveCount(METRIC_ROWS.length)
    await expect(table.locator('caption')).toHaveText(CAPTION)
    // every cell string of the table is in the card text (the card adds only its period labels)
    for (const cell of await table.locator('tbody td').allTextContents()) {
      const s = cell.replace(/\s+/g, ' ').trim()
      if (s) expect(cardText, `table cell "${s.slice(0, 40)}" is in the cards`).toContain(s)
    }
  })
})

test.describe('desktop 1440x900', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('the table alone is rendered and reachable; the hidden cards add no stops or ids', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await expectSingleLayout(page, 'table')
    await expectAccessibleLayout(page, 'table')
    await expectTabStopsOnlyIn(page, 'table')
    expect(await duplicateIds(page)).toEqual([])
    const table = page.locator(`${TABLE} table`)
    await expect(table.locator('tbody tr')).toHaveCount(METRIC_ROWS.length)
    await expect(table.locator('tbody tr').first()).toContainText(METRIC_ROWS[0].change_display!)
  })
})

test.describe('narrow 320x568 and enlarged text', () => {
  test.use({ viewport: { width: 320, height: 568 }, isMobile: true, hasTouch: true })

  test('cards reflow at 320px and at a 125% root font size without sideways scroll or clipping', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await expectSingleLayout(page, 'cards')
    for (const rootFont of ['', '20px']) {
      await page.evaluate((size) => {
        document.documentElement.style.fontSize = size
      }, rootFont)
      await page.locator(CARD).first().scrollIntoViewIfNeeded()
      for (const card of await page.locator(CARD).all()) {
        const runs = await blankRuns(card)
        expect(runs.hScroll, `card scrolls sideways (root font ${rootFont || 'default'})`).toBe(false)
        for (const g of runs.gaps) expect(g).toBeLessThanOrEqual(64)
        for (const s of await cardTextStyles(card)) {
          expect(s.clipped, `${s.tag} "${s.text}" is clipped (root font ${rootFont || 'default'})`).toBe(false)
          expect(s.whiteSpace).not.toMatch(/nowrap|pre$/)
        }
        const r = await rectOf(card)
        expect(r.x).toBeGreaterThanOrEqual(0)
        expect(r.x + r.w).toBeLessThanOrEqual(320.5)
      }
      // The section never scrolls sideways. The page as a whole is checked at the default size only:
      // at a 20px root font the site header's own controls overflow 320px (pre-existing, not the cards).
      const section = await page.locator(SECTION).evaluate((el) => el.scrollWidth <= el.clientWidth + 1)
      expect(section, `the section scrolls sideways (root font ${rootFont || 'default'})`).toBe(true)
      if (!rootFont) expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), 'no page-level sideways scroll').toBe(true)
    }
  })
})

test.describe('the landing page sample (the non-bare caller)', () => {
  test('stacks its three rows below md and keeps the table above', async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      } catch {}
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    const evidence = page.locator('#evidence')
    await expect(evidence).toBeVisible()
    await expect(evidence.locator('[data-metric-card]')).toHaveCount(3)
    await expect(evidence.locator('[data-metric-cards]')).toBeVisible()
    await expect(evidence.locator('[data-metric-table]')).toBeHidden()
    await expect(evidence.getByRole('heading', { name: 'Financial Highlights' })).toBeVisible()
    await expect(evidence.getByText(/Each row carries its own source label/)).toBeVisible()
    for (const card of await evidence.locator('[data-metric-card]').all()) {
      expect((await blankRuns(card)).hScroll).toBe(false)
    }
    await page.setViewportSize({ width: 1440, height: 900 })
    await expect(evidence.locator('[data-metric-table] table')).toBeVisible()
    await expect(evidence.locator('[data-metric-cards]')).toBeHidden()
  })
})
