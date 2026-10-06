import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Locator, type Page } from '@playwright/test'

/**
 * EN-02: the cookie-consent bar yields to the research chrome, in a real Chromium.
 *
 * Before: the bar (fixed bottom-0 z-50) sat over the z-40 "Ask this Filing" launcher — elementFromPoint
 * at the launcher's centre returned "Accept All", a pointer click on it timed out, the first-run
 * coachmark pointed at the covered launcher, and with the mobile sheet open the composer textarea
 * was entirely behind the bar. Now the bar is on z-consent (35: above the page's sticky section nav
 * and the workspace scrims, beneath that z-40 chrome) and publishes its height as --consent-inset,
 * which the launcher, the coachmark, the feedback launcher and the sheets add to their bottom offset
 * while the bar is mounted; the coachmark waits until the bar is gone and the "preferences saved"
 * confirmation is a top-centre toast.
 *
 * Both control sets are checked in the states where each is meant to be active: with no modal open,
 * every consent choice and the launcher hit themselves and are inside the viewport, and they activate
 * by pointer and by keyboard; under a real modal (the settings dialog) the controls beneath are
 * legitimately inert and are re-tested operable after dismissal; under the mobile sheet, whose scrim
 * sits below the bar, a choice stays pointer-operable and resolves consent without closing the sheet.
 * Consent semantics are unchanged: nothing is accepted or dismissed by the layout, and a choice
 * persists and fires `cookieConsentChanged` exactly as before.
 *
 * Desktop note: the pane is a static column that sticks under the header once the page has scrolled
 * past its own header; unscrolled, its bottom overhangs the viewport (on main too: 152px at
 * 1440x900). Opening the pane focuses its composer, and the document's scroll-padding-bottom
 * (the bar's inset) makes that focus scroll the pane into its stuck position, clear of the bar —
 * before, the focus scroll stopped at the viewport edge and left the composer 9px under the bar.
 * The composer checks below perform no scroll of their own.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside
 * the browser with page.route (the summary fixture is a trimmed copy of the public Apple FY2025 10-K
 * example). DOM, pointer and keyboard probes only: this is not a screen-reader test.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const SUMMARY = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-summary.json'), 'utf8')) as Record<string, unknown>
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
const PANE = '[role="dialog"][aria-label="Ask this Filing"]'
const COACH_TEXT = 'New: ask this filing anything'
const SAVED_TEXT = 'Cookie preferences saved'
const CONSENT_CHOICES = ['Accept All', 'Reject All', 'Customize'] as const

type Rect = { x: number; y: number; w: number; h: number }
type Theme = 'light' | 'dark'

declare global {
  interface Window {
    __consentEvents?: unknown[]
  }
}

/** A Pro session: the Answer tab then carries the composer textarea the sheet checks are about. */
async function answerApi(page: Page, baseURL: string) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
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
        return json(200, { id: 1, email: 'pro@example.com', full_name: 'Pro User', is_pro: true, is_beta: false, is_admin: false, email_verified: true })
      case '/api/subscriptions/subscription':
        return json(200, { is_pro: true, stripe_customer_id: 'cus_1', stripe_subscription_id: 'sub_1', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: 0, summaries_limit: 100, is_pro: true, month: '2026-10', qa_used: 0, qa_limit: 300, copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: 50 })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}

interface OpenOptions {
  theme?: Theme
  /** Stored preferences: the bar must not show. */
  consented?: boolean
  /** Do Not Track: defaults are saved silently and the bar must not show. */
  dnt?: boolean
}

/** Fresh storage by default: no consent choice, first-run coachmark not yet seen, logged in (feedback launcher shown). */
async function openFiling(page: Page, baseURL: string, { theme = 'light', consented = false, dnt = false }: OpenOptions = {}) {
  await answerApi(page, baseURL)
  await page.addInitScript(
    ({ theme, consented, dnt }: { theme: Theme; consented: boolean; dnt: boolean }) => {
      try {
        localStorage.setItem('theme', theme)
        localStorage.setItem('en_session_active', '1')
        if (consented) {
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        }
      } catch {}
      if (dnt) Object.defineProperty(navigator, 'doNotTrack', { get: () => '1' })
      window.__consentEvents = []
      window.addEventListener('cookieConsentChanged', (e) => window.__consentEvents?.push((e as CustomEvent).detail))
    },
    { theme, consented, dnt },
  )
  await page.goto('/filing/3')
  await expect(launcher(page)).toBeVisible()
}

