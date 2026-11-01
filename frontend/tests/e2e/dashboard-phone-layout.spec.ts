import { test, expect, type Page } from '@playwright/test'

/**
 * Phone-width layout guards for the signed-in /dashboard and /dashboard/watchlist.
 *
 * 1. No sideways scroll: the dashboard's grids give their phone track an explicit minmax(0, 1fr),
 *    so a long company name beside a status badge truncates instead of widening the page.
 * 2. A stable header: the SecondaryHeader subtitle ("Welcome back, <name or email>") never sizes
 *    the header row, so the page below sits at the same offset whatever the name's length.
 * 3. Room for the name: below sm the back link is its caret alone (still named by its label, with a
 *    44px target), so a typical name fits whole beside the title at 375px.
 * 4. Watchlist insights cards: an explicit phone track, and below sm the ticker and status badges
 *    wrap under the company name instead of widening the card.
 * 5. What changed's chips (E268): under 200% text a chip's figure moves under its label, so the chip
 *    narrows to its row instead of passing its card or scrolling the page, and its text stays inside it.
 * 6. What changed's header (E272): where the card is narrower than 21rem the date column moves under the
 *    company line and the name wraps whole, and the call to action keeps its arrow on its last word.
 * 7. The arrow links (E274): where "See all N companies" or "Open watchlist insights" wraps under 200% text,
 *    the arrow keeps with the last word, the link paints one box for its focus ring, and the words keep
 *    the link's 0.25rem inset, clear of the ring's rounded corners.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md). These specs still need
 * none: the API is answered inside the browser with page.route fixtures, and the middleware's
 * session gate is satisfied by its non-credential presence cookie.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin

type Who = { full_name: string | null; email: string }

const SHORT: Who = { full_name: 'Al', email: 'al@example.com' }
const TYPICAL: Who = { full_name: 'Jordan Whitaker', email: 'jordan@example.com' }
const LONG: Who = { full_name: 'Maximilian Alexander Featherstonehaugh-Worthington', email: 'max@example.com' }
const EMAIL_ONLY: Who = { full_name: null, email: 'maximilian.featherstonehaugh@example-enterprise.com' }

const COMPANIES: Array<[string, string, string]> = [
  ['TSM', 'Taiwan Semiconductor Manufacturing Company Limited', 'ready'],
  ['IBM', 'International Business Machines Corporation', 'generating:summarizing'],
  ['BRK.B', 'Berkshire Hathaway Inc.', 'error'],
  ['AAPL', 'Apple Inc.', 'missing'],
  // A real EDGAR name whose one word ("Telecommunications", ~227px at text-2xl) is wider than a
  // 320px phone's watchlist name column.
  ['SHEN', 'SHENANDOAH TELECOMMUNICATIONS CO/VA/', 'ready'],
]

function fixture(pathname: string, who: Who): unknown {
  switch (pathname) {
    case '/api/auth/me':
      return { id: 1, email: who.email, full_name: who.full_name, is_pro: false, is_beta: false, is_admin: false, email_verified: true }
    case '/api/subscriptions/usage':
      return { summaries_used: 2, summaries_limit: 5, is_pro: false, month: '2026-10', qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3, analysis_used: 0, analysis_limit: 0 }
    case '/api/subscriptions/subscription':
      return { is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null, plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false }
    case '/api/watchlist/insights':
      return COMPANIES.map(([ticker, name, status], i) => ({
        company: { id: i + 1, ticker, name },
        latest_filing: { id: 100 + i, filing_type: '10-K', filing_date: '2026-08-03', period_end_date: '2026-06-30', summary_id: null, summary_status: status, summary_created_at: null, summary_updated_at: null, needs_regeneration: status === 'missing' },
        total_filings: 12,
      }))
    case '/api/dashboard/feed':
      return {
        items: COMPANIES.slice(0, 2).map(([ticker, name], i) => ({
          filing_id: 100 + i, accession_number: null, company: { id: i + 1, ticker, name }, filing_type: '10-Q',
          filing_date: '2026-08-03', period_end_date: '2026-06-30', summary_id: null, summary_status: 'ready', what_changed: null,
        })),
      }
    case '/api/saved-summaries/':
    case '/api/watchlist/':
      return []
    default:
      return undefined
  }
}

/** Responses that replace the fixture's for one test, by path. */
type Overrides = Record<string, unknown>

