import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Locator, type Page } from '@playwright/test'

/**
 * EN-03: below md (768px) each financial metric is one stacked card; at/above md the DataTable is
 * unchanged. Both presentations are in the DOM, switched by CSS, so this spec proves in a real
 * Chromium what jsdom cannot (tests/unit/FinancialMetricsCards.spec.tsx proves content parity on
 * the DOM; this spec proves it on the RENDERED layouts):
 *
 *   - exactly one layout is rendered at every width, and the switch is at 767 → 768 with no mixed state;
 *   - the inactive layout contributes nothing to the accessibility tree (aria snapshot), takes no Tab
 *     stop, and the page carries no duplicate ids;
 *   - the caption / accessible name is exposed by whichever layout is active (both caption variants);
 *   - the facts read from the active layout equal the facts read from the hidden one and the served
 *     rows (names, values, change string + direction + tone + computed colour, per-ADS, takeaways,
 *     both kinds of provenance chip), for the named 7-row fixture and the data variants;
 *   - for the named fixture at 390x844 the Total net sales value, change, takeaway and its provenance
 *     chip are visible in one viewport, the Current / Prior / Change groups sit on one line, nothing
 *     scrolls sideways and no blank run is taller than 64px; no card text computes an ellipsis, a line
 *     clamp, nowrap or a clipping height; long values (and an unbreakable token) wrap instead;
 *   - 320px wide and a 125% root font size reflow without horizontal overflow or clipping;
 *   - the layouts sit in one wrapper, so the md+ table keeps its position (no sibling margin);
 *   - a card's provenance chip still reaches the EN-01 sheet and returns focus on close;
 *   - the landing page's sample table (the non-bare caller) stacks the same way.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside
 * the browser with page.route. The summary is the public Apple FY2025 10-K fixture with its metrics
 * block replaced by fixtures/filing-3-metric-rows.json — the seven production rows copied verbatim
 * from the critique harness's cache, so the "named fixture" here is the content the harness measures.
 * DOM, computed-style and keyboard probes only: this is not a screen-reader test.
 */

type Row = {
  metric: string
  current_period: string
  prior_period: string
  change_display?: string | null
  change_direction?: 'up' | 'down' | 'flat' | null
  change_tone?: 'gain' | 'loss' | 'flat' | null
  commentary?: string
  source_url?: string | null
  source_verified?: boolean | null
  xbrl_concept?: string | null
  per_ads?: unknown
  commentary_evidence?: { verified: boolean } | null
}
type Summary = { rendered_sections: { id: string; blocks: { kind: string; metric_rows?: Row[] }[] }[] }

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const BASE = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-summary.json'), 'utf8')) as Summary
const ROWS = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-metric-rows.json'), 'utf8')) as Row[]
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
const CARDS = `${SECTION} [data-metrics-layout="cards"]`
const CARD = `${SECTION} [data-metric-card]`
const TABLE = `${SECTION} [data-metrics-layout="table"]`
const CAPTION_WITH = 'Financial highlights: current period, prior period, change, and investor takeaway per metric'
const CAPTION_WITHOUT = 'Financial highlights: current period and investor takeaway per metric'

/** The fixture with its metrics block replaced (the data variants are derived from the 7 rows). */
const withRows = (rows: Row[]): Summary => {
  const s = structuredClone(BASE)
  const block = s.rendered_sections.flatMap((sec) => sec.blocks).find((b) => b.kind === 'metrics')!
  block.metric_rows = rows
  return s
}
const NO_COMPARATIVES: Row[] = ROWS.map(({ change_display: _d, change_direction: _r, change_tone: _t, ...row }) => ({ ...row, prior_period: '' }))
const NO_COMMENTARY: Row[] = ROWS.map((row) => ({ ...row, commentary: '', commentary_evidence: null }))
const NO_EVIDENCE: Row[] = ROWS.map((row) => ({ ...row, commentary_evidence: null }))
// Long values that survive the client formatter (a leading non-numeric token renders verbatim) and
// an unbreakable 60-character token in the change string.
const UNBREAKABLE = 'x'.repeat(60)
const LONG: Row[] = [
  {
    ...ROWS[0],
    metric: 'Revenue from contracts with customers, excluding assessed taxes, continuing operations only',
    current_period: 'Restated to $1,234,567,890,123 after the discontinued-operations reclassification',
    prior_period: 'Previously reported $987,654,321,098 before the reclassification',
    change_display: `+25.0% (constant currency +23.4%, excluding the 53rd week) ${UNBREAKABLE}`,
  },
  ...ROWS.slice(1),
]