const bar = (page: Page) => page.getByRole('region', { name: 'Cookie consent' })
// exact: the summary's "Ask this filing" CTA (AskFilingCallout) and the feedback form's submit share these words.
const launcher = (page: Page) => page.getByRole('button', { name: 'Ask this Filing', exact: true })
const feedbackLauncher = (page: Page) => page.getByRole('button', { name: 'Send feedback', exact: true })
const composer = (page: Page) => page.locator(PANE).getByRole('textbox')
const coachmark = (page: Page) => page.getByText(COACH_TEXT)
/** The coachmark stays absent for a while (a mount one tick later would pass a one-shot count). */
async function expectCoachmarkDeferred(page: Page) {
  await expect(coachmark(page)).toHaveCount(0)
  await page.waitForTimeout(600)
  expect(await coachmark(page).count(), 'the coachmark must wait for the bar').toBe(0)
}

const rectOf = (loc: Locator): Promise<Rect> =>
  loc.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { x: r.x, y: r.y, w: r.width, h: r.height }
  })
/** document.elementFromPoint at the element's centre is the element (or a descendant). */
const hitsItself = (loc: Locator) =>
  loc.evaluate((el) => {
    const r = el.getBoundingClientRect()
    const at = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
    return at === el || el.contains(at)
  })
const viewport = (page: Page) => page.evaluate(() => ({ w: window.innerWidth, h: window.innerHeight }))
const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
const inside = (r: Rect, vp: { w: number; h: number }) => r.x >= 0 && r.y >= 0 && r.x + r.w <= vp.w + 0.5 && r.y + r.h <= vp.h + 0.5
const layer = (page: Page) =>
  page.evaluate(() => ({
    visible: document.documentElement.hasAttribute('data-consent-visible'),
    inset: document.documentElement.style.getPropertyValue('--consent-inset'),
  }))
const stored = (page: Page) => page.evaluate(() => JSON.parse(localStorage.getItem('cookie_consent') ?? 'null'))
const consentEvents = (page: Page) => page.evaluate(() => window.__consentEvents ?? [])

/** Every consent choice and both launchers hit themselves, sit inside the viewport and clear the bar. */
async function expectBothControlSetsUsable(page: Page) {
  const vp = await viewport(page)
  await expect.poll(async () => ({ ...(await layer(page)), height: Math.ceil((await rectOf(bar(page))).h) })).toMatchObject({ visible: true })
  const barRect = await rectOf(bar(page))
  await expect.poll(() => layer(page)).toEqual({ visible: true, inset: `${Math.ceil(barRect.h)}px` })
  for (const name of CONSENT_CHOICES) {
    const choice = page.getByRole('button', { name, exact: true })
    expect(await hitsItself(choice), `${name} is covered`).toBe(true)
    expect(inside(await rectOf(choice), vp), `${name} is outside the viewport`).toBe(true)
  }
  for (const [label, loc] of [['launcher', launcher(page)], ['feedback launcher', feedbackLauncher(page)]] as const) {
    const r = await rectOf(loc)
    expect(await hitsItself(loc), `${label} is covered`).toBe(true)
    expect(inside(r, vp), `${label} is outside the viewport`).toBe(true)
    expect(overlaps(r, barRect), `${label} overlaps the bar`).toBe(false)
    expect(r.y + r.h, `${label} is not above the bar`).toBeLessThanOrEqual(barRect.y + 0.5)
  }
  await expectCoachmarkDeferred(page)
  return { vp, barRect }
}

/**
 * The site header (z-50, top-anchored) ranks above the bar by design; its mobile menu opens in flow
 * inside the header. Where the open menu ends above the bar (390x844: 427px of header against a bar
 * at 667) every choice stays operable with it open; on a short phone (320x568) the open menu reaches
 * the bar's region and covers a choice until the user closes it — a user-opened, user-closed surface,
 * documented in DESIGN_SYSTEM §4 (before this change the bar covered the menu's lower items instead).
 * Either way the choices are operable again once the menu is closed.
 */
