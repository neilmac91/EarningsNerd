import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page, type TestInfo } from '@playwright/test'

/** Browser-only collection boundary proof. CI has no backend: every API response and the
 * Turnstile script below is synthetic, and other external traffic is blocked. A green run
 * proves the real rendered UI and requests, not server enforcement, provider behavior or
 * publication of an operator's identity. Run with a synthetic Turnstile site key and Apple
 * enabled to exercise those optional integrations; no real challenge or OAuth flow runs. */
const VERSION = '2026-10-24'
const INVITE = 'synthetic-legal-readiness-invite'
const OPERATOR = {
  legal_name: 'Synthetic Test Operator',
  postal_address: '1 Test Street, Test City',
  country: 'CH',
  contact_email: 'legal@example.com',
}
const CLOSED = {
  collection_available: false,
  checkout_available: false,
  marketing_available: false,
  terms_version: VERSION,
  eligibility_version: VERSION,
  operator: null,
}
const READY = { ...CLOSED, collection_available: true, operator: OPERATOR }
const AGREEMENT = {
  adult_eligible: true,
  terms_accepted: true,
  terms_version: VERSION,
  eligibility_version: VERSION,
}
const surfaces = [
  { name: 'registration', url: `/register?invite=${INVITE}`, closed: 'Registration is currently closed' },
  { name: 'waitlist', url: '/waitlist', closed: 'Waitlist registration is currently closed' },
  { name: 'contact', url: '/contact', closed: 'General contact is currently closed' },
] as const
type Surface = typeof surfaces[number]
type Answer = { status: number; body: unknown }
const answer = (body: unknown): Answer => ({ status: 200, body })
const UNAVAILABLE: Answer = { status: 503, body: { detail: 'Synthetic unavailable response' } }

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

async function harness(page: Page, baseURL: string, theme: 'light' | 'dark' = 'light') {
  const origin = new URL(baseURL).origin
  const state = {
    respond: async (): Promise<Answer> => answer(CLOSED),
    authenticated: false,
    betaMember: false,
    readinessRequests: 0,
    captchaRequests: 0,
    mutations: [] as Array<{ path: string; body: unknown }>,
    blockedExternal: [] as string[],
    pageErrors: [] as string[],
  }
  page.on('pageerror', (error) => state.pageErrors.push(error.message))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('theme', selectedTheme)
    localStorage.setItem('cookie_consent', JSON.stringify({
      version: 2, essential: true, analytics: false, sessionRecording: false,
      timestamp: new Date().toISOString(),
    }))
  }, theme)
  // Observe browser requests independently of the response fixture. Any unexpected mutation
  // is recorded and refused, so a dropped UI guard cannot cause a real side effect.
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      state.mutations.push({ path: url.pathname, body: request.postDataJSON() })
    }
  })
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const cors = {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-headers': 'content-type,cf-turnstile-response',
      'access-control-allow-methods': 'GET,POST,OPTIONS',
    }
    if (url.hostname === 'challenges.cloudflare.com') {
      state.captchaRequests += 1
      return route.fulfill({ contentType: 'application/javascript', body: `
        window.turnstile = {
          render: function(el, options) {
            el.setAttribute('data-synthetic-turnstile', 'true');
            queueMicrotask(function() { options.callback('synthetic-turnstile-token'); });
            return 'synthetic-widget';
          }, reset: function() {}, remove: function() {}
        };
      ` })
    }
    if (url.pathname.startsWith('/api/')) {
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
      if (request.method() !== 'GET') {
        return route.fulfill({ status: 503, headers: cors, json: UNAVAILABLE.body })
      }
      if (url.pathname === '/api/legal/readiness') {
        state.readinessRequests += 1
        const response = await state.respond()
        return route.fulfill({ status: response.status, headers: cors, json: response.body })
      }
      if (url.pathname === '/api/auth/me') {
        return route.fulfill({ status: state.authenticated ? 200 : 401, headers: cors,
          json: state.authenticated
            ? { id: 7, email: 'existing@example.com', full_name: 'Existing User', is_pro: false, is_beta: state.betaMember, is_admin: false, email_verified: true }
            : { detail: 'Not authenticated' } })
      }
      if (url.pathname === '/api/subscriptions/subscription') {
        return route.fulfill({ headers: cors, json: {
          is_pro: false, stripe_customer_id: null, stripe_subscription_id: null,
          subscription_status: null, plan: 'free', status: null, trial_end: null,
          current_period_end: null, cancel_at_period_end: false,
        } })
      }
      if (url.pathname === '/api/subscriptions/usage') {
        return route.fulfill({ headers: cors, json: {
          summaries_used: 0, summaries_limit: 5, is_pro: false, month: '2026-10',
          qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3,
          analysis_used: 0, analysis_limit: 0,
        } })
      }
      if (url.pathname === '/api/auth/registration') {
        return route.fulfill({ headers: cors, json: { mode: 'public', beta_promo_enabled: false } })
      }
      if (url.pathname === '/api/waitlist/stats') {
        return route.fulfill({ headers: cors, json: { total_signups: 0 } })
      }
      return route.fulfill({ status: 404, headers: cors, json: { detail: 'No synthetic fixture' } })
    }
    if (url.origin === origin) return route.continue()
    state.blockedExternal.push(url.origin + url.pathname)
    return route.abort('blockedbyclient')
  })
  return state
}