type Theme = 'light' | 'dark'
type Rect = { x: number; y: number; w: number; h: number }

async function answerApi(page: Page, baseURL: string, summary: Summary) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (pathname) {
      case '/api/filings/3':
        return json(200, FILING)
      case '/api/summaries/filing/3':
        return json(200, summary)
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
async function openFiling(page: Page, baseURL: string, { theme = 'light', rows = ROWS }: { theme?: Theme; rows?: Row[] } = {}) {
  await answerApi(page, baseURL, withRows(rows))
  await page.addInitScript((theme: Theme) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      localStorage.setItem('en:copilot-coachmark-v1', '1')
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  await expect(page.locator(SECTION)).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

const rectOf = (loc: Locator): Promise<Rect> =>
  loc.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { x: r.x, y: r.y, w: r.width, h: r.height }
  })
const viewport = (page: Page) => page.evaluate(() => ({ w: window.innerWidth, h: window.innerHeight }))
/** Inside the viewport AND below the sticky chrome (content under the header / section nav is not visible). */
const inside = (r: Rect, vp: { w: number; h: number; top?: number }) =>
  r.x >= 0 && r.y >= (vp.top ?? 0) - 0.5 && r.x + r.w <= vp.w + 0.5 && r.y + r.h <= vp.h + 0.5
/** The bottom edge of whatever sticky/fixed chrome spans the top of the viewport (site header, mobile section nav). */
const chromeBottom = (page: Page) =>
  page.evaluate(() => {
    let bottom = 0
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('header, nav, div'))) {
      const pos = getComputedStyle(el).position
      if (pos !== 'sticky' && pos !== 'fixed') continue
      const r = el.getBoundingClientRect()
      if (r.top <= 1 && r.height > 0 && r.width >= innerWidth / 2) bottom = Math.max(bottom, r.bottom)
    }
    return bottom
  })
/** Scroll so the element's top sits 8px under the sticky chrome. */
async function settleUnderChrome(page: Page, loc: Locator) {
  const top = await chromeBottom(page)
  await loc.evaluate((el, top) => window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - top - 8, behavior: 'instant' }), top)
  await page.waitForTimeout(100)
  return Math.max(top, await chromeBottom(page))
}

/**
 * Everything the acceptance row says must be equal across layouts, read the same way from both —
 * the browser twin of the unit spec's `factsOf` (same anchors), plus each layout's rendering state.
 */
const probe = (page: Page) =>
  page.evaluate((SECTION) => {
    const sec = document.querySelector(SECTION)!
    const q = (sel: string, root: ParentNode = sec) => Array.from(root.querySelectorAll<HTMLElement>(sel))
    const vis = (e: Element) => e.getClientRects().length > 0
    const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim()
    const facts = (root: HTMLElement) => ({
      caption: root.matches('ul') ? root.getAttribute('aria-label') : (root.querySelector('caption')?.textContent ?? null),
      rows: root.matches('ul') ? q('[data-metric-card]', root).length : q('tbody tr', root).length,
      names: q('[data-metric-field="name"]', root).map((e) => text(e.firstElementChild)),
      currents: q('[data-metric-field="current"]', root).map(text),
      perAds: q('[data-metric-field="per-ads"]', root).map(text),
      priors: q('[data-metric-field="prior"]', root).map(text),
      changes: q('[data-metric-field="change"]', root).map((e) => ({
        text: text(e),
        direction: e.dataset.direction ?? null,
        tone: e.dataset.tone ?? null,
        color: getComputedStyle(e.closest('td, dd') ?? e).color,
      })),
      takeaways: q('[data-metric-field="takeaway"]', root).map((e) => text(e.firstElementChild)),
      xbrlChips: q('[data-metric-field="name"] [aria-label^="Source: "]', root).map((e) => e.getAttribute('aria-label')),
      takeawayChips: q('[data-metric-field="takeaway"] [aria-label^="Source: "]', root).map((e) => e.getAttribute('aria-label')),
    })
    const state = (root: HTMLElement) => ({
      display: getComputedStyle(root).display,
      marginTop: getComputedStyle(root).marginTop,
      visibleNames: q('[data-metric-field="name"]', root).filter(vis).length,
      focusables: q('a, button, [tabindex]', root).filter((e) => e.tabIndex >= 0 && vis(e)).length,
      valueFontSize: parseFloat(getComputedStyle(root.querySelector('[data-metric-field="current"]')!.closest('td, dd')!).fontSize),
    })
    const cards = sec.querySelector<HTMLElement>('[data-metrics-layout="cards"]')!
    const table = sec.querySelector<HTMLElement>('[data-metrics-layout="table"]')!
    const ids = Array.from(document.querySelectorAll('[id]')).map((e) => e.id)
    return {
      cards: facts(cards),
      table: facts(table),
      state: { cards: state(cards), table: state(table) },
      wrapperMarginTop: getComputedStyle(cards.parentElement!).marginTop,
      dupIds: ids.filter((id, i) => ids.indexOf(id) !== i),
      hOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      sectionHOverflow: sec.scrollWidth > sec.clientWidth + 1,
    }
  }, SECTION)