async function expectMenuYields(page: Page, menuClearsBar: boolean) {
  await page.getByRole('button', { name: 'Open menu' }).click()
  await expect(page.getByRole('button', { name: 'Close menu' })).toBeVisible()
  const header = await rectOf(page.locator('header').first())
  const barTop = (await rectOf(bar(page))).y
  if (menuClearsBar) {
    expect(header.y + header.h, 'the open menu reaches the bar').toBeLessThanOrEqual(barTop + 0.5)
    await expectBothControlSetsUsable(page)
  } else {
    expect(header.y + header.h, 'the open menu was expected to reach the bar on this short viewport').toBeGreaterThan(barTop)
  }
  await page.getByRole('button', { name: 'Close menu' }).click()
  await expect(page.getByRole('button', { name: 'Open menu' })).toBeVisible()
  await expectBothControlSetsUsable(page)
}

/** With the pane open: its composer is inside the viewport and never intersected by the bar. */
async function expectComposerClear(page: Page) {
  const vp = await viewport(page)
  const barRect = await rectOf(bar(page))
  await expect(composer(page)).toBeVisible()
  // Desktop: the focus scroll on open is smooth; wait for it to settle before reading rects.
  if (vp.w >= 1024) await expect.poll(() => rectOf(page.locator(PANE)).then((r) => Math.round(r.y + r.h))).toBeLessThanOrEqual(Math.round(barRect.y) + 1)
  const c = await rectOf(composer(page))
  expect(inside(c, vp), 'composer outside the viewport').toBe(true)
  expect(overlaps(c, barRect), 'composer behind the bar').toBe(false)
  const pane = await rectOf(page.locator(PANE))
  expect(pane.y, 'the sheet runs off the top of the viewport').toBeGreaterThanOrEqual(0)
  expect(pane.y + pane.h, 'the pane runs under the bar').toBeLessThanOrEqual(barRect.y + 0.5)
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`desktop 1440x900, ${theme}`, () => {
    test.use({ viewport: { width: 1440, height: 900 } })

    test('consent choices and research controls are usable together; a modal makes the page inert only while open; a choice persists and clears the layer', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      await expect(bar(page)).toBeVisible()
      await expectBothControlSetsUsable(page)

      // The launcher opens the pane by a real pointer click; the desktop pane ends above the bar.
      await launcher(page).click()
      await expect(page.locator(PANE)).toBeVisible()
      await expectComposerClear(page)
      await page.keyboard.press('Escape')
      await expect(page.locator(PANE)).toBeHidden()
      await expectBothControlSetsUsable(page)

      // The settings dialog is a real modal: everything beneath is inert, and operable again on Escape.
      await page.getByRole('button', { name: 'Customize' }).click()
      await expect(page.getByRole('dialog', { name: 'Cookie Preferences' })).toBeVisible()
      expect(await hitsItself(launcher(page))).toBe(false)
      expect(await hitsItself(page.getByRole('button', { name: 'Accept All' }))).toBe(false)
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Customize' })).toBeFocused()
      expect(await stored(page)).toBeNull()
      expect(await consentEvents(page)).toEqual([])
      await expectBothControlSetsUsable(page)

      // Accept All: persisted exactly as before, one event, the layer cleared, the chrome back at its
      // normal offset, the confirmation toast away from the launcher corner, and the deferred coachmark
      // now pointing at a visible launcher.
      await page.getByRole('button', { name: 'Accept All' }).click()
      await expect(bar(page)).toHaveCount(0)
      expect(await layer(page)).toEqual({ visible: false, inset: '' })
      expect(await stored(page)).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
      expect(await consentEvents(page)).toHaveLength(1)
      const vp = await viewport(page)
      const toast = page.getByText(SAVED_TEXT)
      await expect(toast).toBeVisible()
      const launcherRect = await rectOf(launcher(page))
      const toastRect = await rectOf(toast)
      expect(overlaps(toastRect, launcherRect)).toBe(false)
      expect(toastRect.y + toastRect.h).toBeLessThan(vp.h / 2)
      expect(Math.round(vp.h - (launcherRect.y + launcherRect.h))).toBe(20) // 1.25rem base gap, no inset
      expect(await hitsItself(launcher(page))).toBe(true)
      // The pane was opened above, which marks the first-run nudge as seen: it stays dismissed.
      expect(await coachmark(page).count()).toBe(0)
    })

    test('the coachmark is deferred while the bar shows and then points at the uncovered launcher', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      await expect(bar(page)).toBeVisible()
      await expectCoachmarkDeferred(page)
      await page.getByRole('button', { name: 'Accept All' }).click()
      await expect(bar(page)).toHaveCount(0)
      await expect(coachmark(page)).toBeVisible()
      const launcherRect = await rectOf(launcher(page))
      expect(await hitsItself(launcher(page))).toBe(true)
      expect(overlaps(await rectOf(coachmark(page)), launcherRect)).toBe(false)
      expect(inside(await rectOf(coachmark(page)), await viewport(page))).toBe(true)
    })
  })

  test.describe(`phone 390x844 (touch), ${theme}`, () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

    test('the sheet rests on the bar with its composer in view; the bar is inert under the sheet and operable after it closes; keyboard choices work', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      await expect(bar(page)).toBeVisible()
      await expectBothControlSetsUsable(page)

      await expectMenuYields(page, true)

      await launcher(page).tap()
      await expect(page.locator(PANE)).toBeVisible()
      await expectComposerClear(page)
      // The sheet's scrim sits below the bar: the choices stay visible and pointer-operable beside the sheet.
      for (const name of CONSENT_CHOICES) expect(await hitsItself(page.getByRole('button', { name, exact: true }))).toBe(true)
      await page.keyboard.press('Escape')
      await expect(page.locator(PANE)).toBeHidden()
      await expectBothControlSetsUsable(page)

      // Keyboard: Enter opens the settings dialog, Escape returns to Customize, Tab reaches Reject All,
      // Space activates it. The choice is stored and announced exactly as a click would be.
      await page.getByRole('button', { name: 'Customize' }).focus()
      await page.keyboard.press('Enter')
      await expect(page.getByRole('dialog', { name: 'Cookie Preferences' })).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(page.getByRole('button', { name: 'Customize' })).toBeFocused()
      await page.keyboard.press('Tab')
      await expect(page.getByRole('button', { name: 'Reject All' })).toBeFocused()
      await page.keyboard.press('Space')
      await expect(bar(page)).toHaveCount(0)
      expect(await stored(page)).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
      expect(await consentEvents(page)).toHaveLength(1)
      expect(await layer(page)).toEqual({ visible: false, inset: '' })
      const toast = page.getByText(SAVED_TEXT)
      await expect(toast).toBeVisible()
      expect(overlaps(await rectOf(toast), await rectOf(launcher(page)))).toBe(false)
      // The sheet was opened above, which marks the first-run nudge as seen: it stays dismissed.
      expect(await coachmark(page).count()).toBe(0)
    })

    test('a choice made while the sheet is open resolves consent and the sheet settles on the viewport bottom', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      await expect(bar(page)).toBeVisible()
      await launcher(page).tap()
      await expect(page.locator(PANE)).toBeVisible()
      await expectComposerClear(page)
      await page.getByRole('button', { name: 'Accept All' }).tap()
      await expect(bar(page)).toHaveCount(0)
      expect(await stored(page)).toMatchObject({ essential: true, analytics: true, sessionRecording: false })
      expect(await consentEvents(page)).toHaveLength(1)
      expect(await layer(page)).toEqual({ visible: false, inset: '' })
      await expect(page.locator(PANE)).toBeVisible()
      const vp = await viewport(page)
      const pane = await rectOf(page.locator(PANE))
      expect(Math.round(pane.y + pane.h)).toBe(vp.h) // bottom-[var(--consent-inset,0px)] back to 0
      expect(inside(await rectOf(composer(page)), vp)).toBe(true)
      expect(await hitsItself(composer(page))).toBe(true)
    })

    test('the coachmark is deferred while the bar shows and then points at the uncovered launcher', async ({ page, baseURL }) => {
      await openFiling(page, baseURL!, { theme })
      await expect(bar(page)).toBeVisible()
      await expectCoachmarkDeferred(page)
      await page.getByRole('button', { name: 'Reject All' }).tap()
      await expect(bar(page)).toHaveCount(0)
      await expect(coachmark(page)).toBeVisible()
      const launcherRect = await rectOf(launcher(page))
      expect(await hitsItself(launcher(page))).toBe(true)
      expect(overlaps(await rectOf(coachmark(page)), launcherRect)).toBe(false)
      expect(inside(await rectOf(coachmark(page)), await viewport(page))).toBe(true)
    })
  })
}

