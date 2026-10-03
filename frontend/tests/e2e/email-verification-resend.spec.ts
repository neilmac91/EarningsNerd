import { test, expect, type Page } from '@playwright/test'

/**
 * EmailVerificationModal's "Resend link" keeps keyboard focus through its own success and failure
 * (lessons/frontend-busy-controls-stay-focusable.md (e), (h)). jsdom never blurs a control that turns
 * natively `disabled`, so only a real browser can see the old bug: the focused button flipped to
 * `disabled` on success, Chromium blurred it, and focus fell to <body> inside the open dialog.
 *
 * Chromium blurs a newly disabled control at its next rendering update, so every focus read waits
 * for two animation frames first; an immediate read, or a retrying `toBeFocused()`, could pass on a
 * regression before the blur lands.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside
 * the browser with page.route fixtures, and the middleware's session gate is satisfied by its
 * non-credential presence cookie. The modal opens on EMAIL_VERIFICATION_REQUIRED_EVENT, which the
 * axios interceptor dispatches on a gated 403; the spec dispatches it directly.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const EMAIL = 'unverified@example.com'

function fixture(pathname: string): unknown {
  switch (pathname) {
    case '/api/auth/me':
      return { id: 1, email: EMAIL, full_name: 'Ada', is_pro: false, is_beta: false, is_admin: false, email_verified: false }
    case '/api/subscriptions/usage':
      return { summaries_used: 0, summaries_limit: 5, is_pro: false, month: '2026-10', qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3, analysis_used: 0, analysis_limit: 0 }
    case '/api/subscriptions/subscription':
      return { is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null, plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false }
    case '/api/dashboard/feed':
      return { items: [] }
    case '/api/dashboard/calendar/upcoming':
      return { events: [] }
    case '/api/watchlist/insights':
    case '/api/saved-summaries/':
    case '/api/watchlist/':
      return []
    default:
      return undefined
  }
}

type Resend = { status: number; body: unknown }
const SENT: Resend = { status: 200, body: { message: 'If that email has an unverified account, a new verification link is on its way.' } }
const LIMITED: Resend = { status: 429, body: { detail: 'Too many resend requests. Please wait before trying again.' } }
/** Resend under each of its names: idle, busy, sent. */
const RESEND = /^(Resend link|Sending…|Link sent)$/

async function openPrompt(page: Page, baseURL: string, theme: 'light' | 'dark', resend: Resend) {
  const origin = new URL(baseURL).origin
  const requests = { resend: 0 }
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.addInitScript((t) => {
    localStorage.setItem('theme', t)
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: 'x' }))
  }, theme)
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, async (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname === '/api/auth/resend-verification') {
      requests.resend += 1
      // Slow enough that the busy state is on screen while the second Enter lands.
      await new Promise((resolve) => setTimeout(resolve, 400))
      return route.fulfill({ status: resend.status, headers: cors, json: resend.body })
    }
    const body = fixture(pathname)
    return body === undefined
      ? route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } })
      : route.fulfill({ status: 200, headers: cors, json: body })
  })
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: "What's new" })).toBeVisible()
  await page.evaluate(() => window.dispatchEvent(new Event('email-verification-required')))
  const dialog = page.getByRole('dialog', { name: 'Verify your email to continue' })
  await expect(dialog.getByText(EMAIL)).toBeVisible()
  return { dialog, requests }
}

/** The focused element after the next rendering update, when Chromium has applied any blur. */
async function settledFocus(page: Page) {
  return page.evaluate(
    () =>
      new Promise<{ name: string; tag: string }>((resolve) =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            const el = document.activeElement as HTMLElement | null
            if (!el || el === document.body) return resolve({ tag: 'BODY', name: '' })
            resolve({ tag: el.tagName, name: (el.textContent ?? '').replace(/\s+/g, ' ').trim() })
          }),
        ),
      ),
  )
}

for (const theme of ['light', 'dark'] as const) {
  test(`Resend link keeps focus through a successful send (${theme})`, async ({ page, baseURL }) => {
    const { dialog, requests } = await openPrompt(page, baseURL!, theme, SENT)
    const resend = dialog.getByRole('button', { name: RESEND })
    await resend.focus()
    await page.keyboard.press('Enter')
    await expect(resend).toHaveAttribute('aria-busy', 'true')
    await page.keyboard.press('Enter')

    await expect(resend).toHaveAccessibleName('Link sent')
    await expect(resend).toHaveAttribute('aria-disabled', 'true')
    const sent = resend
    await expect(dialog.getByRole('status')).toContainText('New link sent.')
    expect(await settledFocus(page)).toEqual({ tag: 'BUTTON', name: 'Link sent' })
    expect(await sent.evaluate((el: HTMLButtonElement) => el.disabled)).toBe(false)

    // The unavailable look fades the label and hairline, never the element, so the focus ring keeps
    // its full strength; dark's hairline is brand-weak-dark, half of the live 0.28.
    const look = await sent.evaluate((el) => {
      const cs = getComputedStyle(el)
      return { focusVisible: el.matches(':focus-visible'), opacity: cs.opacity, shadow: cs.boxShadow, border: cs.borderTopColor }
    })
    expect(look.focusVisible).toBe(true)
    expect(look.opacity).toBe('1')
    expect(look.shadow).toContain(theme === 'dark' ? 'rgba(127, 178, 149, 0.55)' : 'rgba(79, 122, 99, 0.5)')
    if (theme === 'dark') expect(look.border).toBe('rgba(127, 178, 149, 0.14)')

    await page.keyboard.press('Enter')
    expect(requests.resend).toBe(1)
    await page.keyboard.press('Tab')
    expect(await settledFocus(page)).toEqual({ tag: 'BUTTON', name: "I've verified" })
  })

  test(`Resend link keeps focus and says what to do after a 429 (${theme})`, async ({ page, baseURL }) => {
    const { dialog, requests } = await openPrompt(page, baseURL!, theme, LIMITED)
    const resend = dialog.getByRole('button', { name: RESEND })
    await resend.focus()
    await page.keyboard.press('Enter')

    await expect(dialog.getByRole('alert')).toContainText("We've sent several links recently.")
    await expect(resend).toHaveAttribute('aria-disabled', 'true')
    expect(await settledFocus(page)).toEqual({ tag: 'BUTTON', name: 'Resend link' })
    await page.keyboard.press('Enter')
    expect(requests.resend).toBe(1)
  })
}