/** The counts the acceptance names, derived from the served rows (no client math here either). */
const servedVector = (rows: Row[], hasComparatives: boolean) => ({
  names: rows.length,
  currents: rows.length,
  priors: hasComparatives ? rows.length : 0,
  changes: hasComparatives ? rows.length : 0,
  takeaways: rows.length,
  xbrlChips: rows.filter((r) => r.source_url).length,
  takeawayChips: rows.filter((r) => r.commentary_evidence).length,
  perAds: rows.filter((r) => r.per_ads).length,
})
const vectorOf = (f: Awaited<ReturnType<typeof probe>>['cards']) => ({
  names: f.names.length,
  currents: f.currents.length,
  priors: f.priors.length,
  changes: f.changes.length,
  takeaways: f.takeaways.length,
  xbrlChips: f.xbrlChips.length,
  takeawayChips: f.takeawayChips.length,
  perAds: f.perAds.length,
})

/** Parity of the two layouts with each other and with the served rows; the active one rendered alone. */
async function expectParity(page: Page, active: 'cards' | 'table', rows: Row[], hasComparatives = true) {
  const p = await probe(page)
  expect(p.cards, 'the facts read from the cards equal the facts read from the table').toEqual(p.table)
  expect(vectorOf(p.cards)).toEqual(servedVector(rows, hasComparatives))
  expect(p.cards.caption).toBe(hasComparatives ? CAPTION_WITH : CAPTION_WITHOUT)
  expect(p.cards.names).toEqual(rows.map((r) => r.metric))
  expect(p.cards.takeaways).toEqual(rows.map((r) => r.commentary || '-'))
  if (hasComparatives) {
    expect(p.cards.changes.map((c) => [c.text, c.direction, c.tone])).toEqual(
      rows.map((r) => (r.change_display ? [r.change_display, r.change_direction ?? null, r.change_tone ?? null] : ['—', null, null])),
    )
  }
  const inactive = active === 'cards' ? 'table' : 'cards'
  expect(p.state[active].display).not.toBe('none')
  expect(p.state[inactive].display).toBe('none')
  expect(p.state[active].visibleNames, 'one rendered name per row — never 0, never both layouts').toBe(rows.length)
  expect(p.state[inactive].visibleNames).toBe(0)
  expect(p.state[inactive].focusables, 'the hidden layout offers no focusable control').toBe(0)
  // one wrapper for both layouts: neither inherits a sibling margin from the section body's space-y
  expect(p.wrapperMarginTop).toBe('0px')
  expect(p.state.cards.marginTop).toBe('0px')
  expect(p.state.table.marginTop).toBe('0px')
  // card figures are never smaller than the table's
  expect(p.state.cards.valueFontSize).toBeGreaterThanOrEqual(p.state.table.valueFontSize)
  expect(p.dupIds).toEqual([])
  expect(p.hOverflow, 'no page-level sideways scroll').toBe(false)
  expect(p.sectionHOverflow, 'no sideways scroll inside the section').toBe(false)
  return p
}

