import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, FILING, SUMMARY, type Theme } from './fixtures/filing3Api'

/**
 * EN-05: focus around terminal summary generation, in a real Chromium.
 *
 *  - A Pro visitor opens a filing with no summary, so the page generates one at load, and it fails.
 *    On main focus stayed on <body>: the keyboard user tabbed through the site header (9 stops at
 *    1440px, 6 at 390px) to reach "Retry generation". Now the failure card's heading takes focus
 *    nobody holds, described by the failure's reason, and one Tab reaches the Retry.
 *  - "Retry generation" by keyboard hands focus to the progress card's heading (RetryButton); on main
 *    it fell to <body>. A run that fails again brings focus back to the new card's heading.
 *  - The monthly-limit card a free visitor gets takes focus the same way.
 *  - Focus somebody holds when the failure lands (a header link) is never moved.
 *  - A successful run hands unclaimed/progress focus to its first content heading, without
 *    scrolling; cached reads, held focus and modal ownership do not trigger that arrival.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API, including the
 * generation stream, is answered inside the browser. DOM and keyboard probes only, not a screen reader.
 */

type Outcome = 'fail' | 'limit' | 'complete' | 'partial'
type Who = 'pro' | 'free'
/** The generation stream's next answer; `hold` keeps the request open until the test releases it. */
interface Stream { next: Outcome | 'hold'; release?: (outcome: Outcome) => void }

const FAILED = 'The filing could not be summarized right now.'
const ERROR_HEADING = 'Generation interrupted'
const LIMIT_HEADING = "You've hit this month's free limit"
const PROGRESS_HEADING = 'Generating your analysis'