async function signIn(page: Page, who: Who, baseURL: string, overrides: Overrides = {}) {
  const origin = new URL(baseURL).origin
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const pathname = new URL(route.request().url()).pathname
    const body = pathname in overrides ? overrides[pathname] : fixture(pathname, who)
    return body === undefined
      ? route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } })
      : route.fulfill({ status: 200, headers: cors, json: body })
  })
}

async function openDashboard(page: Page, who: Who, baseURL: string) {
  await signIn(page, who, baseURL)
  await page.goto('/dashboard')
  await expect(page.getByRole('link', { name: 'Open watchlist insights' })).toBeVisible()
  await expect(page.getByText('Latest report').first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

for (const width of [320, 375, 390, 1440]) {
  test(`dashboard has no horizontal scroll at ${width}px with long company names`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await openDashboard(page, LONG, baseURL!)
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(scrollWidth).toBe(clientWidth)
    // The longest name truncates inside its row rather than widening it.
    const name = page.getByText('Taiwan Semiconductor Manufacturing Company Limited').last()
    const box = await name.boundingBox()
    expect(box!.x + box!.width).toBeLessThanOrEqual(clientWidth)
    // Beside a status badge such as "No summary yet" a name column keeps a few characters (the row
    // wraps its status cluster instead) rather than collapsing under the badge.
    const nameWidths = await page
      .locator('a[href^="/company/"]:has(+ div button[aria-label^="Remove "]) .truncate.font-semibold')
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().width))
    expect(nameWidths).toHaveLength(COMPANIES.length)
    for (const w of nameWidths) expect(w).toBeGreaterThanOrEqual(24)
  })
}

test('dashboard header height does not depend on the greeting at 375px', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 375, height: 900 })
  const offsets: Array<{ header: number; main: number }> = []
  for (const who of [SHORT, LONG, EMAIL_ONLY]) {
    await page.unrouteAll({ behavior: 'ignoreErrors' })
    await openDashboard(page, who, baseURL!)
    offsets.push(
      await page.evaluate(() => {
        const title = [...document.querySelectorAll('h1')].find((h) => h.textContent === 'Dashboard')!
        const header = title.closest('header')!
        return {
          header: header.getBoundingClientRect().height,
          main: document.querySelector('main')!.getBoundingClientRect().top + window.scrollY,
        }
      }),
    )
  }
  expect(offsets[1]).toEqual(offsets[0])
  expect(offsets[2]).toEqual(offsets[0])
})

test('a typical name fits beside an icon-only back link at 375px', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 375, height: 900 })
  await openDashboard(page, TYPICAL, baseURL!)
  // Measure the truncating <p> (an inline span reports no client width).
  const greeting = page.locator('header p', { hasText: 'Welcome back, Jordan Whitaker' })
  expect(await greeting.evaluate((el) => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth)).toBe(true)
  const back = page.getByRole('link', { name: 'Back to home' })
  await expect(back).toBeVisible()
  const box = (await back.boundingBox())!
  expect(box.width).toBeGreaterThanOrEqual(44)
  expect(box.height).toBeGreaterThanOrEqual(44)
  expect(box.x).toBeGreaterThanOrEqual(0)
})

for (const width of [320, 375, 390, 1440]) {
  test(`watchlist insights has no horizontal scroll at ${width}px with long company names`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await signIn(page, LONG, baseURL!)
    await page.goto('/dashboard/watchlist')
    const names = page.locator('main h2')
    await expect(names).toHaveCount(COMPANIES.length)
    await page.evaluate(() => document.fonts.ready)
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(scrollWidth).toBe(clientWidth)
    // Every name's text fits its own box (a long word breaks rather than spilling past the card),
    // the box sits inside the viewport, and it is not squeezed narrower than the name needs on
    // one line, up to 100px.
    const measured = await names.evaluateAll((els) =>
      els.map((el) => {
        const probe = el.cloneNode(true) as HTMLElement
        probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;width:auto;min-width:0'
        el.parentElement!.appendChild(probe)
        const natural = probe.getBoundingClientRect().width
        probe.remove()
        const box = el.getBoundingClientRect()
        return { right: box.right, width: box.width, natural, spill: el.scrollWidth - el.clientWidth }
      }),
    )
    for (const m of measured) {
      expect(m.spill).toBeLessThanOrEqual(0)
      expect(m.right).toBeLessThanOrEqual(clientWidth)
      expect(m.width).toBeGreaterThanOrEqual(Math.min(100, m.natural - 1))
    }
  })
}

