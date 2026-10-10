import { createRequire } from 'node:module'
import { test, expect, type Page } from '@playwright/test'
import { settled } from './fixtures/contrast'
import { answerApi, API_ORIGIN, PANE, SUMMARY } from './fixtures/filing3Api'

/**
 * Text floors on the main routes, read from what Chromium renders (critique v3.1 DC-TERTIARY,
 * DET-OVL-1 and DET-OVL-2). DOM and computed-style measurements only: this is not a screen-reader
 * or visual test.
 *
 * Muted ink (DESIGN_SYSTEM §7, the rule-12 gate for DC-TERTIARY): every piece of text painted in the
 * tertiary ink clears 4.5:1 against what is actually behind it. Tertiary (#636A77) computes to 4.9:1
 * on the cream page ground, 4.8:1 on brand-weak, 5.2:1 on panel and 4.55:1 on a 10% info tint over
 * panel, so captions, counts and micro-labels may use it on any of those grounds; copy the reader
 * must read stays secondary. The ink is read from tailwind.config.js, so a token change cannot leave
 * the census looking at a colour nothing uses; the census must also find tertiary text, or a broken
 * probe would pass.
 * Light theme only: every dark pairing is the secondary-dark ink, which this change leaves alone.
 *
 * Heading outline (DET-OVL-1, DESIGN_SYSTEM §5): no visited route or state skips a level, in DOM
 * order (how the Impeccable detector reads it) and in the accessibility tree. The footer's column
 * titles (h3) sit under the footer's own visually hidden h2, so a page whose content ends at h1 (the
 * 404, /analysis, /search) no longer jumps from h1 to h3; a GuidanceCard that stands in for a page's
 * content under the h1 titles itself h2 (the four page-level card states below).
 *
 * Body text (DET-OVL-2): regression checks for the detector's two rules, not a documented design
 * rule (DESIGN.md lets local leading utilities override the scale): no paragraph of body text on the
 * homepage sets its line height under 1.3 times its size, and at 390px no body paragraph on the
 * filing page, with the Ask sheet open or closed, runs closer than the page's 16px side gutter to the
 * viewport edge. A deliberate exception updates these cases in the same change.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API origin is answered
 * inside the browser.
 */