test.describe('narrow and short viewports', () => {
  for (const [w, h] of [
    [320, 568],
    [1280, 600],
  ] as const) {
    test.describe(`${w}x${h}`, () => {
      test.use({ viewport: { width: w, height: h }, isMobile: w < 1024, hasTouch: w < 1024 })
      test('bar, launcher and composer never overlap', async ({ page, baseURL }) => {
        await openFiling(page, baseURL!)
        await expect(bar(page)).toBeVisible()
        // At 320x568 the unscrolled section nav (sticky, z-sticky) sits in the bar's region: the hit
        // tests below prove the bar paints over it (a consent layer at 20 lost "Accept All" to it).
        await expectBothControlSetsUsable(page)
        if (w < 1024) await expectMenuYields(page, false)
        await launcher(page).click()
        await expect(page.locator(PANE)).toBeVisible()
        await expectComposerClear(page)
        await page.keyboard.press('Escape')
        await expect(page.locator(PANE)).toBeHidden()
        await expectBothControlSetsUsable(page)
      })
    })
  }
})

test.describe('phone 390x844 with a simulated bottom safe-area inset', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

  test('the bar carries the inset and the chrome keeps its gap above it', async ({ page, baseURL }) => {
    const cdp = await page.context().newCDPSession(page)
    try {
      await cdp.send('Emulation.setSafeAreaInsetsOverride', { insets: { top: 0, left: 0, bottom: 34, right: 0 } })
    } catch {
      test.skip(true, 'this Chromium has no Emulation.setSafeAreaInsetsOverride')
    }
    await openFiling(page, baseURL!)
    await expect(bar(page)).toBeVisible()
    const safe = await page.evaluate(() => {
      const probe = document.createElement('div')
      probe.style.height = 'env(safe-area-inset-bottom)'
      document.body.appendChild(probe)
      const h = probe.getBoundingClientRect().height
      probe.remove()
      return h
    })
    test.skip(safe === 0, 'the safe-area override did not reach env()')
    const { barRect } = await expectBothControlSetsUsable(page)
    const padding = await bar(page).evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom))
    expect(Math.round(padding)).toBe(34)
    const l = await rectOf(launcher(page))
    expect(Math.round(barRect.y - (l.y + l.h))).toBe(20) // 1.25rem above the bar, the safe area not counted twice
    await launcher(page).tap()
    await expectComposerClear(page)
  })
})

test.describe('no bar', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('stored preferences: no bar, no layer, chrome at its normal offset, coachmark on the launcher', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, { consented: true })
    await expect(bar(page)).toHaveCount(0)
    expect(await layer(page)).toEqual({ visible: false, inset: '' })
    const vp = await viewport(page)
    const l = await rectOf(launcher(page))
    expect(Math.round(vp.h - (l.y + l.h))).toBe(20)
    expect(await hitsItself(launcher(page))).toBe(true)
    await expect(coachmark(page)).toBeVisible()
    expect(await consentEvents(page)).toEqual([])
  })

  test('Do Not Track: defaults saved silently, no bar, no layer', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, { dnt: true })
    await expect(bar(page)).toHaveCount(0)
    expect(await layer(page)).toEqual({ visible: false, inset: '' })
    expect(await stored(page)).toMatchObject({ essential: true, analytics: false, sessionRecording: false })
    expect(await consentEvents(page)).toHaveLength(1)
    expect(await page.getByText(SAVED_TEXT).count()).toBe(0)
  })
})