async function openFiling(
  page: Page,
  baseURL: string,
  stream: Stream,
  who: Who = 'pro',
  { theme = 'light', cached = false, legacy = false, consent = true }: {
    theme?: Theme; cached?: boolean; legacy?: boolean; consent?: boolean
  } = {},
) {
  const pro = who === 'pro'
  let summaryReady = cached
  const summary = legacy
    ? { ...SUMMARY, business_overview: 'The selected filing reports revenue growth and its material risks.', rendered_sections: [] }
    : SUMMARY
  const origin = new URL(baseURL).origin
  const cors = {
    'access-control-allow-origin': origin,
    'access-control-allow-credentials': 'true',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
  }
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route((url) => url.origin === API_ORIGIN, async (route) => {
    const request = route.request()
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (new URL(request.url()).pathname) {
      case '/api/summaries/filing/3/generate-stream': {
        const outcome = stream.next === 'hold'
          ? await new Promise<Outcome>((resolve) => { stream.release = resolve })
          : stream.next
        if (outcome === 'complete' || outcome === 'partial') {
          summaryReady = true
          return route.fulfill({
            status: 200,
            headers: { ...cors, 'content-type': 'text/event-stream' },
            body: `data: ${JSON.stringify({ type: outcome, summary_id: summary.id })}\n\n`,
          })
        }
        // 4xx is not retried by the stream client, so the card appears at once.
        return outcome === 'fail'
          ? json(422, { detail: FAILED })
          : json(403, { detail: "You've reached your monthly limit. Upgrade to Pro for unlimited summaries." })
      }
      case '/api/filings/3':
        return json(200, FILING)
      case '/api/summaries/filing/3':
        return summaryReady ? json(200, summary) : json(404, { detail: 'Not found' })
      case '/api/filings/3/content':
        return json(200, { filing_id: 3, has_content: false, markdown_content: null })
      case '/api/auth/me':
        return json(200, { id: 1, email: `${who}@example.com`, full_name: 'Test User', is_pro: pro, is_beta: false, is_admin: false, email_verified: true })
      case '/api/subscriptions/subscription':
        return json(200, pro
          ? { is_pro: true, stripe_customer_id: 'cus_1', stripe_subscription_id: 'sub_1', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: null, cancel_at_period_end: false }
          : { is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null, plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: pro ? 0 : 5, summaries_limit: pro ? 100 : 5, is_pro: pro, month: '2026-10', qa_used: 0, qa_limit: pro ? 300 : 0, copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: pro ? 50 : 0 })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
  await page.addInitScript(({ theme, consent }) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      if (consent) localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, { theme, consent })
  await page.goto('/filing/3')
}

for (const theme of ['light', 'dark'] as const) {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    test.describe(`completed summary / ${theme} / ${viewport.width}`, () => {
      test.use({ viewport })

      for (const outcome of ['complete', 'partial'] as const) {
        test(`${outcome} takes unclaimed focus once, on its content heading without scrolling`, async ({ page, baseURL }) => {
          const stream: Stream = { next: 'hold' }
          await openFiling(page, baseURL!, stream, 'pro', { theme })
          await expect(heading(page, PROGRESS_HEADING)).toBeVisible()
          await expect.poll(() => stream.release !== undefined).toBe(true)
          const scrollY = await page.evaluate(() => window.scrollY)
          stream.release!(outcome)
          await expect(heading(page, 'The Print')).toBeFocused()
          expect(await page.evaluate(() => window.scrollY)).toBe(scrollY)
          const home = page.getByRole('link', { name: 'EarningsNerd home' })
          await home.focus()
          await page.evaluate(() => window.dispatchEvent(new Event('focus')))
          await expect(home).toBeFocused()
        })
      }

      test('success after keyboard Retry transfers the replaced progress heading focus', async ({ page, baseURL }) => {
        const stream: Stream = { next: 'fail' }
        await openFiling(page, baseURL!, stream, 'pro', { theme })
        await expect(heading(page, ERROR_HEADING)).toBeFocused()
        stream.next = 'hold'
        await page.keyboard.press('Tab')
        await page.keyboard.press('Enter')
        await expect(heading(page, PROGRESS_HEADING)).toBeFocused()
        await expect.poll(() => stream.release !== undefined).toBe(true)
        stream.release!('complete')
        await expect(heading(page, 'The Print')).toBeFocused()
      })

      test('success preserves focus held on a header link', async ({ page, baseURL }) => {
        const stream: Stream = { next: 'hold' }
        await openFiling(page, baseURL!, stream, 'pro', { theme })
        const home = page.getByRole('link', { name: 'EarningsNerd home' })
        await home.focus()
        await expect.poll(() => stream.release !== undefined).toBe(true)
        stream.release!('complete')
        await expect(heading(page, 'The Print')).toBeVisible()
        await expect(home).toBeFocused()
      })

      test('success behind an open dialog cannot take unclaimed dialog focus', async ({ page, baseURL }) => {
        const stream: Stream = { next: 'hold' }
        await openFiling(page, baseURL!, stream, 'pro', { theme, consent: false })
        await page.getByRole('button', { name: 'Customize', exact: true }).click()
        const dialog = page.getByRole('dialog', { name: 'Cookie preferences' })
        await expect(dialog).toBeVisible()
        await expect.poll(() => stream.release !== undefined).toBe(true)
        // A dialog control can leave between commits; body focus does not release its modal owner.
        await page.evaluate(() => (document.activeElement as HTMLElement)?.blur())
        stream.release!('complete')
        await expect(heading(page, 'The Print')).toBeVisible()
        await expect(heading(page, 'The Print')).not.toBeFocused()
        await expect(dialog).toBeVisible()
      })

      test('a cached summary never claims arrival focus', async ({ page, baseURL }) => {
        await openFiling(page, baseURL!, { next: 'complete' }, 'pro', { theme, cached: true })
        await expect(heading(page, 'The Print')).toBeVisible()
        await expect(heading(page, 'The Print')).not.toBeFocused()
      })

      test('legacy content without section headings has a stable completion heading', async ({ page, baseURL }) => {
        const stream: Stream = { next: 'hold' }
        await openFiling(page, baseURL!, stream, 'pro', { theme, legacy: true })
        await expect.poll(() => stream.release !== undefined).toBe(true)
        stream.release!('complete')
        await expect(heading(page, 'Summary')).toBeFocused()
      })
    })
  }
}

const heading = (page: Page, name: string) => page.getByRole('heading', { name, exact: true })

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test.describe(`${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport })

    test('a generation that fails on load focuses the card heading, and one Tab reaches Retry generation', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { next: 'fail' })
      await expect(heading(page, ERROR_HEADING)).toBeFocused()
      await expect(page.locator('[role="alert"]', { has: heading(page, ERROR_HEADING) })).toContainText(FAILED)
      // The focused title carries the reason, whatever the live announcement does when focus moves.
      await expect(heading(page, ERROR_HEADING)).toHaveAccessibleDescription(FAILED)
      await page.keyboard.press('Tab')
      await expect(page.getByRole('button', { name: 'Retry generation' })).toBeFocused()
    })

    test('Retry generation by keyboard focuses the progress heading, and a run that fails again focuses the new card', async ({ page, baseURL }) => {
      const stream: Stream = { next: 'fail' }
      await openFiling(page, baseURL!, stream)
      await expect(heading(page, ERROR_HEADING)).toBeFocused()
      stream.next = 'hold'
      await page.keyboard.press('Tab')
      await page.keyboard.press('Enter')
      await expect(heading(page, PROGRESS_HEADING)).toBeFocused()
      await expect.poll(() => stream.release !== undefined).toBe(true)
      stream.release!('fail')
      await expect(heading(page, ERROR_HEADING)).toBeFocused()
    })

    test("a free visitor's monthly-limit card focuses its heading, one Tab before the upgrade link", async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { next: 'limit' }, 'free')
      await expect(heading(page, LIMIT_HEADING)).toBeFocused()
      await page.keyboard.press('Tab')
      // The trial or plain upgrade link, whichever this visitor is offered.
      await expect(page.locator('[role="status"]', { has: heading(page, LIMIT_HEADING) }).getByRole('link')).toBeFocused()
    })

    test('focus held elsewhere when the failure lands stays there', async ({ page, baseURL }) => {
      const stream: Stream = { next: 'hold' }
      await openFiling(page, baseURL!, stream)
      await expect(heading(page, PROGRESS_HEADING)).toBeVisible()
      const home = page.getByRole('link', { name: 'EarningsNerd home' })
      await home.focus()
      await expect.poll(() => stream.release !== undefined).toBe(true)
      stream.release!('fail')
      await expect(heading(page, ERROR_HEADING)).toBeVisible()
      await expect(home).toBeFocused()
    })
  })
}