async function noCollectionControls(page: Page) {
  await expect(page.locator('#main input, #main textarea')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Continue with (Google|Apple)/ })).toHaveCount(0)
  await expect(page.getByRole('group', { name: 'Security check' })).toHaveCount(0)
  await expect(page.locator('script[src*="challenges.cloudflare.com"]')).toHaveCount(0)
}

async function screenshot(page: Page, info: TestInfo, name: string, fullPage = true) {
  const directory = process.env.LEGAL_READINESS_SCREENSHOTS
  const file = directory ? path.join(directory, `${name}.png`) : info.outputPath(`${name}.png`)
  if (directory) await mkdir(directory, { recursive: true })
  // Full-page capture otherwise paints sticky chrome at the scroll offset left by a focused
  // below-fold button, making it look as though the page header sits midway through the page.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  await page.screenshot({ path: file, fullPage, animations: 'disabled' })
  await info.attach(name, { path: file, contentType: 'image/png' })
}

async function fillReadyForm(page: Page, surface: Surface) {
  if (surface.name === 'registration') {
    await page.getByLabel('Email', { exact: true }).fill('new@example.com')
    await page.getByLabel('Password', { exact: true }).fill('Synthetic-test-password-42!')
    await page.getByRole('checkbox', { name: /at least 18/ }).check()
    await page.getByRole('checkbox', { name: /agree to the/ }).check()
    return page.getByRole('button', { name: 'Create account', exact: true })
  }
  if (surface.name === 'waitlist') {
    await page.getByLabel('Email address', { exact: true }).fill('waiting@example.com')
    return page.getByRole('button', { name: 'Join the waitlist', exact: true })
  }
  await page.getByLabel('Name *', { exact: true }).fill('Synthetic Reader')
  await page.getByLabel('Email *', { exact: true }).fill('contact@example.com')
  await page.getByLabel('Message *', { exact: true }).fill('A synthetic account support question for browser verification.')
  return page.getByRole('button', { name: 'Send message', exact: true })
}