/** Exactly one of the two layouts is rendered (display) at the current width. */
async function expectSingleLayout(page: Page, active: 'cards' | 'table') {
  if (active === 'cards') {
    await expect(page.locator(CARDS)).toBeVisible()
    await expect(page.locator(TABLE)).toBeHidden()
  } else {
    await expect(page.locator(`${TABLE} table`)).toBeVisible()
    await expect(page.locator(CARDS)).toBeHidden()
  }
}

/** The aria snapshot of the section names the active layout with the caption and omits the other. */
async function expectAccessibleLayout(page: Page, active: 'cards' | 'table', caption = CAPTION_WITH) {
  const snapshot = await page.locator(SECTION).ariaSnapshot()
  const hasList = snapshot.includes(`list "${caption}"`)
  const hasTable = snapshot.includes(`table "${caption}"`)
  expect(hasList, `a list named by the caption in the aria snapshot:\n${snapshot}`).toBe(active === 'cards')
  expect(hasTable, `a table named by the caption in the aria snapshot:\n${snapshot}`).toBe(active === 'table')
  // the hidden layout contributes none of its own nodes: the cards' terms and definitions, or the
  // table's column headers, rows and cells
  if (active === 'cards') {
    expect(snapshot, `no table nodes while the cards are active:\n${snapshot}`).not.toMatch(/columnheader|- cell|- row /)
    expect(snapshot).toMatch(/- term: Current period/)
    expect(snapshot).toMatch(/- definition/)
  } else {
    expect(snapshot, `no card nodes while the table is active:\n${snapshot}`).not.toMatch(/- term|- definition|- listitem/)
    expect(snapshot).toMatch(/columnheader "Current Period"/)
  }
  return snapshot
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

/** Computed-style facts for every text holder in a card (chips keep their own text-data-xs type). */
const cardTextStyles = (card: Locator) =>
  card.evaluate((root) => {
    const out: { tag: string; text: string; whiteSpace: string; overflowWrap: string; textOverflow: string; lineClamp: string; clipped: boolean; fontSize: number; floor: number }[] = []
    for (const el of Array.from(root.querySelectorAll<HTMLElement>('*'))) {
      if (el.closest('svg') || el.closest('a, button') || el.closest('.sr-only')) continue // chips keep their own type; sr-only text is visually hidden by design (1px, nowrap, clipped)
      const ownText = Array.from(el.childNodes).some((n) => n.nodeType === Node.TEXT_NODE && (n.textContent ?? '').trim())
      if (!ownText) continue
      const cs = getComputedStyle(el)
      // labels (dt) and the per-ADS annotation (PerAdsNote, text-xs by design) are 12px; everything
      // else is the table's 14px body
      const annotation = el.tagName === 'DT' || !!el.closest('[data-metric-field="per-ads"]')
      const block = cs.display !== 'inline' // inline boxes report no scroll size; clipping is a block-level fact
      out.push({
        tag: el.tagName.toLowerCase(),
        text: (el.textContent ?? '').trim().slice(0, 30),
        whiteSpace: cs.whiteSpace,
        overflowWrap: cs.overflowWrap,
        textOverflow: cs.textOverflow,
        lineClamp: cs.webkitLineClamp,
        clipped: block && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1),
        fontSize: parseFloat(cs.fontSize),
        floor: annotation ? 12 : 14,
      })
    }
    return out
  })
async function expectNothingClippedIn(card: Locator, label = '') {
  for (const s of await cardTextStyles(card)) {
    expect(s.whiteSpace, `${label}${s.tag} "${s.text}" white-space`).not.toMatch(/nowrap|pre$/)
    expect(s.overflowWrap, `${label}${s.tag} "${s.text}" overflow-wrap`).toBe('anywhere')
    expect(s.textOverflow, `${label}${s.tag} "${s.text}" text-overflow`).not.toBe('ellipsis')
    expect(s.lineClamp, `${label}${s.tag} "${s.text}" line-clamp`).toBe('none')
    expect(s.clipped, `${label}${s.tag} "${s.text}" is clipped`).toBe(false)
    expect(s.fontSize, `${label}${s.tag} "${s.text}" font-size`).toBeGreaterThanOrEqual(s.floor)
  }
}

/** The `<dl>` groups (Current / Prior / Change) and their terms and definitions: one line = one distinct top each. */
const lineTops = (card: Locator) =>
  card.evaluate((root) => {
    const tops = (sel: string) => Array.from(new Set(Array.from(root.querySelectorAll(sel)).map((el) => Math.round(el.getBoundingClientRect().top))))
    return { groups: tops('dl > div'), terms: tops('dt'), definitions: tops('dd') }
  })

