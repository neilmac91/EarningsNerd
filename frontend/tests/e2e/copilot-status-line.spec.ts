import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, PANE, answerApi } from './fixtures/filing3Api'

/**
 * E238: the Ask rail's status line is the research pane's, between the [Filing · Ask] tabs and the two panels, so the
 * accessibility tree holds it whichever tab shows. A reader who asks and opens the filing while the answer is read is
 * told "Answer ready." when it completes. The line used to sit in the Ask panel, which the Filing tab hides with
 * display:none, so nothing was said.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside the browser for a
 * Pro visitor by fixtures/filing3Api.ts, and this spec holds the Ask stream until the Filing tab shows. Playwright's
 * role queries leave out what the accessibility tree leaves out (display:none, aria-hidden), so a status region they
 * find is one a screen reader is given. DOM probes only: this is not a screen-reader test.
 */

// A completed answer with no citations, in the wire shape copilot-api.ts admits.
const ANSWER = {
  type: 'complete',
  kind: 'answer',
  answer: 'Total net sales were $416.2 billion in fiscal 2025.',
  grounded: 0,
  citations: [],
  followups: [],
}
const LAUNCHER = 'button[aria-label="Source"]'

/** The filing page for a Pro visitor, its Ask stream held until the returned release is called. */
async function openFiling(page: Page, baseURL: string) {
  await answerApi(page, baseURL, 'pro')
  let release!: () => void
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  // Registered last, so it runs first: the Ask stream and its preflight. Every other request falls through to
  // answerApi's routes.
  const cors = {
    'access-control-allow-origin': new URL(baseURL).origin,
    'access-control-allow-credentials': 'true',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
  }
  await page.route(
    (url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3/ask-stream',
    async (route) => {
      if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
      await held
      await route.fulfill({
        status: 200,
        headers: { ...cors, 'content-type': 'text/event-stream', 'cache-control': 'no-cache' },
        body: `data: ${JSON.stringify(ANSWER)}\n\n`,
      })
    },
  )
  // Consent answered and the first-run coachmark seen: neither is under test here.
  await page.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })
  await page.goto('/filing/3')
  await expect(page.locator(LAUNCHER)).toBeVisible()
  return release
}

/** The status regions in the accessibility tree that say these words. */
const statusSaying = (page: Page, words: string) => page.getByRole('status').filter({ hasText: words })

for (const vp of [
  { name: 'desktop 1440x900', width: 1440, height: 900 },
  { name: 'sheet 390x844', width: 390, height: 844 },
]) {
  test.describe(`the pane's status line, ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } })

    test('is heard while the Filing tab shows: the answer completes there as "Answer ready."', async ({ page, baseURL }) => {
      const release = await openFiling(page, baseURL!)
      await page.locator(LAUNCHER).click()
      const composer = page.locator(PANE).getByPlaceholder('Ask about this filing…')
      await composer.fill('What drove revenue?')
      await composer.press('Enter')
      // The question is in flight: it shows in the Ask panel, above its reading card.
      await expect(page.locator(PANE).getByRole('tabpanel', { name: 'Ask' }).getByText('What drove revenue?')).toBeVisible()

      // The reader opens the filing while the answer is read. The Ask panel hides, the reading card with it, so the
      // one status region still saying the reading line is the pane's.
      const filingTab = page.locator(PANE).getByRole('tab', { name: /filing/i })
      await filingTab.click()
      await expect(filingTab).toHaveAttribute('aria-selected', 'true')
      await expect(statusSaying(page, 'Reading the filing…')).toHaveCount(1)

      release()
      await expect(statusSaying(page, 'Answer ready.')).toHaveCount(1)
      await expect(statusSaying(page, 'Reading the filing…')).toHaveCount(0)
    })
  })
}