/** Chromium's own text setting doubled (standard 32, fixed 26), as reflow-200.spec.ts doubles it, confirmed taken. */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('32px')
}

/** What changed's chips (E268, chief design's review of #1877): a typical card's three and a bank's four, the bank's
    "Noninterest income +103.9%" the longest, with the EPS name the dashboard took in E259 ("EPS (diluted)"). Under 200%
    text a chip that could not move its figure under its label held itself at least 267px wide: the bank card made the
    page scroll at 320 and 360px, and a typical card's chips passed its border at 320, 340 and 1024px. */
const CHANGED: Array<{ ticker: string; name: string; items: Array<[string, string, 'up' | 'down', string, 'gain' | 'loss']> }> = [
  { ticker: 'AAPL', name: 'Apple Inc.', items: [
    ['revenue', 'Revenue', 'up', '+6.4%', 'gain'],
    ['net_income', 'Net income', 'down', '−3.0%', 'loss'],
    ['eps_diluted', 'EPS (diluted)', 'up', '+2.1%', 'gain'],
  ] },
  { ticker: 'JPM', name: 'JPMorgan Chase & Co.', items: [
    ['net_interest_income', 'Net interest income', 'up', '+4.2%', 'gain'],
    ['noninterest_income', 'Noninterest income', 'up', '+103.9%', 'gain'],
    ['net_income', 'Net income', 'up', '+12.0%', 'gain'],
    ['eps_diluted', 'EPS (diluted)', 'up', '+14.5%', 'gain'],
  ] },
]
const CHANGED_FEED = {
  // No watchlist rows: under 200% text a row's status cluster passes a phone's width on its own (E273), so with them the
  // page's scroll would not be the chips'. The cards' headers stay, and keep inside their cards (E272, below).
  '/api/watchlist/insights': [],
  '/api/dashboard/feed': {
    items: [
      ...CHANGED.map(({ ticker, name, items }, i) => ({
        filing_id: 200 + i, accession_number: null, company: { id: 50 + i, ticker, name }, filing_type: '10-Q',
        filing_date: '2026-08-03', period_end_date: '2026-06-30', summary_id: 300 + i, summary_status: 'ready',
        what_changed: {
          headline: '', data_quality: 'ok',
          items: items.map(([metric, label, direction, display, tone]) => ({ metric, label, direction, pct: null, current: 1, prior: 1, display, tone })),
        },
      })),
      // E272's long name, whose common words a narrow card must not break, and whose call to action ("Regenerate
      // summary") wraps on a phone under 200% text, so the arrow's case reads a label that does wrap. No figures,
      // so the chip cases still read seven chips.
      {
        filing_id: 202, accession_number: null, company: { id: 52, ticker: 'IBM', name: 'International Business Machines Corporation' },
        filing_type: '10-Q', filing_date: '2026-08-03', period_end_date: '2026-06-30', summary_id: 302, summary_status: 'placeholder',
        what_changed: null,
      },
    ],
  },
}

/** The dashboard with the two What changed cards and no watchlist rows: it waits for the seven chips, since with no
    watchlist the page shows no "Open watchlist insights" link to wait for. */
async function openFeed(page: Page, baseURL: string) {
  await signIn(page, TYPICAL, baseURL, CHANGED_FEED)
  await page.goto('/dashboard')
  await expect(page.locator('[data-what-changed-chip]')).toHaveCount(7)
  await page.evaluate(() => document.fonts.ready)
}

/** Each chip's box against its row and its card, and where Chromium paints its label and figure: their text's line
    boxes through a Range (as admin-invite-chip-reflow.spec.ts reads EmailChipsInput's chip), so text that spills out of
    its own box still counts, against the chip's content box (inside its border and padding). */