const TAILWIND = createRequire(__filename)('../../tailwind.config.js') as {
  theme: { extend: { colors: { text: { tertiary: { light: string } } } } }
}
const hexToRgb = (hex: string) => {
  const n = parseInt(hex.replace('#', ''), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}
const TERTIARY_INK = hexToRgb(TAILWIND.theme.extend.colors.text.tertiary.light)
const LAUNCHER = 'button[aria-haspopup="dialog"][aria-label="Source"]'

const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const companyFiling = (id: number, filing_type: string, filing_date: string, report_date: string) => ({
  id, filing_type, filing_date: `${filing_date}T00:00:00+00:00`, report_date,
  accession_number: `0000320193-25-0000${id}`, document_url: `${FOLDER}doc-${id}.htm`, sec_url: FOLDER,
})

/** The company page and the signed-in dashboard, answered in the browser (the filing page uses filing3Api). */
async function answerSiteApi(page: Page, baseURL: string, signedIn: boolean) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  if (signedIn) await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (pathname) {
      case '/api/companies/AAPL':
        return json(200, { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' })
      case '/api/filings/company/AAPL':
        return json(200, [companyFiling(11, '10-K', '2025-10-31', '2025-09-27'), companyFiling(12, '10-Q', '2025-08-01', '2025-06-28'), companyFiling(14, '10-K', '2024-11-01', '2024-09-28')])
      case '/api/auth/me':
        return signedIn
          ? json(200, { id: 1, email: 'jordan@example.com', full_name: 'Jordan Whitaker', is_pro: false, is_beta: false, is_admin: false, email_verified: true })
          : json(401, { detail: 'Not authenticated' })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: 2, summaries_limit: 5, is_pro: false, month: '2026-10', qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3, analysis_used: 0, analysis_limit: 0 })
      case '/api/subscriptions/subscription':
        return json(200, { is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null, plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/watchlist/insights':
        return json(200, [{ company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' }, latest_filing: { id: 11, filing_type: '10-K', filing_date: '2025-10-31', period_end_date: '2025-09-27', summary_id: null, summary_status: 'ready', summary_created_at: null, summary_updated_at: null, needs_regeneration: false }, total_filings: 12 }])
      case '/api/dashboard/feed':
        return json(200, { items: [] })
      case '/api/saved-summaries/':
      case '/api/watchlist/':
        return json(200, [])
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}

type Route = { name: string; path: string; status?: number; open: (page: Page, baseURL: string) => Promise<void>; ready: (page: Page) => Promise<void> }
const ROUTES: Route[] = [
  { name: 'home', path: '/', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() },
  { name: 'pricing', path: '/pricing', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Pricing' })).toBeVisible() },
  { name: 'company', path: '/company/AAPL', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('button', { name: /^Report year 2025\b/ })).toBeVisible() },
  { name: 'filing', path: '/filing/3', open: (p, b) => answerApi(p, b, 'anon'), ready: (p) => expect(p.getByText('On this page')).toBeVisible() },
  { name: 'dashboard', path: '/dashboard', open: (p, b) => answerSiteApi(p, b, true), ready: (p) => expect(p.getByRole('heading', { level: 2, name: 'Your companies' })).toBeVisible() },
  { name: 'not found', path: '/no-such-page', status: 404, open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible() },
]

async function visit(page: Page, baseURL: string, route: Route) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })
  await route.open(page, baseURL)
  const response = await page.goto(route.path)
  if (route.status) expect(response?.status()).toBe(route.status)
  await route.ready(page)
  await expect(page.getByRole('contentinfo')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

/** Every visible text element painted in `ink`, with its WCAG contrast over the composited ground. */
const inkCensus = (page: Page, ink: string) =>
  page.evaluate((ink) => {
    type Rgba = { r: number; g: number; b: number; a: number }
    const parse = (c: string): Rgba => {
      const m = c.match(/rgba?\(([^)]+)\)/)
      if (!m) throw new Error(`unparsed colour ${c}`)
      const [r, g, b, a = '1'] = m[1].split(/[\s,/]+/).filter(Boolean)
      return { r: +r, g: +g, b: +b, a: +a }
    }
    const over = (t: Rgba, u: Rgba): Rgba => ({ r: t.r * t.a + u.r * (1 - t.a), g: t.g * t.a + u.g * (1 - t.a), b: t.b * t.a + u.b * (1 - t.a), a: 1 })
    const lum = ({ r, g, b }: Rgba) => {
      const ch = (v: number) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4 }
      return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    }
    const found: { text: string; ratio: number }[] = []
    for (const el of document.querySelectorAll('body *')) {
      const s = getComputedStyle(el)
      if (s.color !== ink) continue
      const text = [...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent ?? '').join('').trim()
      const box = el.getBoundingClientRect()
      if (!text || box.width <= 1 || box.height <= 1 || !el.checkVisibility({ visibilityProperty: true })) continue
      const layers: Rgba[] = []
      for (let n: Element | null = el; n; n = n.parentElement) {
        const bg = parse(getComputedStyle(n).backgroundColor)
        if (bg.a > 0) layers.push(bg)
        if (bg.a === 1) break
      }
      if (!layers.length || layers[layers.length - 1].a !== 1) layers.push({ r: 255, g: 255, b: 255, a: 1 })
      const ground = layers.reduceRight((under, top) => over(top, under))
      const [hi, lo] = [lum(over(parse(s.color), ground)), lum(ground)].sort((x, y) => y - x)
      found.push({ text: text.slice(0, 48), ratio: Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100 })
    }
    return found
  }, ink)

/** Heading levels in DOM order (the detector's reading) and as the accessibility tree exposes them. */
const headingSkips = (page: Page) =>
  page.evaluate(() => {
    const all = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')]
    const exposed = all.filter((h) => !h.closest('[aria-hidden="true"]') && h.checkVisibility({ visibilityProperty: true }))
    const skips = (list: Element[]) => {
      const out: string[] = []
      let prev = 0
      let prevText = ''
      for (const h of list) {
        const level = Number(h.tagName[1])
        const text = (h.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)
        if (prev && level > prev + 1) out.push(`h${prev} "${prevText}" -> h${level} "${text}"`)
        prev = level
        prevText = text
      }
      return out
    }
    return { dom: skips(all), exposed: skips(exposed), footer: [...document.querySelectorAll('footer h2, footer h3')].map((h) => h.tagName) }
  })

test.describe('main routes at 1440x900, light theme', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const route of ROUTES) {
    test(`${route.name}: muted ink clears AA and the heading outline skips no level`, async ({ page, baseURL }) => {
      await visit(page, baseURL!, route)
      await page.mouse.move(0, 0)

      const census = await inkCensus(page, TERTIARY_INK)
      // Anti-vacuity: the homepage keeps tertiary labels inside its sample cards (on panel and white).
      if (route.name === 'home') expect(census.length, `tertiary text found on ${route.name}`).toBeGreaterThan(10)
      // Soft: one run reports every floor a route misses.
      expect.soft(census.filter((c) => c.ratio < 4.5), `tertiary text under 4.5:1 on ${route.name}`).toEqual([])

      if (route.name === 'company') {
        // The year header brightens to brand-weak under the pointer; its filing count stays legible.
        const header = page.getByRole('button', { name: /^Report year 2025\b/ })
        await header.hover()
        await settled(header)
        expect.soft((await inkCensus(page, TERTIARY_INK)).filter((c) => c.ratio < 4.5), 'tertiary text under 4.5:1 with a year header hovered').toEqual([])
      }

      const outline = await headingSkips(page)
      expect.soft(outline.dom, `skipped heading levels on ${route.name} (DOM order)`).toEqual([])
      expect.soft(outline.exposed, `skipped heading levels on ${route.name} (accessibility tree)`).toEqual([])
      expect.soft(outline.footer.join(' '), 'the footer opens its own h2 before its h3 column titles').toMatch(/^H2( H3)+$/)
    })
  }
})

/**
 * A GuidanceCard that stands in for a page's content sits directly under the page h1, so its title is
 * an h2 there (it is an h3 by default, for a card inside an h2 section). These are the states where a
 * reader lands on one: a guest, or a signed-in user whose run fails, opening a filing that has no
 * summary yet (where the company page's filing links lead); a stored summary whose writer failed; an
 * empty watchlist. Outline only: the watchlist's muted ink is a named candidate, not this gate's.
 */
const CARD_STATES: { name: string; route: Route; card: string }[] = [
  {
    name: 'filing without a summary, guest (the signup gate)',
    route: { ...ROUTES[3], open: (p, b) => noSummary(p, b, 'anon'), ready: (p) => expect(p.getByRole('link', { name: 'Create free account' })).toBeVisible() },
    card: 'Create a free account to analyze this filing',
  },
  {
    name: 'filing without a summary, signed in, the run fails',
    route: { ...ROUTES[3], open: (p, b) => noSummary(p, b, 'pro'), ready: (p) => expect(p.getByRole('button', { name: 'Retry generation' })).toBeVisible() },
    card: 'Generation interrupted',
  },
  {
    name: 'filing whose stored summary has a writer error',
    route: {
      ...ROUTES[3],
      open: async (p, b) => {
        await answerApi(p, b, 'anon')
        await p.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3', (r) =>
          r.fulfill({ status: 200, headers: corsFor(b), json: { ...SUMMARY, raw_summary: { ...(SUMMARY.raw_summary as object), writer_error: 'writer failed' } } }),
        )
      },
      ready: (p) => expect(p.getByRole('button', { name: 'Retry' })).toBeVisible(),
    },
    card: 'Summary temporarily unavailable',
  },
  {
    name: 'empty watchlist',
    route: {
      name: 'watchlist',
      path: '/dashboard/watchlist',
      open: async (p, b) => {
        await answerSiteApi(p, b, true)
        await p.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/watchlist/insights', (r) =>
          r.fulfill({ status: 200, headers: corsFor(b), json: [] }),
        )
      },
      // The card itself, at whatever level it renders, so the outline is read once the insights have
      // landed (a loading state may already paint the page h1).
      ready: (p) => expect(p.getByRole('heading', { name: 'No watchlist companies yet' })).toBeVisible(),
    },
    card: 'No watchlist companies yet',
  },
]