/** No run of blank space taller than 64px between the card's visible blocks, and none inside its padding. */
const blankRuns = (card: Locator) =>
  card.evaluate((root) => {
    const r = root.getBoundingClientRect()
    const blocks = Array.from(root.children).map((c) => c.getBoundingClientRect()).filter((b) => b.height > 0)
    const gaps: number[] = [blocks[0].top - r.top]
    for (let i = 1; i < blocks.length; i++) gaps.push(blocks[i].top - blocks[i - 1].bottom)
    gaps.push(r.bottom - blocks[blocks.length - 1].bottom)
    const over = Array.from(root.querySelectorAll<HTMLElement>('dd, [data-metric-field="change"]')).filter((el) => el.scrollWidth > el.clientWidth + 1).length
    return { gaps: gaps.map((g) => Math.round(g)), height: Math.round(r.height), hScroll: root.scrollWidth > root.clientWidth + 1, overflowingValues: over }
  })
async function expectCardsWellFormed(page: Page, label = '') {
  const cards = await page.locator(CARD).all()
  expect(cards.length).toBeGreaterThan(0)
  for (const card of cards) {
    const runs = await blankRuns(card)
    expect(runs.hScroll, `${label}card scrolls sideways`).toBe(false)
    expect(runs.overflowingValues, `${label}a value or change line overflows its box`).toBe(0)
    for (const g of runs.gaps) expect(g, `${label}blank run in a card: ${runs.gaps}`).toBeLessThanOrEqual(64)
    await expectNothingClippedIn(card, label)
  }
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`phone 390x844, ${theme}`, () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

    test('one card per metric with parity to the hidden table and the served rows; Total net sales fits one viewport on one value line; nothing clipped or scrolled sideways', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      await expectSingleLayout(page, 'cards')
      await expect(page.locator(CARD)).toHaveCount(ROWS.length)
      const p = await expectParity(page, 'cards', ROWS)
      // computed tone colour agrees between the card's dd and the table's td, row by row (per theme)
      expect(p.cards.changes.map((c) => c.color)).toEqual(p.table.changes.map((c) => c.color))

      const first = page.locator(CARD).first()
      const top = await settleUnderChrome(page, first)
      const vp = { ...(await viewport(page)), top }
      const cardRect = await rectOf(first)
      expect(inside(cardRect, vp), `the whole first card fits one viewport (card ${JSON.stringify(cardRect)}, chrome bottom ${top})`).toBe(true)
      // the named fixture's Current / Prior / Change groups are one line at 390px
      const tops = await lineTops(first)
      expect(tops.groups, `the value row wrapped: group tops ${tops.groups}`).toHaveLength(1)
      expect(tops.terms).toHaveLength(1)
      expect(tops.definitions).toHaveLength(1)
      // value, change, takeaway and its chip, each inside the viewport at once
      const value = first.locator('[data-metric-field="current"]')
      const change = first.locator('[data-metric-field="change"]')
      // the takeaway text is the field's first child; the evidence chip's wrapper is a span too
      const takeaway = first.locator('[data-metric-field="takeaway"] > span:first-child')
      const chip = first.getByRole('button', { name: 'Source: Verified in filing' })
      for (const [label, loc] of [['value', value], ['change', change], ['takeaway', takeaway], ['chip', chip]] as const) {
        await expect(loc).toBeVisible()
        expect(inside(await rectOf(loc), vp), `${label} inside the viewport`).toBe(true)
      }
      await expect(takeaway).toHaveText(ROWS[0].commentary!)
      await expect(change).toHaveText(ROWS[0].change_display!)
      await expect(first.getByRole('term')).toHaveText(['Current period', 'Prior period', 'Change'])
      await expectCardsWellFormed(page)
      await expectAccessibleLayout(page, 'cards')
      await expectTabStopsOnlyIn(page, 'cards')
    })

    test('a card chip is a real control: tapping the takeaway chip opens the EN-01 sheet, Escape returns focus to it', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      const chip = page.locator(CARD).first().getByRole('button', { name: 'Source: Verified in filing' })
      await chip.scrollIntoViewIfNeeded()
      await chip.tap()
      const sheet = page.getByRole('dialog', { name: 'Source detail' })
      await expect(sheet).toBeVisible()
      await expect(sheet.getByRole('link', { name: /open in sec edgar/i })).toHaveAttribute('href', /aapl-20250927\.htm/)
      await page.keyboard.press('Escape')
      await expect(sheet).toHaveCount(0)
      await expect(chip).toBeFocused()
      expect(await probe(page).then((p) => p.dupIds)).toEqual([])
    })
  })
}

