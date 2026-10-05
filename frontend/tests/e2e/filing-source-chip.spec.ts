import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'

/**
 * EN-01: a provenance chip on the filing page always reaches the source, in a real Chromium.
 *
 * With the research pane closed, activating "Verified in filing" used to do nothing visible: the
 * pane stayed hidden and only its hidden tab flipped. Now the activation opens the pane on the
 * Filing tab, highlights the passage when the filing text is available and matched, or shows the
 * truthful empty / unmatched / error state with the original-document action, whose target is the
 * filing's primary document (document_url) rather than the EDGAR folder. Touch gets the documented
 * sheet with "Show in filing"; the keyboard reaches "Open in SEC EDGAR" from the chip; the result is
 * the same for an anonymous visitor and a Pro user.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside
 * the browser with page.route fixtures (the summary is a trimmed copy of the public Apple FY2025 10-K
 * example, fixtures/filing-3-summary.json), so the server render falls back to the client fetch.
 * DOM and keyboard probes only: this is not a screen-reader test.
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
// The takeaway chip's verified excerpt (fixtures/filing-3-summary.json, Total net sales).
const EXCERPT = 'Americas net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services.'
const CHIP = 'Source: Verified in filing'
const PANE = '[role="dialog"][aria-label="Ask this Filing"]'

type Who = 'anon' | 'pro'
type Content = 'none' | 'matched' | 'unmatched' | 'error'
type Theme = 'light' | 'dark'

async function answerApi(page: Page, baseURL: string, who: Who, content: Content) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  if (who === 'pro') await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (pathname) {
      case '/api/filings/3':
        return json(200, FILING)
      case '/api/summaries/filing/3':
        return json(200, SUMMARY)
      case '/api/filings/3/content':
        if (content === 'error') return json(500, { detail: 'content unavailable' })
        if (content === 'none') return json(200, { filing_id: 3, has_content: false, markdown_content: null })
        return json(200, {
          filing_id: 3,
          has_content: true,
          markdown_content:
            content === 'matched'
              ? `# Item 8. Financial Statements\n\nNet sales by reportable segment. ${EXCERPT} Europe net sales also increased.\n`
              : '# Item 8. Financial Statements\n\nNothing cited in the summary appears in this text.\n',
        })
      case '/api/auth/me':
        return who === 'anon'
          ? json(401, { detail: 'Not authenticated' })
          : json(200, { id: 1, email: 'pro@example.com', full_name: 'Pro User', is_pro: true, is_beta: false, is_admin: false, email_verified: true })
      case '/api/subscriptions/subscription':
        return json(200, { is_pro: true, stripe_customer_id: 'cus_1', stripe_subscription_id: 'sub_1', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: 0, summaries_limit: 100, is_pro: true, month: '2026-10', qa_used: 0, qa_limit: 300, copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: 50 })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}

async function openFiling(page: Page, baseURL: string, { who = 'anon', content = 'none', theme = 'light' }: { who?: Who; content?: Content; theme?: Theme } = {}) {
  await answerApi(page, baseURL, who, content)
  // Consent answered and the first-run coachmark seen: EN-02 owns the consent bar; this spec is the chip.
  await page.addInitScript((t: string) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      // components/CookieConsent.tsx reads STORAGE_KEY 'cookie_consent' (its own preference shape).
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  const chip = page.getByRole('button', { name: CHIP }).first()
  await expect(chip).toBeVisible()
  await chip.scrollIntoViewIfNeeded()
  return chip
}

const paneState = (page: Page) =>
  page.evaluate((sel) => {
    const d = document.querySelector<HTMLElement>(sel)
    const r = d?.getBoundingClientRect()
    return {
      ariaHidden: d?.getAttribute('aria-hidden') ?? null,
      display: d ? getComputedStyle(d).display : null,
      height: r ? Math.round(r.height) : 0,
      selectedTab: document.querySelector('[role="tab"][aria-selected="true"]')?.textContent?.trim() ?? null,
    }
  }, PANE)

const activeName = (page: Page) =>
  page.evaluate(() => {
    const el = document.activeElement
    return el && el !== document.body ? el.getAttribute('aria-label') || el.textContent?.trim() || el.tagName : 'BODY'
  })

test.describe('desktop: a chip activation opens the pane on the Filing tab', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const who of ['anon', 'pro'] as const) {
    for (const theme of ['light', 'dark'] as const) {
      test(`${who}, ${theme}: closed pane → open on Filing with the truthful empty state and the document link`, async ({ page, baseURL }) => {
        const chip = await openFiling(page, baseURL!, { who, theme })
        expect(await paneState(page)).toMatchObject({ ariaHidden: 'true', display: 'none' })

        await chip.click()
        await expect(page.locator(PANE)).toBeVisible()
        expect(await paneState(page)).toMatchObject({ ariaHidden: 'false', selectedTab: 'Filing' })
        const pane = page.locator(PANE)
        await expect(pane.getByText('The full filing text is not available to view in-app yet.')).toBeVisible()
        await expect(pane.getByRole('link', { name: /open the original on sec\.gov/i })).toHaveAttribute('href', DOCUMENT)
        await expect(pane.getByRole('link', { name: 'Open original' })).toHaveAttribute('href', DOCUMENT)
        // Opening on the Filing tab neither focuses the composer nor shows the Ask teaser.
        expect(await activeName(page)).not.toBe('TEXTAREA')
        await expect(pane.getByRole('textbox')).toHaveCount(0)

        // Escape closes the pane and the chip keeps focus (it was the activated control). The pointer
        // moves off the chip first: the pane narrows the column, Chromium re-dispatches mousemove, and
        // a chip under the pointer would open its hover popover and take the Escape.
        await page.mouse.move(0, 0)
        await page.keyboard.press('Escape')
        await expect(page.locator(PANE)).toBeHidden()
        expect(await activeName(page)).toBe(CHIP)
      })
    }
  }

  test('an activation while the pane is open switches it to Filing without closing it', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!, { who: 'pro' })
    // The launcher by its label (the summary also has an "Ask this filing" CTA button).
    await page.locator('button[aria-label="Ask this Filing"]').click()
    await expect(page.locator(PANE)).toBeVisible()
    expect(await paneState(page)).toMatchObject({ selectedTab: 'Answer' })
    await chip.click()
    await expect(page.locator(PANE)).toBeVisible()
    expect(await paneState(page)).toMatchObject({ ariaHidden: 'false', selectedTab: 'Filing' })
  })

  test('a closed pane stays closed; a new activation reopens it', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!)
    await chip.click()
    await expect(page.locator(PANE)).toBeVisible()
    await page.mouse.move(0, 0)
    await page.keyboard.press('Escape')
    await expect(page.locator(PANE)).toBeHidden()
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.waitForTimeout(1500)
    await expect(page.locator(PANE)).toBeHidden()
    await chip.click()
    await expect(page.locator(PANE)).toBeVisible()
    expect(await paneState(page)).toMatchObject({ selectedTab: 'Filing' })
  })

  test('with filing text, a matched excerpt is highlighted in the reader', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!, { who: 'pro', content: 'matched' })
    await chip.click()
    const pane = page.locator(PANE)
    await expect(pane.locator('.filing-reader')).toContainText(EXCERPT)
    await expect
      .poll(() => page.evaluate(() => (CSS as unknown as { highlights: Map<string, { size: number }> }).highlights.get('copilot-citation')?.size ?? 0))
      .toBeGreaterThan(0)
    await expect(pane.getByText(/Couldn’t pinpoint the exact passage/)).toHaveCount(0)
  })

  test('with filing text that lacks the excerpt, the reader says so and still offers the document', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!, { content: 'unmatched' })
    await chip.click()
    const pane = page.locator(PANE)
    await expect(pane.getByText(/Couldn’t pinpoint the exact passage/)).toBeVisible()
    await expect(pane.getByRole('link', { name: 'Open original' }).first()).toHaveAttribute('href', DOCUMENT)
    expect(await page.evaluate(() => (CSS as unknown as { highlights: Map<string, { size: number }> }).highlights.get('copilot-citation')?.size ?? 0)).toBe(0)
    await expect(pane.getByText(/source match found/i)).toHaveCount(0)
  })

  test('a content-fetch failure shows the error state with Try again and the document link', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!, { content: 'error' })
    await chip.click()
    const pane = page.locator(PANE)
    await expect(pane.getByText('Could not load the filing text.')).toBeVisible()
    await expect(pane.getByRole('button', { name: /try again/i })).toBeVisible()
    await expect(pane.getByRole('link', { name: /open the original on sec\.gov/i })).toHaveAttribute('href', DOCUMENT)
  })

  test('closing from inside the pane (Close button, or Escape with focus on a pane control) returns focus to the chip', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!, { who: 'pro' })
    await chip.click()
    await expect(page.locator(PANE)).toBeVisible()
    await page.mouse.move(0, 0)
    // A keyboard user reaches the pane's Close and presses it: the control that had focus goes
    // display:none, so focus must come back to the chip, not fall to <body>.
    await page.locator(PANE).getByRole('button', { name: 'Close' }).focus()
    expect(await activeName(page)).toBe('Close')
    await page.keyboard.press('Enter')
    await expect(page.locator(PANE)).toBeHidden()
    expect(await activeName(page)).toBe(CHIP)

    // The same from Escape with focus on a pane control (the Filing tab).
    await chip.click()
    await expect(page.locator(PANE)).toBeVisible()
    await page.mouse.move(0, 0)
    await page.locator(PANE).getByRole('tab', { name: 'Filing' }).focus()
    expect(await activeName(page)).toBe('Filing')
    await page.keyboard.press('Escape')
    await expect(page.locator(PANE)).toBeHidden()
    expect(await activeName(page)).toBe(CHIP)
  })

  test('keyboard: Tab from the chip reaches "Open in SEC EDGAR", Tab again resumes the page, Escape returns to the chip', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!)
    await chip.focus()
    await expect(page.getByRole('group', { name: 'Source detail' })).toBeVisible()
    await page.keyboard.press('Tab')
    expect(await activeName(page)).toBe('Open in SEC EDGAR')
    const href = await page.evaluate(() => (document.activeElement as HTMLAnchorElement).href)
    expect(href.startsWith(DOCUMENT)).toBe(true)
    await expect(page.getByRole('group', { name: 'Source detail' })).toBeVisible()

    await page.keyboard.press('Shift+Tab')
    expect(await activeName(page)).toBe(CHIP)
    await page.keyboard.press('Tab')
    expect(await activeName(page)).toBe('Open in SEC EDGAR')
    await page.keyboard.press('Escape')
    await expect(page.getByRole('group', { name: 'Source detail' })).toHaveCount(0)
    expect(await activeName(page)).toBe(CHIP)

    // Tab past the link leaves the popover for the page's next stop after the chip (here the next
    // metric's chip, whose own popover opens on focus), never <body> and never a stop skipped. Escape
    // left the chip focused with its popover closed, so blur and refocus to open it again.
    const nextStop = await page.evaluate((chipName) => {
      const stops = Array.from(document.querySelectorAll<HTMLElement>('a[href], button, input, select, textarea, [tabindex]')).filter(
        (el) => !el.hasAttribute('disabled') && el.tabIndex >= 0 && el.getClientRects().length > 0 && !el.closest('[role="group"][aria-label="Source detail"]'),
      )
      const chip = stops.find((el) => el.getAttribute('aria-label') === chipName)
      const next = chip ? stops[stops.indexOf(chip) + 1] : undefined
      return next ? next.getAttribute('aria-label') || next.textContent?.trim() || next.tagName : null
    }, CHIP)
    expect(nextStop).not.toBeNull()
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
    await chip.focus()
    await expect(page.getByRole('group', { name: 'Source detail' })).toBeVisible()
    await page.keyboard.press('Tab')
    expect(await activeName(page)).toBe('Open in SEC EDGAR')
    await page.keyboard.press('Tab')
    await expect(chip).toHaveAttribute('aria-expanded', 'false')
    const landed = await activeName(page)
    expect(landed).toBe(nextStop)
    expect(landed).not.toBe('BODY')
    expect(landed).not.toBe('Open in SEC EDGAR')
  })
})

test.describe('touch: a tap opens the sheet, "Show in filing" opens the pane', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

  test('the sheet holds the EDGAR link and the in-app jump; the jump opens the pane on Filing; close returns focus to the chip', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!, { who: 'pro' })
    await chip.tap()
    const sheet = page.getByRole('dialog', { name: 'Source detail' })
    await expect(sheet).toBeVisible()
    await expect(sheet.getByRole('link', { name: /open in sec edgar/i })).toHaveAttribute('href', /aapl-20250927\.htm/)
    await expect(page.locator(PANE)).toBeHidden()

    await sheet.getByRole('button', { name: 'Show in filing' }).tap()
    await expect(sheet).toHaveCount(0)
    await expect(page.locator(PANE)).toBeVisible()
    expect(await paneState(page)).toMatchObject({ ariaHidden: 'false', selectedTab: 'Filing' })
    const pane = page.locator(PANE)
    await expect(pane.getByRole('link', { name: /open the original on sec\.gov/i })).toHaveAttribute('href', DOCUMENT)

    await page.keyboard.press('Escape')
    await expect(page.locator(PANE)).toBeHidden()
    expect(await activeName(page)).toBe(CHIP)
  })

  test('Escape on the sheet closes it and returns focus to the chip', async ({ page, baseURL }) => {
    const chip = await openFiling(page, baseURL!)
    await chip.tap()
    await expect(page.getByRole('dialog', { name: 'Source detail' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: 'Source detail' })).toHaveCount(0)
    expect(await activeName(page)).toBe(CHIP)
  })
})
