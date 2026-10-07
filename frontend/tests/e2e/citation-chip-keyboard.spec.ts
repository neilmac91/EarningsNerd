import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'

/**
 * EN-01 follow-up: an Ask answer's citation chip ([1]) and the research pane it lives in, by keyboard,
 * in a real Chromium.
 *
 *  - Escape on the focused chip, or from its card's "Open original" link, closes the card alone and
 *    leaves focus on the chip; the pane closes on the next press. On main the first Escape closed
 *    the whole pane (desktop) or sheet (below lg), because the card handled the key in React, after
 *    the sheet's document-level trap and alongside the rail's window listener.
 *  - Enter on the chip switches the pane to the Filing tab, which hides the chip: focus goes to the
 *    selected Filing tab instead of falling to <body>.
 *  - A summary chip that opened the pane gets focus back when the pane closes, even after a citation
 *    was followed from the answer (the answer's chip never replaces the pane's opener).
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API, including the
 * Ask stream, is answered inside the browser with page.route fixtures for a Pro visitor. DOM and
 * keyboard probes only: this is not a screen-reader test.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const SUMMARY = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-summary.json'), 'utf8')) as Record<string, unknown>

const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const DOCUMENT = `${FOLDER}aapl-20250927.htm`
const FILING = {
  id: 3,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  accession_number: '0000320193-25-000079',
  document_url: DOCUMENT,
  sec_url: FOLDER,
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
}
// A completed Ask answer with three verified citations, in the wire shape copilot-api.ts admits.
const ANSWER = {
  type: 'complete',
  kind: 'answer',
  answer:
    'Total net sales were $416.2B in FY2025 [F1]. Growth came mainly from Services [2]. Management cautions that gross margins remain subject to volatility and downward pressure [1].',
  grounded: 3,
  citations: [
    { n: 1, excerpt: 'As a result, the Company believes, in general, gross margins will be subject to volatility and downward pressure.', section_ref: 'Item 7. MD&A – Gross Margin', verified: true, fragment_url: `${DOCUMENT}#:~:text=As%20a%20result` },
    { n: 2, excerpt: 'Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services.', section_ref: 'Item 7. MD&A – Products and Services Performance', verified: true, fragment_url: `${DOCUMENT}#:~:text=Services%20net%20sales` },
    { n: 'F1', excerpt: 'RevenueFromContractWithCustomerExcludingAssessedTax = 416,161,000,000 USD (FY2025)', section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', verified: true, fragment_url: DOCUMENT },
  ],
  followups: ['Which segment declined in 2025?', 'What drove the lower effective tax rate?'],
}
const PANE = '[role="dialog"][aria-label="Ask this Filing"]'
const LAUNCHER = 'button[aria-haspopup="dialog"][aria-label="Ask this Filing"]'
const SUMMARY_CHIP = 'Source: Verified in filing'
const CARD = '[role="group"][aria-label^="Citation 1:"]'

async function openFiling(page: Page, baseURL: string) {
  const origin = new URL(baseURL).origin
  const cors = {
    'access-control-allow-origin': origin,
    'access-control-allow-credentials': 'true',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
  }
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const request = route.request()
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (new URL(request.url()).pathname) {
      case '/api/filings/3':
        return json(200, FILING)
      case '/api/summaries/filing/3':
        return json(200, SUMMARY)
      case '/api/filings/3/content':
        return json(200, { filing_id: 3, has_content: false, markdown_content: null })
      case '/api/auth/me':
        return json(200, { id: 1, email: 'pro@example.com', full_name: 'Pro User', is_pro: true, is_beta: false, is_admin: false, email_verified: true })
      case '/api/subscriptions/subscription':
        return json(200, { is_pro: true, stripe_customer_id: 'cus_1', stripe_subscription_id: 'sub_1', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: 0, summaries_limit: 100, is_pro: true, month: '2026-10', qa_used: 0, qa_limit: 300, copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: 50 })
      case '/api/summaries/filing/3/ask-stream':
        return route.fulfill({
          status: 200,
          headers: { ...cors, 'content-type': 'text/event-stream', 'cache-control': 'no-cache' },
          body: `data: ${JSON.stringify({ type: 'progress', stage: 'reading' })}\n\ndata: ${JSON.stringify(ANSWER)}\n\n`,
        })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
  // Consent answered and the first-run coachmark seen: neither is under test here.
  await page.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })
  await page.goto('/filing/3')
  await expect(page.getByRole('button', { name: SUMMARY_CHIP }).first()).toBeVisible()
}

/** Ask a question in the open pane and return the answer's [1] chip. */
async function ask(page: Page) {
  const composer = page.locator(PANE).getByPlaceholder('Ask about this filing…')
  await composer.fill('What drove revenue?')
  await composer.press('Enter')
  const chip = page.locator(PANE).getByRole('button', { name: /^Citation 1:/ })
  await expect(chip).toBeVisible()
  // Keep the pointer off the answer so no hover card competes with the keyboard.
  await page.mouse.move(5, 5)
  return chip
}