async function chipGeometry(page: Page) {
  return page.evaluate(() => {
    const lines = (el: Element | undefined) => {
      if (!el?.firstChild) return []
      const range = document.createRange()
      range.selectNodeContents(el)
      return [...range.getClientRects()].map((r) => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom }))
    }
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      chips: [...document.querySelectorAll<HTMLElement>('[data-what-changed-chip]')].map((chip) => {
        const box = chip.getBoundingClientRect()
        const style = getComputedStyle(chip)
        const row = chip.parentElement!.getBoundingClientRect()
        const card = chip.closest('a')!.getBoundingClientRect()
        // The chip's own group of two: its label, then its figure.
        const [label, figure] = [...chip.querySelector(':scope > span')!.children]
        return {
          name: chip.textContent, left: box.left, right: box.right,
          rowLeft: row.left, rowRight: row.right, cardRight: card.right,
          content: {
            left: box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
            right: box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
          },
          label: lines(label), figure: lines(figure),
          radius: style.borderTopLeftRadius,
        }
      }),
    }
  })
}

type Chip = Awaited<ReturnType<typeof chipGeometry>>['chips'][number]

/** Every line of the chip's label and figure is painted inside its content box: a word that cannot break, or a figure
    held beside a label that cannot narrow, runs past it. */
function expectTextInside(c: Chip) {
  for (const line of [...c.label, ...c.figure]) {
    expect(line.left, `${c.name}: its text starts inside the chip`).toBeGreaterThanOrEqual(c.content.left - 0.5)
    expect(line.right, `${c.name}: its text ends inside the chip`).toBeLessThanOrEqual(c.content.right + 0.5)
  }
}

for (const width of [320, 340, 360, 640, 768, 1024, 1280]) {
  test(`What changed's chips stay inside their row at ${width}px under 200% text`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await openFeed(page, baseURL!)
    await doubleText(page)
    await page.evaluate(() => document.fonts.ready)
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))

    const m = await chipGeometry(page)
    expect(m.chips).toHaveLength(7)
    expect(m.scrollWidth, 'the page does not scroll sideways').toBe(m.clientWidth)
    for (const c of m.chips) {
      expect(c.left, `${c.name} starts inside its row`).toBeGreaterThanOrEqual(c.rowLeft - 0.5)
      expect(c.right, `${c.name} ends inside its row`).toBeLessThanOrEqual(c.rowRight + 0.5)
      expect(c.right, `${c.name} ends inside its card`).toBeLessThanOrEqual(c.cardRight)
      expectTextInside(c)
      // The 16px step, which is 32px under 200% text: a pill on one line and a rounded box once it wraps.
      expect(c.radius).toBe('32px')
    }
    // The bank's longest chip: on a phone and in the two-column feed from 1280px (the second column opens at 40rem,
    // E272) its figure moves under the label's last line; on the one-column feed's full-width cards from 640 to 1279px
    // it keeps beside the label, on one line.
    const bank = m.chips.find((c) => c.name?.startsWith('Noninterest income'))!
    expect(bank.figure).toHaveLength(1)
    if (width <= 360 || width >= 1280) {
      const labelBottom = Math.max(...bank.label.map((line) => line.bottom))
      expect(bank.figure[0].top, 'its figure moves under its label').toBeGreaterThanOrEqual(labelBottom - 0.5)
    } else {
      expect(bank.label, 'its label keeps one line').toHaveLength(1)
      expect(bank.figure[0].top, 'its figure keeps beside its label, on its line').toBeLessThan(bank.label[0].bottom - 0.5)
    }
  })
}

test("What changed's chips keep one line at 1440px at the default text size", async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await openFeed(page, baseURL!)
  const m = await chipGeometry(page)
  expect(m.chips).toHaveLength(7)
  for (const c of m.chips) {
    expect(c.label, `${c.name} keeps its label on one line`).toHaveLength(1)
    expect(c.figure, `${c.name} keeps its figure on one line`).toHaveLength(1)
    expect(c.figure[0].top, `${c.name} keeps its figure beside its label`).toBe(c.label[0].top)
    expectTextInside(c)
    expect(c.radius).toBe('16px')
  }
})

/** The What changed card's header and call to action (E272, chief design on #1897): where the card's content box is
    narrower than the 21rem the header needs side by side, the date column moves under the company line and the name
    wraps, so each painted line of the name, the ticker and the date column sits inside the card, the company line and
    the date column never overlap, the name shows whole, and "Read summary" keeps its arrow on its last word's line.
    Stacked, the logo keeps to the name's first line, and the date ("Aug 3, 2026") keeps whole (chief design on #1900). */