test.describe('Public access promises', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const [width, textSize] of [[390, 16], [390, 32], [1440, 16]]) {
      test(`examples remain available during intake hold in ${theme} at ${width}px and ${textSize}px text`, async ({ page, baseURL }, info) => {
        const state = await harness(page, baseURL!, theme)
        await page.setViewportSize({ width, height: 900 })
        const cdp = await page.context().newCDPSession(page)
        await cdp.send('Page.setFontSizes', { fontSizes: { standard: textSize, fixed: textSize === 32 ? 26 : 13 } })
        const pending = deferred<Answer>()
        state.respond = () => pending.promise
        await page.goto('/')
        await expect(page.getByText('Checking registration availability. You can explore a live example.')).toBeVisible()
        await expect(page.getByRole('link', { name: /Request.*invite|Create a free account|Sign up|Join the waitlist/i })).toHaveCount(0)
        pending.resolve(answer(CLOSED))
        await expect(page.getByText('New registrations are currently closed. Existing members can log in.')).toBeVisible()
        await expect(page.getByRole('link', { name: 'View plans' })).toHaveCount(1)
        await expect(page.getByRole('link', { name: /Upgrade to Pro|Start .*free trial/ })).toHaveCount(0)
        await expect(page.getByText('Free for beta members')).toHaveCount(0)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
        await screenshot(page, info, `public-home-${theme}-${width}-${textSize}`, false)

        state.respond = async () => answer(CLOSED)
        await page.goto('/waitlist')
        await expect(page.getByText('New registrations are currently closed. Existing members can log in.')).toBeVisible()
        await noCollectionControls(page)
        await expect(page.getByText(/You can (still )?join the waitlist/)).toHaveCount(0)
        await expect(page.getByRole('link', { name: 'Join the waitlist', exact: true })).toHaveCount(0)
        const example = page.locator('#main').getByRole('link', { name: 'See a live example', exact: true })
        await expect(example).toHaveAttribute('href', /(?:\/filing\/.*demo=1|\/company\/AAPL)/)
        await example.focus()
        await expect(example).toBeFocused()
        await expect(page.locator('#main').getByRole('link', { name: /^log in$/i })).toBeVisible()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
        await screenshot(page, info, `public-waitlist-${theme}-${width}-${textSize}`, false)
        expect(state.captchaRequests).toBe(0)
        expect(state.mutations).toEqual([])
        expect(state.blockedExternal).toEqual([])
        expect(state.pageErrors).toEqual([])
        await cdp.detach()
      })
    }
  }
})