const corsFor = (baseURL: string) => ({ 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' })
/** The filing fixture with no stored summary: a guest gets the signup gate; a signed-in run starts and fails (the stream is not answered). */
async function noSummary(page: Page, baseURL: string, who: 'anon' | 'pro') {
  await answerApi(page, baseURL, who)
  await page.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3', (r) =>
    r.fulfill({ status: 404, headers: corsFor(baseURL), json: { detail: 'Summary not found' } }),
  )
}

test.describe('page-level guidance cards at 1440x900, light theme', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const state of CARD_STATES) {
    test(`${state.name}: the card's title is an h2 under the page h1, no level skipped`, async ({ page, baseURL }) => {
      await visit(page, baseURL!, state.route)
      const outline = await headingSkips(page)
      expect.soft(outline.dom, `skipped heading levels: ${state.name} (DOM order)`).toEqual([])
      expect.soft(outline.exposed, `skipped heading levels: ${state.name} (accessibility tree)`).toEqual([])
      // Anti-vacuity: the card is on the page, as the h2 the outline needs.
      await expect(page.getByRole('heading', { level: 2, name: state.card })).toBeVisible()
    })
  }
})

/** Body text with a line height under 1.3 times its size (the detector's tight-leading rule). */
const tightLeading = (page: Page) =>
  page.evaluate(() => {
    const out: string[] = []
    for (const el of document.querySelectorAll('body *')) {
      if (/^H[1-6]$/.test(el.tagName) || !el.checkVisibility()) continue
      const own = [...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent ?? '').join('').trim()
      if (own.length <= 10 || (el.textContent ?? '').trim().length <= 50) continue
      const s = getComputedStyle(el)
      const ratio = parseFloat(s.lineHeight) / parseFloat(s.fontSize)
      if (ratio < 1.3) out.push(`${own.slice(0, 40)} (${s.fontSize} / ${s.lineHeight})`)
    }
    return out
  })