const paneOpen = (page: Page) => page.locator(PANE).evaluate((el) => getComputedStyle(el).display !== 'none')

for (const vp of [
  { name: 'desktop 1440x900', width: 1440, height: 900, sheet: false },
  { name: 'sheet 390x844', width: 390, height: 844, sheet: true },
]) {
  test.describe(`answer citation by keyboard, ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } })

    test('Escape on the focused chip closes its card alone; the next Escape closes the pane', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!)
      await page.locator(LAUNCHER).click()
      const chip = await ask(page)
      await chip.focus()
      await expect(page.locator(CARD)).toBeVisible()

      await page.keyboard.press('Escape')
      await expect(page.locator(CARD)).toHaveCount(0)
      expect(await paneOpen(page)).toBe(true)
      await expect(chip).toBeFocused()

      await page.keyboard.press('Escape')
      await expect.poll(() => paneOpen(page)).toBe(false)
      // The sheet returns focus to the launcher; the desktop close path is EN-05's (deferred).
      if (vp.sheet) await expect(page.locator(LAUNCHER)).toBeFocused()
    })

    test("Escape from the card's Open original link closes the card and refocuses the chip", async ({ page, baseURL }) => {
      await openFiling(page, baseURL!)
      await page.locator(LAUNCHER).click()
      const chip = await ask(page)
      await chip.focus()
      await page.keyboard.press('Tab')
      await expect(page.locator(CARD).getByRole('link', { name: 'Open original' })).toBeFocused()

      await page.keyboard.press('Escape')
      await expect(page.locator(CARD)).toHaveCount(0)
      expect(await paneOpen(page)).toBe(true)
      await expect(chip).toBeFocused()
    })

    test('Enter on the chip opens the Filing tab with focus on it; the arrow keys return to the answer and its composer', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!)
      await page.locator(LAUNCHER).click()
      const chip = await ask(page)
      await chip.focus()
      await page.keyboard.press('Enter')

      const filingTab = page.locator(PANE).getByRole('tab', { name: 'Filing' })
      await expect(filingTab).toHaveAttribute('aria-selected', 'true')
      await expect(filingTab).toBeFocused()
      await expect(page.locator(PANE).getByText('The full filing text is not available to view in-app yet.')).toBeVisible()

      // Back on the answer, the rail focuses its composer, as it does whenever the Answer view becomes
      // active (AskCopilotRail); the hand-off above never competes with it.
      await page.keyboard.press('ArrowLeft')
      await expect(page.locator(PANE).getByRole('tab', { name: 'Answer' })).toHaveAttribute('aria-selected', 'true')
      await expect(page.locator(PANE).getByPlaceholder('Ask about this filing…')).toBeFocused()
      await expect(page.locator(PANE).getByRole('button', { name: /^Citation 1:/ })).toBeVisible()
    })

    test('a summary chip that opened the pane gets focus back after a citation followed from the answer', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!)
      const summaryChip = page.getByRole('button', { name: SUMMARY_CHIP }).first()
      await summaryChip.scrollIntoViewIfNeeded()
      await summaryChip.focus()
      await page.keyboard.press('Enter')
      await expect(page.locator(PANE).getByRole('tab', { name: 'Filing' })).toHaveAttribute('aria-selected', 'true')

      await page.locator(PANE).getByRole('tab', { name: 'Answer' }).click()
      const chip = await ask(page)
      await chip.focus()
      await page.keyboard.press('Enter')
      await expect(page.locator(PANE).getByRole('tab', { name: 'Filing' })).toBeFocused()

      await page.keyboard.press('Escape')
      await expect.poll(() => paneOpen(page)).toBe(false)
      await expect(summaryChip).toBeFocused()
    })
  })
}