test.describe('Public collection readiness', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const surface of surfaces) {
      test(`${surface.name} waits and stays closed at 390px and 200% text in ${theme}`, async ({ page, baseURL }, info) => {
        const state = await harness(page, baseURL!, theme)
        const cdp = await page.context().newCDPSession(page)
        await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
        const pending = deferred<Answer>()
        state.respond = () => pending.promise
        await page.goto(surface.url)
        await expect(page.getByRole('status', { name: `Checking ${surface.name} availability` })).toBeVisible()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
        await noCollectionControls(page)
        expect(state.captchaRequests).toBe(0)
        expect(state.mutations).toEqual([])
        pending.resolve(answer(CLOSED))
        await expect(page.getByText(surface.closed, { exact: true })).toBeVisible()
        await noCollectionControls(page)
        await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /dark/ : /^(?!.*\bdark\b)/)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
        const main = page.locator('#main')
        await expect(main.getByRole('link', { name: 'support@earningsnerd.io', exact: true }).first()).toHaveAttribute('href', 'mailto:support@earningsnerd.io')
        await expect(main.getByRole('link', { name: 'privacy@earningsnerd.io', exact: true }).first()).toHaveAttribute('href', 'mailto:privacy@earningsnerd.io')
        await page.screenshot({ path: info.outputPath(`${surface.name}-closed-${theme}-390-200.png`), animations: 'disabled' })
        expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('32px')
        expect(state.captchaRequests).toBe(0)
        expect(state.mutations).toEqual([])
        expect(state.blockedExternal).toEqual([])
        // Closing new collection must not remove the existing account sign-in route.
        await main.getByRole('link', { name: /^log in$/i }).first().click()
        await expect(page).toHaveURL(/\/login(?:\?|$)/)
        await page.getByRole('button', { name: 'Continue with email', exact: true }).click()
        await expect(page.getByLabel('Email', { exact: true })).toBeVisible()
      })
    }

    for (const textSize of [16, 32]) {
      test(`registration keeps its heading in place while opening in ${theme} at ${textSize}px text`, async ({ page, baseURL }) => {
        const state = await harness(page, baseURL!, theme)
        await page.emulateMedia({ reducedMotion: 'reduce' })
        const cdp = await page.context().newCDPSession(page)
        await cdp.send('Page.setFontSizes', { fontSizes: { standard: textSize, fixed: textSize === 32 ? 26 : 13 } })
        const pending = deferred<Answer>()
        state.respond = () => pending.promise
        await page.goto(surfaces[0].url)
        await expect(page.getByRole('status', { name: 'Checking registration availability' })).toBeVisible()
        await noCollectionControls(page)
        const heading = page.getByRole('heading', { name: 'Create your account', exact: true })
        const before = await heading.boundingBox()
        pending.resolve(answer(READY))
        await expect(page.getByRole('checkbox', { name: /at least 18/ })).toBeVisible()
        await expect(page.getByRole('status', { name: 'Checking registration availability' })).toHaveCount(0)
        const after = await heading.boundingBox()
        expect(Math.abs(after!.y - before!.y)).toBeLessThanOrEqual(1)
        expect(await page.evaluate(() => window.scrollY)).toBe(0)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
        expect(state.mutations).toEqual([])
        await cdp.detach()
      })
    }

    test(`closed checkout stays focusable and preserves existing billing in ${theme}`, async ({ page, baseURL }, info) => {
      const state = await harness(page, baseURL!, theme)
      await page.goto('/pricing')
      const button = page.getByRole('button', { name: 'Checkout unavailable', exact: true })
      await expect(button).toHaveAttribute('aria-disabled', 'true')
      await expect(button).not.toHaveAttribute('disabled', '')
      await button.focus()
      await button.press('Enter')
      await expect(button).toBeFocused()
      await expect(page).toHaveURL(/\/pricing$/)
      await expect(page.getByRole('link', { name: 'Manage existing billing' })).toHaveAttribute('href', '/dashboard/settings#billing')
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await screenshot(page, info, `pricing-closed-${theme}-390`)
      expect(state.mutations).toEqual([])
      expect(state.captchaRequests).toBe(0)
      expect(state.blockedExternal).toEqual([])
    })
  }

  // The status above the waitlist form holds the checking line and the counter's pill in one cell (E222, chief design on
  // #1686, comment 6433704320), so the form keeps its place as readiness answers open. As the line became the pill, in
  // CI's fonts, the form moved 2px up at 390px and 18px down at 1440px, and under 200% text 86px up at 320px, 46px up at
  // 390px, 6px up at 640 and 1440px and 34px down at 960 and 1800px. The shown line sits central in the cell the pill
  // sets. Light only: the theme changes no layout here.
  for (const { width, textSize } of [
    { width: 390, textSize: 16 }, { width: 1440, textSize: 16 },
    { width: 320, textSize: 32 }, { width: 390, textSize: 32 }, { width: 640, textSize: 32 },
    { width: 960, textSize: 32 }, { width: 1440, textSize: 32 }, { width: 1800, textSize: 32 },
  ]) {
    test(`the waitlist keeps its form in place while opening at ${width}px and ${textSize}px text`, async ({ page, baseURL }) => {
      const state = await harness(page, baseURL!)
      await page.setViewportSize({ width, height: 900 })
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const cdp = await page.context().newCDPSession(page)
      await cdp.send('Page.setFontSizes', { fontSizes: { standard: textSize, fixed: textSize === 32 ? 26 : 13 } })
      const pending = deferred<Answer>()
      state.respond = () => pending.promise
      await page.goto('/waitlist')
      await expect(page.getByRole('status', { name: 'Checking waitlist availability' })).toBeVisible()
      // The auth check answers at once: its guest link is in the bar before the first read, so the reads see readiness.
      await expect(page.getByRole('banner').getByRole('link', { name: /^(Live example|See a live example)$/ })).toHaveCount(1)
      await page.evaluate(() => document.fonts.ready)
      const form = page.locator('#waitlist')
      const status = form.locator('xpath=preceding-sibling::div[1]')
      const centred = () => status.evaluate((cell) => {
        const shown = cell.querySelector(':scope > div > :not([aria-hidden])')!
        const range = document.createRange()
        range.selectNodeContents(shown)
        const text = range.getBoundingClientRect()
        const box = cell.firstElementChild!.getBoundingClientRect()
        return Math.abs(text.y + text.height / 2 - (box.y + box.height / 2))
      })
      const before = await form.boundingBox()
      expect(await centred(), 'the checking line sits central in its cell').toBeLessThanOrEqual(1)
      pending.resolve(answer(READY))
      await expect(page.getByLabel('Email address', { exact: true })).toBeVisible()
      await expect(status.getByText('Join the waitlist', { exact: true })).toBeVisible()
      await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
      const after = await form.boundingBox()
      expect(Math.abs(after!.y - before!.y), `the form at ${before!.y}px while readiness checked and ${after!.y}px once it answered open`).toBeLessThanOrEqual(1)
      expect(await centred(), "the counter's pill sits central in its cell").toBeLessThanOrEqual(1)
      expect(await page.evaluate(() => window.scrollY)).toBe(0)
      expect(state.mutations).toEqual([])
      await cdp.detach()
    })
  }

  for (const surface of surfaces) {
    for (const [name, response] of [
      ['readiness error', UNAVAILABLE],
      ['nonboolean readiness', answer({ ...READY, collection_available: 'true' })],
      ['unpublished operator', answer({ ...READY, operator: null })],
    ] as const) {
      test(`${surface.name} refuses ${name}`, async ({ page, baseURL }) => {
        const state = await harness(page, baseURL!)
        state.respond = async () => response
        await page.goto(surface.url)
        await expect(page.getByText(surface.closed, { exact: true })).toBeVisible()
        await noCollectionControls(page)
        expect(state.mutations).toEqual([])
        expect(state.captchaRequests).toBe(0)
      })
    }
    for (const [name, response] of [['closed', answer(CLOSED)], ['unreachable', UNAVAILABLE]] as const) {
      test(`${surface.name} rechecks before sending and closes when readiness becomes ${name}`, async ({ page, baseURL }) => {
        const state = await harness(page, baseURL!)
        state.respond = async () => answer(READY)
        await page.goto(surface.url)
        const button = await fillReadyForm(page, surface)
        await expect(button).not.toHaveAttribute('aria-disabled', 'true')
        state.respond = async () => response
        await button.click()
        await expect(page.getByText(surface.closed, { exact: true })).toBeVisible()
        await expect(page.locator('#main input, #main textarea')).toHaveCount(0)
        expect(state.readinessRequests).toBeGreaterThanOrEqual(2)
        expect(state.mutations).toEqual([])
      })
    }
  }

  test('password registration requires two unchecked declarations and sends current explicit evidence', async ({ page, baseURL }, info) => {
    const state = await harness(page, baseURL!)
    state.respond = async () => answer(READY)
    await page.goto(surfaces[0].url)
    const adult = page.getByRole('checkbox', { name: /at least 18/ })
    const terms = page.getByRole('checkbox', { name: /agree to the/ })
    const create = page.getByRole('button', { name: 'Create account', exact: true })
    const google = page.getByRole('button', { name: 'Continue with Google', exact: true })
    await expect(adult).not.toBeChecked()
    await expect(terms).not.toBeChecked()
    await expect(google).not.toHaveAttribute('aria-disabled', 'true')
    await page.getByLabel('Email', { exact: true }).fill('new@example.com')
    await page.getByLabel('Password', { exact: true }).fill('Synthetic-test-password-42!')
    await create.focus()
    await create.press('Enter')
    await expect(adult).toBeFocused()
    await expect(page.getByRole('group', { name: 'Account requirements' }).getByRole('alert')).toHaveText('Confirm both statements to create an account.')
    expect(state.mutations).toEqual([])
    await adult.check()
    await create.click()
    await expect(terms).toBeFocused()
    await expect(page.getByRole('group', { name: 'Account requirements' }).getByRole('alert')).toHaveCount(1)
    await expect(google).not.toHaveAttribute('aria-disabled', 'true')
    await terms.check()
    await expect(create).not.toHaveAttribute('aria-disabled', 'true')
    await screenshot(page, info, 'registration-ready-light-390')
    await create.click()
    await expect.poll(() => state.mutations.length).toBe(1)
    expect(state.mutations[0]).toEqual({ path: '/api/auth/register', body: {
      email: 'new@example.com', password: 'Synthetic-test-password-42!', full_name: '',
      invite_code: INVITE, ...AGREEMENT,
    } })
    expect(state.readinessRequests).toBeGreaterThanOrEqual(2)
    // A configured widget must really request the intercepted script; otherwise the closed
    // tests alone could pass vacuously with Turnstile absent from the build.
    if (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY) expect(state.captchaRequests).toBe(1)
  })

  for (const provider of ['Google', 'Apple'] as const) {
    test(`${provider} signup requires both declarations and rechecks before its POST`, async ({ page, baseURL }) => {
      test.skip(provider === 'Apple' && process.env.NEXT_PUBLIC_ENABLE_APPLE_SIGNIN !== 'true', 'Apple is disabled in this build')
      const state = await harness(page, baseURL!)
      state.respond = async () => answer(READY)
      await page.goto(surfaces[0].url)
      const button = page.getByRole('button', { name: `Continue with ${provider}`, exact: true })
      await expect(button).not.toHaveAttribute('aria-disabled', 'true')
      await button.focus()
      await button.press('Enter')
      expect(state.mutations).toEqual([])
      await expect(page.getByRole('checkbox', { name: /at least 18/ })).toBeFocused()
      await expect(page.getByRole('group', { name: 'Account requirements' }).getByRole('alert')).toHaveText('Confirm both statements to create an account.')
      await page.getByRole('checkbox', { name: /at least 18/ }).check()
      await button.click()
      await expect(page.getByRole('checkbox', { name: /agree to the/ })).toBeFocused()
      await expect(page.getByRole('group', { name: 'Account requirements' }).getByRole('alert')).toHaveCount(1)
      await page.getByRole('checkbox', { name: /agree to the/ }).check()
      await button.click()
      await expect.poll(() => state.mutations.length).toBe(1)
      expect(state.mutations[0]).toEqual({ path: `/api/auth/${provider.toLowerCase()}/start`, body: { invite: INVITE, ...AGREEMENT } })
      expect(state.readinessRequests).toBeGreaterThanOrEqual(2)
      expect(state.blockedExternal).toEqual([])
    })
  }

  for (const surface of surfaces.slice(1)) {
    test(`fresh published readiness permits one ${surface.name} submission`, async ({ page, baseURL }) => {
      const state = await harness(page, baseURL!)
      state.respond = async () => answer(READY)
      await page.goto(surface.url)
      const button = await fillReadyForm(page, surface)
      await expect(button).not.toHaveAttribute('aria-disabled', 'true')
      await button.click()
      await expect.poll(() => state.mutations.length).toBe(1)
      expect(state.mutations[0]).toEqual(surface.name === 'waitlist'
        ? { path: '/api/waitlist/join', body: {
          email: 'waiting@example.com', name: null, referral_code: null, source: 'waitlist', honeypot: '',
        } }
        : { path: '/api/contact/', body: {
          name: 'Synthetic Reader', email: 'contact@example.com', subject: null,
          message: 'A synthetic account support question for browser verification.',
        } })
      expect(state.readinessRequests).toBeGreaterThanOrEqual(2)
      if (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY) expect(state.captchaRequests).toBe(1)
    })
  }

  test('changed policy versions remove the form before any signup request', async ({ page, baseURL }) => {
    const state = await harness(page, baseURL!)
    state.respond = async () => answer(READY)
    await page.goto(surfaces[0].url)
    const button = await fillReadyForm(page, surfaces[0])
    await expect(button).not.toHaveAttribute('aria-disabled', 'true')
    state.respond = async () => answer({ ...READY, terms_version: '2026-10-25', eligibility_version: '2026-10-25' })
    await button.click()
    await expect(page.getByText('Registration needs a refresh', { exact: true })).toBeVisible()
    await expect(page.getByText('The account requirements have changed. Refresh this page to load the current Terms and eligibility requirements before signing up.')).toBeVisible()
    await expect(page.locator('#main input, #main textarea')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Continue with (Google|Apple)/ })).toHaveCount(0)
    await expect(page.getByRole('group', { name: 'Security check' })).toHaveCount(0)
    expect(state.mutations).toEqual([])
    // Reloading an unchanged bundle must not manufacture assent to newer policy text.
    await page.goto(surfaces[0].url)
    await expect(page.getByText('Registration needs a refresh', { exact: true })).toBeVisible()
    await noCollectionControls(page)
    expect(state.mutations).toEqual([])
  })

  test('a newer API policy cannot expose signup controls in an older bundle', async ({ page, baseURL }) => {
    const state = await harness(page, baseURL!)
    state.respond = async () => answer({ ...READY, terms_version: '2026-10-25', eligibility_version: '2026-10-25' })
    await page.goto(surfaces[0].url)
    await expect(page.getByText('Registration needs a refresh', { exact: true })).toBeVisible()
    await noCollectionControls(page)
    expect(state.captchaRequests).toBe(0)
    expect(state.mutations).toEqual([])
  })

  for (const [name, response] of [['closed', answer(CLOSED)], ['unreachable', UNAVAILABLE]] as const) {
    test(`existing free account cannot begin checkout when readiness becomes ${name}`, async ({ page, baseURL }) => {
      const state = await harness(page, baseURL!)
      state.authenticated = true
      state.respond = async () => answer({ ...READY, checkout_available: true })
      await page.goto('/pricing')
      const button = page.getByRole('button', { name: /^(Start \d+-day free trial|Upgrade to Pro)$/ })
      await expect(button).toBeVisible()
      state.respond = async () => response
      await button.click()
      await expect(page.getByRole('button', { name: 'Checkout unavailable', exact: true })).toHaveAttribute('aria-disabled', 'true')
      expect(state.readinessRequests).toBeGreaterThanOrEqual(2)
      expect(state.mutations).toEqual([])
    })
  }

  test('existing beta account sees no claim or zero-price offer while checkout is closed', async ({ page, baseURL }) => {
    const state = await harness(page, baseURL!)
    state.authenticated = true
    state.betaMember = true
    await page.goto('/pricing')
    const unavailable = page.getByRole('button', { name: 'Checkout unavailable', exact: true })
    await expect(unavailable).toHaveAttribute('aria-disabled', 'true')
    await expect(page.getByText("You're a beta member. Pro is on us.", { exact: true })).toHaveCount(0)
    await expect(page.getByText('Free for beta members · no card required', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Pro', exact: true }).locator('..').getByText('$0', { exact: true })).toHaveCount(0)
    await unavailable.focus()
    await unavailable.press('Enter')
    await expect(unavailable).toBeFocused()
    await expect(page.getByRole('link', { name: 'Manage existing billing' })).toBeVisible()
    expect(state.mutations).toEqual([])
    // Positive control: this is a real beta-user UI fixture, not an unresolved/guest render.
    state.respond = async () => answer({ ...READY, checkout_available: true })
    await page.reload()
    await expect(page.getByText("You're a beta member. Pro is on us.", { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Claim Pro', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Pro', exact: true }).locator('..').getByText('$0', { exact: true })).toBeVisible()
    expect(state.mutations).toEqual([])
  })

  test('public privacy notice exposes no operator address until explicitly published', async ({ page, baseURL }) => {
    const state = await harness(page, baseURL!)
    await page.goto('/privacy')
    await expect(page.getByText(/Operator details are currently unavailable here/)).toBeVisible()
    await expect(page.locator('#main address')).toHaveCount(0)
    await expect(page.locator('#main').getByRole('link', { name: 'privacy@earningsnerd.io', exact: true }).first()).toHaveAttribute('href', 'mailto:privacy@earningsnerd.io')
    expect(state.mutations).toEqual([])
    state.respond = async () => answer(READY)
    await page.reload()
    await expect(page.locator('#main address')).toContainText(OPERATOR.legal_name)
    await expect(page.locator('#main address')).toContainText(OPERATOR.postal_address)
    await expect(page.locator('#main address')).toContainText(OPERATOR.contact_email)
  })
})