/** Body paragraphs whose box runs closer than 16px to either viewport edge (the detector's rule). */
const edgeParagraphs = (page: Page) =>
  page.evaluate(() => {
    const vw = document.documentElement.clientWidth
    const out: string[] = []
    for (const el of document.querySelectorAll('p, li')) {
      const own = [...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent ?? '').join('').trim()
      if (own.length <= 10 || (el.textContent ?? '').trim().length <= 40 || el.closest('nav, header') || !el.checkVisibility()) continue
      const s = getComputedStyle(el)
      const box = el.getBoundingClientRect()
      const ownGround = s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent'
      if (ownGround || s.position === 'fixed' || s.position === 'absolute' || box.width / vw <= 0.5) continue
      if (box.left < 16 || box.right > vw - 16) out.push(`${own.slice(0, 40)} (left ${Math.round(box.left)}px, right ${Math.round(vw - box.right)}px)`)
    }
    return out
  })

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`homepage body text keeps at least 1.3 line height at ${viewport.width}px`, async ({ page, baseURL }) => {
    await page.setViewportSize(viewport)
    await visit(page, baseURL!, ROUTES[0])
    await expect(page.getByRole('heading', { name: 'Also in Pro' })).toBeAttached()
    expect(await tightLeading(page)).toEqual([])
  })
}

test('at 390px the filing page keeps body text 16px off the edges, with the Ask sheet closed and open', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await visit(page, baseURL!, { ...ROUTES[3], open: (p, b) => answerApi(p, b, 'pro'), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() })
  expect.soft(await edgeParagraphs(page), 'sheet closed').toEqual([])

  await page.locator(LAUNCHER).click()
  await expect(page.locator(PANE).getByPlaceholder('Ask about this filing…')).toBeVisible()
  await settled(page.locator(PANE))
  expect(await edgeParagraphs(page), 'sheet open').toEqual([])
})
