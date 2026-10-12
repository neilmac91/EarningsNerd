import { test, expect, type Page } from '@playwright/test'

/**
 * P-09 (Design Critique 2026-10): loading and motion honesty.
 *
 * 1. Under reduced motion nothing moves: on the public pages with entrances (home, and sign-in and sign-up
 *    with their email forms open) and in the dashboard settings and watchlist loading states, the document
 *    has no CSS animation at all, running or finished. Every animation utility carries its guard (earningsnerd/no-unguarded-animation)
 *    and the globals.css classes guard themselves (designRules.spec.ts).
 * 2. With motion allowed, the same loading state does run its shimmer, so check 1 is not vacuous.
 * 3. Account settings and watchlist insights load as their own frame over bones in the shapes of the cards
 *    that replace them (fullPageSpinnerGate.spec.ts): when the data lands, the first card takes the place of
 *    its bones and the title stays where it was; on settings, whose first card has a fixed shape, the second
 *    lands within a few pixels of its bones too.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md). The API is answered inside the
 * browser with page.route, and the middleware's session gate is satisfied by its presence cookie, as in
 * dashboard-phone-layout.spec.ts. Holding /api/auth/me keeps a page in its loading state.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin

const FIXTURES: Record<string, unknown> = {
  '/api/auth/me': { id: 1, email: 'avery@example.com', full_name: 'Avery', is_pro: false, is_beta: false, is_admin: false, email_verified: true },
  '/api/watchlist/insights': [
    {
      company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
      latest_filing: { id: 100, filing_type: '10-K', filing_date: '2026-08-03', period_end_date: '2026-06-30', summary_id: null, summary_status: 'ready', summary_created_at: null, summary_updated_at: null, needs_regeneration: false },
      total_filings: 12,
    },
  ],
}

function hold() {
  let release!: () => void
  const released = new Promise<void>((resolve) => { release = resolve })
  return { release, released }
}

/** Signed in, with /api/auth/me answered once `me` resolves (at once without it). */
async function signIn(page: Page, baseURL: string, me?: Promise<void>) {
  const origin = new URL(baseURL).origin
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname === '/api/auth/me' && me) await me
    const body = FIXTURES[pathname]
    return body === undefined
      ? route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } })
      : route.fulfill({ status: 200, headers: cors, json: body })
  })
}

/** Every CSS keyframe animation in the document, running or finished, named with the element it moves.
 *  Transitions are left out: a field's focus ring easing in is state feedback, not motion. */
const animations = (page: Page) =>
  page.evaluate(() =>
    document
      .getAnimations()
      .filter((a): a is CSSAnimation => a instanceof CSSAnimation)
      .map((a) => {
        const target = (a.effect as KeyframeEffect | null)?.target as Element | null
        return `${a.animationName} (${a.playState}) on <${target?.tagName.toLowerCase()} class="${target?.getAttribute('class') ?? ''}">`
      }),
  )

/** The top of the first card (Card's rounded-xl recipe) at or around the element. */
const cardTop = (page: Page, selector: string) =>
  page.locator(selector).first().evaluate((el) => el.closest('.rounded-xl')!.getBoundingClientRect().top)

test.describe('under reduced motion', () => {
  test.use({ reducedMotion: 'reduce' })

  for (const path of ['/', '/login', '/register']) {
    test(`${path} runs no animation`, async ({ page }) => {
      await page.goto(path)
      await expect(page.locator('h1').first()).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      expect(await animations(page)).toEqual([])
      if (path === '/') return
      // The email form's own entrance.
      await page.getByRole('button', { name: /^(Continue|Sign up) with email$/ }).click()
      await expect(page.getByLabel(/^Email/)).toBeVisible()
      expect(await animations(page)).toEqual([])
    })
  }

  for (const [path, title, wait] of [
    ['/dashboard/settings', 'Account settings', 'Loading your settings'],
    ['/dashboard/watchlist', 'Watchlist insights', 'Loading your watchlist'],
  ]) {
    test(`${path} loads as still bones`, async ({ page, baseURL }) => {
      const me = hold()
      await signIn(page, baseURL!, me.released)
      try {
        await page.goto(path)
        await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
        await expect(page.getByRole('status', { name: wait })).toBeVisible()
        expect(await animations(page)).toEqual([])
      } finally {
        me.release()
      }
    })
  }
})

test('with motion allowed, the settings bones shimmer', async ({ page, baseURL }) => {
  const me = hold()
  await signIn(page, baseURL!, me.released)
  try {
    await page.goto('/dashboard/settings')
    await expect(page.getByRole('status', { name: 'Loading your settings' })).toBeVisible()
    const running = await animations(page)
    expect(running.filter((a) => a.startsWith('shimmer (running)')).length).toBeGreaterThan(0)
  } finally {
    me.release()
  }
})

test('account settings: the sections land where their bones stood', async ({ page, baseURL }) => {
  const me = hold()
  await signIn(page, baseURL!, me.released)
  try {
    await page.goto('/dashboard/settings')
    const title = page.getByRole('heading', { level: 1, name: 'Account settings' })
    await expect(page.getByRole('status', { name: 'Loading your settings' })).toBeVisible()
    await expect(page.locator('.animate-spin')).toHaveCount(0)
    const titleTop = (await title.boundingBox())!.y
    const boneTop = await cardTop(page, '[aria-label="Loading your settings"] > .rounded-xl')
    const nextBoneTop = await cardTop(page, '[aria-label="Loading your settings"] > .rounded-xl:nth-child(2)')

    me.release()
    await expect(page.getByRole('heading', { name: 'Billing' })).toBeVisible()
    expect(await cardTop(page, 'h2:text-is("Profile")')).toBe(boneTop)
    expect((await title.boundingBox())!.y).toBe(titleTop)
    // Profile's bones are its own shape (fields and Save), so Billing lands where its bones stood too.
    expect(Math.abs((await cardTop(page, 'h2:text-is("Billing")')) - nextBoneTop)).toBeLessThanOrEqual(8)
  } finally {
    me.release()
  }
})

test('watchlist insights: the first card lands where its bone stood', async ({ page, baseURL }) => {
  const me = hold()
  await signIn(page, baseURL!, me.released)
  try {
    await page.goto('/dashboard/watchlist')
    const title = page.getByRole('heading', { level: 1, name: 'Watchlist insights' })
    await expect(page.getByRole('status', { name: 'Loading your watchlist' })).toBeVisible()
    await expect(page.locator('.animate-spin')).toHaveCount(0)
    const titleTop = (await title.boundingBox())!.y
    const boneTop = await cardTop(page, '[aria-label="Loading your watchlist"] > .rounded-xl')

    me.release()
    await expect(page.getByRole('heading', { name: 'Apple Inc.' })).toBeVisible()
    expect(await cardTop(page, 'main h2:text-is("Apple Inc.")')).toBe(boneTop)
    expect((await title.boundingBox())!.y).toBe(titleTop)
  } finally {
    me.release()
  }
})
