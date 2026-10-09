import { createRequire } from 'node:module'
import { test, expect, type Page } from '@playwright/test'
import { settled } from './fixtures/contrast'
import { answerApi, API_ORIGIN } from './fixtures/filing3Api'

/**
 * Text floors on the main routes, read from what Chromium renders (critique v3.1 DC-TERTIARY).
 * DOM and computed-style measurements only: this is not a screen-reader or visual test.
 *
 * Muted ink (DESIGN_SYSTEM §2 and §7, the rule-12 gate for DC-TERTIARY): every piece of text painted
 * in the tertiary ink clears 4.5:1 against what is actually behind it. Tertiary (#6B7280) measures
 * 4.35:1 on the cream page ground, 4.26:1 on brand-weak and 4.04:1 on a 10% info tint, so muted
 * text on those grounds uses the secondary ink; tertiary stays on panel and white (4.63:1, 4.83:1).
 * The ink is read from tailwind.config.js, so a token change cannot leave the census looking at a
 * colour nothing uses; the census must also find tertiary text, or a broken probe would pass.
 * Light theme only: every dark pairing is the secondary-dark ink, which this change leaves alone.
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

test.describe('main routes at 1440x900, light theme', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const route of ROUTES) {
    test(`${route.name}: muted ink clears AA`, async ({ page, baseURL }) => {
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
    })
  }
})
