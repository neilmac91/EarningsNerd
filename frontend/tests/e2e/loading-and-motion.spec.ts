import { test, expect, type Page } from '@playwright/test'
import { answerApi } from './fixtures/filing3Api'
import { answerLegalReadiness } from './fixtures/legalReady'

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
 * 4. The filing page with a summary in flight (the generation stream held open, as text-floors.spec.ts holds it,
 *    so the progress card stays at its first stage with every step pending): under reduced motion the document
 *    has no CSS animation there either, and the card's live-status line ("10-K · Opening the filing…",
 *    StreamingSummaryDisplay.tsx) reads the same after longer than two ambient loops (2 x 1800ms, the longest
 *    motion token), with motion allowed too. The line changes only with the backend's stage, never on a timer
 *    (WCAG 2.2.2): the rotating callout it replaced changed on its own.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md). The API is answered inside the
 * browser with page.route, and the middleware's session gate is satisfied by its presence cookie, as in
 * dashboard-phone-layout.spec.ts. Holding /api/auth/me keeps a page in its loading state; holding the generation
 * stream keeps a filing's run in flight (fixtures/filing3Api.ts answers the rest of that page).
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

/** The generating card's live-status line at its first stage: the filing's form code, then the fetching pool's one
 *  line (StreamingSummaryDisplay.tsx STATUS_LINES). The held stream sends no stage and no elapsed time, so the card
 *  never leaves initializing and never stalls. */
const STATUS_LINE = '10-K · Opening the filing…'

/** The filing page's own browser state, as its sibling specs seed it: the coachmark dismissed and consent given, so
 *  neither surface joins the card under test. */
const seedFilingPage = (page: Page) =>
  page.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })

/** A signed-in run in flight on a filing with no summary, the hold text-floors.spec.ts uses: fixtures/filing3Api.ts
 *  answers the page for a Pro reader, the stored summary answers 404 so the page starts a run, and the stream request
 *  is never answered, so the progress card stays up at its first stage. Resolves with the card's live-status line, the
 *  heading's next sibling. */
async function openRunInFlight(page: Page, baseURL: string) {
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await answerApi(page, baseURL, 'pro')
  // Registered after answerApi, so these answer first.
  await page.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3', (route) =>
    route.fulfill({ status: 404, headers: cors, json: { detail: 'Summary not found' } }),
  )
  await page.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3/generate-stream', () => new Promise<void>(() => {}))
  await page.goto('/filing/3')
  const heading = page.getByRole('heading', { level: 2, name: 'Generating the summary' })
  await expect(heading).toBeVisible()
  await expect(page.getByText('Writing the summary and checking figures against the filing', { exact: true })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  return heading.locator('xpath=following-sibling::p[1]')
}

test.describe('under reduced motion', () => {
  test.use({ reducedMotion: 'reduce' })

  for (const path of ['/', '/login', '/register']) {
    test(`${path} runs no animation`, async ({ page, baseURL }) => {
      if (path === '/register') await answerLegalReadiness(page, baseURL!)
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

  test('/filing/3 with a summary in flight runs no animation, and its status line holds for longer than two ambient loops', async ({ page, baseURL }) => {
    await seedFilingPage(page)
    const line = await openRunInFlight(page, baseURL!)
    expect(await animations(page)).toEqual([])
    await expect(line).toHaveText(STATUS_LINE)
    // Longer than 2 x 1800ms (the ambient token, the longest motion token): a line on a timer would have changed by
    // now. This one changes only with the backend's stage, which the held stream never sends, so there is nothing
    // to await but the clock.
    await page.waitForTimeout(4000)
    await expect(line).toHaveText(STATUS_LINE)
    expect(await animations(page)).toEqual([])
  })
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

// The no-timer property is the component's, not the motion setting's: with motion allowed the status line's mount
// crossfade runs once (animate-fadeIn, on the keyed span), and the line still reads the same after the same wait.
test('with motion allowed, the in-flight status line holds for longer than two ambient loops too', async ({ page, baseURL }) => {
  await seedFilingPage(page)
  const line = await openRunInFlight(page, baseURL!)
  await expect(line).toHaveText(STATUS_LINE)
  // Longer than 2 x 1800ms (the ambient token), as under reduced motion above.
  await page.waitForTimeout(4000)
  await expect(line).toHaveText(STATUS_LINE)
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
