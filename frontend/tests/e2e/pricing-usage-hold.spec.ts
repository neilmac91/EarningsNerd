import { test, expect, type Page } from '@playwright/test'

/**
 * The pricing page's usage box holds its place while a signed-in reader's usage read is in flight (E226).
 *
 * The box mounted only when the usage read answered, after the identity read, and pushed the plan cards down by its
 * height and margin: in CI's fonts 130 to 138px from 320 to 1440px, and 266 and 273px at 320 and 390px under 200% text
 * (chief design's measurement on #1700). The held card takes the plan the identity read names, a Free account's box
 * with its meter and a Pro account's without, so the first plan's heading keeps its place as the count lands. Under
 * 200% text the count line sits at its wrap edge at about 290 to 350px and 518 to 580px, where a count whose figures
 * are narrower or wider than the copy's "0" takes a line fewer or more, 40px, an exception chief design accepted on
 * #1715; the cases below hold at their widths.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside the browser with
 * page.route, the usage read held until the case answers it, and the middleware's session gate is satisfied by its
 * non-credential presence cookie.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin

const VERSION = '2026-10-24'
const READINESS = {
  collection_available: true,
  checkout_available: false,
  marketing_available: false,
  terms_version: VERSION,
  eligibility_version: VERSION,
  operator: { legal_name: 'Synthetic Test Operator', postal_address: '1 Test Street, Test City', country: 'CH', contact_email: 'legal@example.com' },
}

const ACCOUNTS = {
  Free: {
    isPro: false,
    usage: { summaries_used: 4, summaries_limit: 5 },
    status: null,
    line: '4 / 5 summaries used this month',
  },
  Pro: {
    isPro: true,
    usage: { summaries_used: 12, summaries_limit: null },
    status: 'active',
    line: '12 / ∞ summaries used this month',
  },
} as const

type Account = (typeof ACCOUNTS)[keyof typeof ACCOUNTS]

/** Answers the API for a signed-in account, the usage read held: the returned function answers it. */
async function signIn(page: Page, account: Account, baseURL: string): Promise<() => void> {
  const origin = new URL(baseURL).origin
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  let answerUsage: () => void = () => {}
  const usageAnswered = new Promise<void>((resolve) => { answerUsage = resolve })
  await page.route((url) => url.origin === API_ORIGIN, async (route) => {
    const json = (body: unknown) => route.fulfill({ status: 200, headers: cors, json: body })
    switch (new URL(route.request().url()).pathname) {
      case '/api/auth/me':
        return json({ id: 1, email: 'jordan@example.com', full_name: 'Jordan Whitaker', is_pro: account.isPro, is_beta: false, is_admin: false, email_verified: true })
      case '/api/subscriptions/subscription':
        return json({
          is_pro: account.isPro, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: account.status,
          plan: account.isPro ? 'pro' : 'free', status: account.status, trial_end: null, current_period_end: null, cancel_at_period_end: false,
        })
      case '/api/subscriptions/usage':
        await usageAnswered
        return json({ ...account.usage, is_pro: account.isPro, month: '2026-10', qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3, analysis_used: 0, analysis_limit: 0 })
      case '/api/auth/registration':
        return json({ mode: 'public', beta_promo_enabled: false })
      case '/api/legal/readiness':
        return json(READINESS)
      default:
        return route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } })
    }
  })
  return answerUsage
}

const CASES = [
  { width: 320, textSize: 16 },
  { width: 390, textSize: 16 },
  { width: 768, textSize: 16 },
  { width: 1440, textSize: 16 },
  { width: 320, textSize: 32 },
  { width: 390, textSize: 32 },
]

for (const [plan, account] of Object.entries(ACCOUNTS)) {
  for (const { width, textSize } of CASES) {
    const at = `${width}px${textSize === 32 ? ' under 200% text' : ''}`
    test(`the plans keep their place as a ${plan} account's usage lands, at ${at}`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height: 900 })
      const cdp = await page.context().newCDPSession(page)
      await cdp.send('Page.setFontSizes', { fontSizes: { standard: textSize, fixed: textSize === 32 ? 26 : 13 } })
      const answerUsage = await signIn(page, account, baseURL!)
      await page.goto('/pricing')

      // The account has settled (a plan reads "Current plan") and the usage card holds its place.
      await expect(page.getByRole('button', { name: 'Current plan', exact: true })).toBeVisible()
      await expect(page.locator('[aria-busy="true"]').filter({ hasText: 'Current usage' })).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      const heading = page.getByRole('heading', { level: 2, name: 'Free', exact: true })
      const top = () => heading.evaluate((el) => el.getBoundingClientRect().top + window.scrollY)
      const held = await top()

      answerUsage()
      await expect(page.getByText(account.line, { exact: true })).toBeVisible()
      await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
      const landed = await top()
      expect(
        Math.abs(landed - held),
        `the Free plan's heading at ${held}px with the usage card held and ${landed}px once ${account.line.split(' summaries')[0]} landed`,
      ).toBeLessThanOrEqual(1)
    })
  }
}
