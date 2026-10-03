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

async function signIn(page: Page, who: Who, baseURL: string) {
  const origin = new URL(baseURL).origin
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const body = fixture(new URL(route.request().url()).pathname, who)
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
    // Beside a long "Generating (<stage>)" badge a name column keeps a few characters (the row
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
    // Every name sits inside the viewport with room to read, not squeezed beside the badges.
    for (const box of await names.evaluateAll((els) => els.map((el) => el.getBoundingClientRect().toJSON()))) {
      expect(box.right).toBeLessThanOrEqual(clientWidth)
      expect(box.width).toBeGreaterThanOrEqual(100)
    }
  })
}