async function headerGeometry(page: Page) {
  return page.evaluate(() => {
    const box = (r: DOMRect) => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom })
    const lines = (node: Node) => {
      const range = document.createRange()
      range.selectNodeContents(node)
      return [...range.getClientRects()].filter((r) => r.width > 0).map(box)
    }
    return [...document.querySelectorAll<HTMLElement>('[data-what-changed-header]')].map((header) => {
      const card = header.parentElement!
      const style = getComputedStyle(card)
      const outer = card.getBoundingClientRect()
      const content = {
        left: outer.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
        right: outer.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
      }
      const [company, dates] = [...header.children] as HTMLElement[]
      const [name, ticker] = [...company.lastElementChild!.children] as HTMLElement[]
      // The logo, where it shows (it gives way below 7.25rem), and the date's own words.
      const logo = company.children.length > 1 ? (company.firstElementChild as HTMLElement) : null
      const logoShown = !!logo && getComputedStyle(logo).display !== 'none'
      const date = dates.lastElementChild!.querySelector('span')!
      // The call to action's last word: the line box of its last text node's last line, whatever wraps it; and how
      // many lines its words take.
      const cta = card.lastElementChild as HTMLElement
      const walker = document.createTreeWalker(cta, NodeFilter.SHOW_TEXT)
      const texts: Text[] = []
      for (let node = walker.nextNode(); node; node = walker.nextNode()) if (node.textContent!.trim()) texts.push(node as Text)
      const lastLines = lines(texts[texts.length - 1])
      const ctaLines = new Set(texts.flatMap((text) => lines(text).map((line) => Math.round(line.top)))).size
      // A word of the name painted across two lines, where the word on its own would fit the card's content box: a break
      // the header could have spared it, with a line of its own or the logo's room (below 7.25rem the logo gives way).
      const nameText = name.firstChild as Text
      const splitWords: string[] = []
      let at = 0
      for (const word of nameText.data.split(' ')) {
        const range = document.createRange()
        range.setStart(nameText, at)
        range.setEnd(nameText, at + word.length)
        const tops = new Set([...range.getClientRects()].map((r) => Math.round(r.top)))
        const probe = document.createElement('span')
        probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap'
        probe.textContent = word
        name.appendChild(probe)
        const fits = probe.getBoundingClientRect().width <= content.right - content.left
        probe.remove()
        if (tops.size > 1 && fits) splitWords.push(word)
        at += word.length + 1
      }
      return {
        name: name.textContent!, content,
        nameLines: lines(name), nameBox: box(name.getBoundingClientRect()), tickerBox: box(ticker.getBoundingClientRect()),
        dateLines: lines(dates), dateStarts: [...dates.children].map((line) => line.getBoundingClientRect().left),
        companyBox: box(company.getBoundingClientRect()), datesBox: box(dates.getBoundingClientRect()),
        nameCut: name.scrollWidth - name.clientWidth, splitWords,
        arrow: box(cta.querySelector('svg')!.getBoundingClientRect()), lastWord: lastLines[lastLines.length - 1], ctaLines,
        logo: logoShown ? box(logo!.getBoundingClientRect()) : null,
        dateText: date.textContent!, dateLineCount: new Set(lines(date).map((line) => Math.round(line.top))).size,
      }
    })
  })
}

type Header = Awaited<ReturnType<typeof headerGeometry>>[number]

const overlaps = (a: { left: number; right: number; top: number; bottom: number }, b: typeof a) =>
  a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5