test.describe('the switch is at 767 → 768 with no mixed state', () => {
  test.use({ viewport: { width: 767, height: 1024 } })

  test('cards at 767, the unchanged table at 768 (same facts, headers in order, no sibling margin)', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await expectSingleLayout(page, 'cards')
    const at767 = await expectParity(page, 'cards', ROWS)
    await expectAccessibleLayout(page, 'cards')
    await expectTabStopsOnlyIn(page, 'cards')
    const first = page.locator(CARD).first()
    await first.scrollIntoViewIfNeeded()
    expect((await lineTops(first)).groups).toHaveLength(1)

    await page.setViewportSize({ width: 768, height: 1024 })
    await expectSingleLayout(page, 'table')
    const at768 = await expectParity(page, 'table', ROWS)
    expect(at768.table.names).toEqual(at767.cards.names) // the same summary, both widths
    await expectAccessibleLayout(page, 'table')
    await expectTabStopsOnlyIn(page, 'table')
    const table = page.locator(`${TABLE} table`)
    await expect(table.locator('thead th')).toHaveText(['Metric', 'Current Period', 'Prior Period', 'Change', 'Investor Takeaway'])
    await expect(table.locator('tbody tr')).toHaveCount(ROWS.length)
    await expect(table.locator('caption')).toHaveText(CAPTION_WITH)
    // the table starts exactly at the section body's content edge: the hidden list earns it no margin
    const offset = await page.evaluate(
      ({ TABLE, SECTION }) => {
        const t = document.querySelector(TABLE)!
        const body = t.closest(`${SECTION} > *:not(header)`) as HTMLElement | null
        const parent = t.parentElement!.parentElement!
        const padTop = parseFloat(getComputedStyle(parent).paddingTop)
        return { body: !!body, delta: t.getBoundingClientRect().top - (parent.getBoundingClientRect().top + padTop) }
      },
      { TABLE, SECTION },
    )
    expect(Math.abs(offset.delta)).toBeLessThanOrEqual(0.5)
  })
})

test.describe('desktop 1440x900', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('the table alone is rendered and reachable; the hidden cards add no stops, nodes or ids and still carry the same facts', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await expectSingleLayout(page, 'table')
    await expectParity(page, 'table', ROWS)
    await expectAccessibleLayout(page, 'table')
    await expectTabStopsOnlyIn(page, 'table')
    const table = page.locator(`${TABLE} table`)
    await expect(table.locator('tbody tr')).toHaveCount(ROWS.length)
    await expect(table.locator('tbody tr').first()).toContainText(ROWS[0].change_display!)
  })
})

test.describe('narrow 320x568 and enlarged text', () => {
  test.use({ viewport: { width: 320, height: 568 }, isMobile: true, hasTouch: true })

  test('cards reflow at 320px and at a 125% root font size without sideways scroll or clipping (wrapping is the allowed outcome)', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await expectSingleLayout(page, 'cards')
    for (const rootFont of ['', '20px']) {
      await page.evaluate((size) => {
        document.documentElement.style.fontSize = size
      }, rootFont)
      await page.locator(CARD).first().scrollIntoViewIfNeeded()
      const label = `(root font ${rootFont || 'default'}) `
      await expectCardsWellFormed(page, label)
      for (const card of await page.locator(CARD).all()) {
        const r = await rectOf(card)
        expect(r.x).toBeGreaterThanOrEqual(0)
        expect(r.x + r.w).toBeLessThanOrEqual(320.5)
      }
      // The section never scrolls sideways. The page as a whole is checked at the default size only:
      // at a 20px root font the site header's own controls overflow 320px (pre-existing, not the cards).
      const section = await page.locator(SECTION).evaluate((el) => el.scrollWidth <= el.clientWidth + 1)
      expect(section, `${label}the section scrolls sideways`).toBe(true)
      if (!rootFont) expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), 'no page-level sideways scroll').toBe(true)
      // one line is NOT asserted here: the strip may wrap at 320px or under a larger root font
      test.info().annotations.push({ type: `value-row-lines ${label.trim()}`, description: String((await lineTops(page.locator(CARD).first())).groups.length) })
    }
  })
})