function expectHeaderFits(h: Header, stacked: boolean) {
  // Stacked, the name wraps, so its painted lines are its extent; side by side a long name truncates, and its text runs on
  // under the clip, so its box is.
  const name = stacked ? h.nameLines : [h.nameBox]
  for (const line of [...name, h.tickerBox, ...h.dateLines]) {
    expect(line.left, `${h.name}: its header starts inside the card`).toBeGreaterThanOrEqual(h.content.left - 0.5)
    expect(line.right, `${h.name}: its header ends inside the card`).toBeLessThanOrEqual(h.content.right + 0.5)
  }
  for (const part of [...name, h.tickerBox]) {
    for (const date of h.dateLines) expect(overlaps(part, date), `${h.name}: the company line clears the date column`).toBe(false)
  }
  if (stacked) {
    // One column: the date column under the company line and at the card's left edge, and the name whole, wrapped
    // rather than cut, with no word broken that had room for itself.
    expect(h.datesBox.top, `${h.name}: the date column sits under the company line`).toBeGreaterThanOrEqual(h.companyBox.bottom - 0.5)
    for (const left of h.dateStarts) expect(Math.abs(left - h.content.left), `${h.name}: each date line starts at the card's left edge`).toBeLessThanOrEqual(0.5)
    expect(h.nameCut, `${h.name} shows whole`).toBeLessThanOrEqual(0)
    expect(h.splitWords, `${h.name}: no word breaks that fits the card`).toEqual([])
    // The logo keeps to the name's first line, as ActivityLine's dot keeps to its first line (chief design on #1900).
    if (h.logo) {
      const first = h.nameLines[0]
      expect(Math.abs((h.logo.top + h.logo.bottom) / 2 - (first.top + first.bottom) / 2), `${h.name}: the logo keeps to the name's first line`).toBeLessThanOrEqual(1)
    }
  } else {
    // Side by side: the date column beside the company line, at its right.
    expect(h.datesBox.top, `${h.name}: the date column sits beside the company line`).toBeLessThan(h.companyBox.bottom)
    expect(h.datesBox.left, `${h.name}: the date column starts after the company line`).toBeGreaterThanOrEqual(h.companyBox.right - 0.5)
  }
  expect(h.dateLineCount, `${h.name}: the date "${h.dateText}" keeps whole`).toBe(1)
  // The arrow sits on the line of the label's last word, right after it, never parted to the card's far edge.
  expect(h.arrow.top, `${h.name}: the arrow is on its last word's line`).toBeLessThan(h.lastWord.bottom)
  expect(h.arrow.bottom).toBeGreaterThan(h.lastWord.top)
  expect(h.arrow.left, `${h.name}: the arrow comes after its last word`).toBeGreaterThanOrEqual(h.lastWord.right - 0.5)
  expect(h.arrow.left - h.lastWord.right, `${h.name}: the arrow follows its last word`).toBeLessThanOrEqual(10)
}

for (const width of [320, 340, 360, 640, 768, 1024, 1280]) {
  test(`What changed's header stacks inside its card at ${width}px under 200% text`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await openFeed(page, baseURL!)
    await doubleText(page)
    await page.evaluate(() => document.fonts.ready)
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
    const headers = await headerGeometry(page)
    expect(headers).toHaveLength(3)
    for (const h of headers) expectHeaderFits(h, true)
    if (width <= 360) {
      const ibm = headers.find((h) => h.name.startsWith('International'))!
      expect(ibm.ctaLines, '"Regenerate summary" wraps, so the arrow reads a wrapped label').toBe(2)
    }
  })
}

// At the default size the header stacks where the card is narrower than 21rem (a phone, the two-column feed from 640px
// and at 1024px) and stays side by side where it is wider (1440px).
for (const [width, stacked] of [[320, true], [360, true], [390, true], [640, true], [1024, true], [1440, false]] as const) {
  test(`What changed's header ${stacked ? 'stacks' : 'stays side by side'} inside its card at ${width}px`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await openFeed(page, baseURL!)
    const headers = await headerGeometry(page)
    expect(headers).toHaveLength(3)
    for (const h of headers) expectHeaderFits(h, stacked)
  })
}

/** The dashboard's two links with a trailing arrow (E274): the feed's "See all N companies" under its cards and the
    Your companies card's "Open watchlist insights", fed the five watched companies' rows so the feed's three cards
    link to the rest: "See all 5 companies". Wherever a label wraps, the arrow sits inside its last word's line,
    right after it, never between the lines; the link paints one box, so its focus ring draws one outline around
    every line of it; and its words and arrow keep the link's 0.25rem inset from that box (4px, 8px under 200% text),
    so the ring's rounded corners never cross them, and stay inside the link's row. A smaller floor let a 2 or 3px
    inset pass under 200% text with the ring's curve across the "5" (E274's review). */
const FEED_WITH_ROWS: Overrides = Object.fromEntries(
  Object.entries(CHANGED_FEED).filter(([pathname]) => pathname !== '/api/watchlist/insights'),
)

async function arrowLinkGeometry(page: Page, name: string) {
  return page.getByRole('link', { name, exact: true }).evaluate((link) => {
    const box = (r: DOMRect) => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom })
    const lines = (node: Node) => {
      const range = document.createRange()
      range.selectNodeContents(node)
      return [...range.getClientRects()].filter((r) => r.width > 0).map(box)
    }
    const walker = document.createTreeWalker(link, NodeFilter.SHOW_TEXT)
    const texts: Text[] = []
    for (let node = walker.nextNode(); node; node = walker.nextNode()) if (node.textContent!.trim()) texts.push(node as Text)
    const lastLines = lines(texts[texts.length - 1])
    return {
      boxes: link.getClientRects().length,
      painted: texts.flatMap(lines),
      lineCount: new Set(texts.flatMap((text) => lines(text).map((line) => Math.round(line.top)))).size,
      lastWord: lastLines[lastLines.length - 1],
      arrow: box(link.querySelector('svg')!.getBoundingClientRect()),
      link: box(link.getBoundingClientRect()),
      row: box(link.parentElement!.getBoundingClientRect()),
      // The inset the link's px-1 gives: 0.25rem of the root's font size.
      inset: parseFloat(getComputedStyle(document.documentElement).fontSize) / 4,
    }
  })
}

function expectArrowWithLastWord(g: Awaited<ReturnType<typeof arrowLinkGeometry>>) {
  expect(g.boxes, 'the link paints one box, so its focus ring draws one outline').toBe(1)
  expect(g.arrow.top, "the arrow sits inside its last word's line").toBeGreaterThanOrEqual(g.lastWord.top - 2)
  expect(g.arrow.bottom, "the arrow sits inside its last word's line").toBeLessThanOrEqual(g.lastWord.bottom + 2)
  expect(g.arrow.left, 'the arrow comes after its last word').toBeGreaterThanOrEqual(g.lastWord.right - 0.5)
  expect(g.arrow.left - g.lastWord.right, 'the arrow follows its last word').toBeLessThanOrEqual(10)
  for (const part of [...g.painted, g.arrow]) {
    expect(part.left, 'the words and arrow start inside the row').toBeGreaterThanOrEqual(g.row.left - 0.5)
    expect(part.right, 'the words and arrow end inside the row').toBeLessThanOrEqual(g.row.right + 0.5)
    expect(part.left - g.link.left, "the words and arrow keep the link's inset, off the ring's corners").toBeGreaterThanOrEqual(g.inset - 0.5)
    expect(g.link.right - part.right, "the words and arrow keep the link's inset, off the ring's corners").toBeGreaterThanOrEqual(g.inset - 0.5)
  }
}

// Each link with the widest width the cases below test at which its label wraps under 200% text with room to spare,
// so a case says when it reads a wrapped label. Where a label stops wrapping is the font's to say: in one Chromium with
// CI's fonts "See all 5 companies" wrapped up to 356px and "Open watchlist insights" up to 397px, and CI's own runner
// wrapped "See all 5 companies" at 360px too. So a wider case asserts no count; the arrow's checks hold on one line or
// on two.
const ARROW_LINKS: Array<[name: string, wrapsTo: number]> = [['See all 5 companies', 340], ['Open watchlist insights', 390]]

for (const width of [320, 340, 360, 375, 390, 640, 1024]) {
  test(`the dashboard's arrow links keep their arrow with their last word at ${width}px under 200% text`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await signIn(page, TYPICAL, baseURL!, FEED_WITH_ROWS)
    await page.goto('/dashboard')
    await expect(page.locator('[data-what-changed-chip]')).toHaveCount(7)
    await doubleText(page)
    await page.evaluate(() => document.fonts.ready)
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
    for (const [name, wrapsTo] of ARROW_LINKS) {
      const g = await arrowLinkGeometry(page, name)
      expectArrowWithLastWord(g)
      if (width <= wrapsTo) expect(g.lineCount, `${name} wraps here, so the case reads a wrapped label`).toBe(2)
    }
  })
}

for (const width of [320, 1440]) {
  test(`the dashboard's arrow links keep one line at ${width}px at the default text size`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 })
    await signIn(page, TYPICAL, baseURL!, FEED_WITH_ROWS)
    await page.goto('/dashboard')
    await expect(page.locator('[data-what-changed-chip]')).toHaveCount(7)
    await page.evaluate(() => document.fonts.ready)
    for (const [name] of ARROW_LINKS) {
      const g = await arrowLinkGeometry(page, name)
      expect(g.lineCount, `${name} keeps one line`).toBe(1)
      expectArrowWithLastWord(g)
    }
  })
}