test.describe('data variants at 390x844', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

  test('no comparatives: no Prior / Change group, cell or chip in either layout; the short caption names the list and the table', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, { rows: NO_COMPARATIVES })
    await expectSingleLayout(page, 'cards')
    await expectParity(page, 'cards', NO_COMPARATIVES, false)
    const snapshot = await expectAccessibleLayout(page, 'cards', CAPTION_WITHOUT)
    expect(snapshot).not.toMatch(/Prior period|- term: Change/)
    await expect(page.locator(CARD).first().getByRole('term')).toHaveText(['Current period'])
    expect(await page.locator(`${TABLE} th`).count()).toBe(3)
    expect(await page.locator(`${SECTION} [data-metric-field="prior"], ${SECTION} [data-metric-field="change"]`).count()).toBe(0)
    await expectCardsWellFormed(page)
  })

  test('no commentary and no evidence: the "-" placeholder and no takeaway chip, nothing invented', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, { rows: NO_COMMENTARY })
    await expectSingleLayout(page, 'cards')
    const p = await expectParity(page, 'cards', NO_COMMENTARY)
    expect(p.cards.takeaways).toEqual(NO_COMMENTARY.map(() => '-'))
    expect(p.cards.takeawayChips).toEqual([])
    await expect(page.locator(`${SECTION} [aria-label="Source: Verified in filing"]`)).toHaveCount(0)

    await openFiling(page, baseURL!, { rows: NO_EVIDENCE })
    const q = await expectParity(page, 'cards', NO_EVIDENCE)
    expect(q.cards.takeaways).toEqual(NO_EVIDENCE.map((r) => r.commentary))
    expect(q.cards.takeawayChips).toEqual([])
    expect(q.cards.xbrlChips).toHaveLength(ROWS.filter((r) => r.source_url).length)
  })

  test('long values and an unbreakable token wrap rather than clip or scroll — the groups drop to new lines, the strings stay verbatim', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, { rows: LONG })
    await expectSingleLayout(page, 'cards')
    const p = await expectParity(page, 'cards', LONG)
    expect(p.cards.currents[0]).toBe(LONG[0].current_period)
    expect(p.cards.priors[0]).toBe(LONG[0].prior_period)
    expect(p.cards.changes[0].text).toBe(LONG[0].change_display)
    const first = page.locator(CARD).first()
    await first.scrollIntoViewIfNeeded()
    const tops = await lineTops(first)
    expect(tops.groups.length, `the long value row wrapped onto more than one line: ${tops.groups}`).toBeGreaterThan(1)
    await expectCardsWellFormed(page)
    // the unbreakable token broke inside its box rather than widening the card or the page
    const change = first.locator('[data-metric-field="change"]')
    const changeBox = await change.evaluate((el) => {
      const dd = el.closest('dd')!
      const rects = Array.from(el.getClientRects())
      return { lines: rects.length, ddScroll: dd.scrollWidth, ddClient: dd.clientWidth, cardClient: el.closest('[data-metric-card]')!.clientWidth }
    })
    expect(changeBox.lines).toBeGreaterThan(1)
    expect(changeBox.ddScroll).toBeLessThanOrEqual(changeBox.ddClient + 1)
    expect(changeBox.ddClient).toBeLessThanOrEqual(changeBox.cardClient)
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
    await expect(evidence.locator('[data-metrics-layout="cards"]')).toBeVisible()
    await expect(evidence.locator('[data-metrics-layout="table"]')).toBeHidden()
    await expect(evidence.getByRole('heading', { name: 'Financial Highlights' })).toBeVisible()
    await expect(evidence.getByText(/Each row carries its own source label/)).toBeVisible()
    for (const card of await evidence.locator('[data-metric-card]').all()) {
      expect((await blankRuns(card)).hScroll).toBe(false)
    }
    await page.setViewportSize({ width: 1440, height: 900 })
    await expect(evidence.locator('[data-metrics-layout="table"] table')).toBeVisible()
    await expect(evidence.locator('[data-metrics-layout="cards"]')).toBeHidden()
  })
})
