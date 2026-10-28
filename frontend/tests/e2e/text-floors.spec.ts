import { legalReady } from './fixtures/legalReady'
import { readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'
import { settled, textContrast } from './fixtures/contrast'
import { answerAnalysisApi, runAnalysis } from './fixtures/analysisLayoutApi'
import { calendarWeekReady, pinCalendarWeek } from './fixtures/calendarWeek'
import { answerApi, API_ORIGIN, PANE, SUMMARY } from './fixtures/filing3Api'
import { answerSearch, runSearch } from './fixtures/searchApi'
import { AUTH_ROUTES, isAuthRoute } from '../../lib/authShellRoutes'
import { STATIC_ENTRIES } from '../../app/sitemap'

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
 * The census runs in both themes (E202 (1)): in dark, muted text takes tertiary's dark twin (gray-400 #9CA3AF), measured
 * the same way against what is behind it, tints included; tests/unit/figureSurfaceInks.spec.ts also holds that twin
 * text-safe on the bare dark panel and page.
 *
 * The waitlist's join link (E82), in both themes: the pill rests at the secondary recipe's hover fill
 * (`bg-brand-weak`; in dark a shade stronger, `bg-brand-dark/15` beside the recipe's `brand-weak-dark` at 0.14)
 * and takes its pressed fill under the pointer (`hover:bg-brand-border/60`, dark
 * `dark:hover:bg-brand-border-dark`). Per theme: the theme took, the label
 * is the recipe's sage ink (read from tailwind.config.js, so the case measures that label), `:hover` is on the
 * link and its fill changes, and the label clears 4.5:1 on what is behind it at rest and hovered. The ratio is
 * read unrounded: on the How it works card the dark label computes to 4.500005:1 on the hovered fill, where a
 * ratio rounded to two places would pass 4.495:1. themePairs.spec.ts holds the light hover to its dark twin.
 *
 * Heading outline (DET-OVL-1, DESIGN_SYSTEM §5): no visited route or state skips a level, in DOM
 * order (how the Impeccable detector reads it) and in the accessibility tree. The footer's column
 * titles (h3) sit under the footer's own visually hidden h2, so a page whose content ends at h1 (the
 * 404, /search, /analysis before a run) no longer jumps from h1 to h3; a GuidanceCard that stands in for a page's
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
  theme: { extend: { colors: { text: { tertiary: { light: string; dark: string } }; brand: { strong: string; 'strong-dark': string } } } }
}
const hexToRgb = (hex: string) => {
  const n = parseInt(hex.replace('#', ''), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}
const TERTIARY_INK = hexToRgb(TAILWIND.theme.extend.colors.text.tertiary.light)
const TERTIARY_INK_DARK = hexToRgb(TAILWIND.theme.extend.colors.text.tertiary.dark)
/** The secondary recipe's label ink, per theme (`text-brand-strong`, `dark:text-brand-strong-dark`). */
const BRAND_INK = {
  light: hexToRgb(TAILWIND.theme.extend.colors.brand.strong),
  dark: hexToRgb(TAILWIND.theme.extend.colors.brand['strong-dark']),
}
const LAUNCHER = 'button[aria-haspopup="dialog"][aria-label="Source"]'
/** The in-flight card's pending step, the label the "summary in flight" route waits for. */
const PENDING_STEP = 'Writing the summary and checking figures against the filing’s data'

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
      case '/api/legal/readiness':
        return json(200, legalReady)
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
      case '/api/dashboard/calendar/upcoming':
        // The dashboard's Upcoming earnings card, there while CI's e2e build turns the calendar on.
        return json(200, { events: [{ ticker: 'AAPL', company_name: 'Apple Inc.', earnings_date: '2026-10-29', time: 'amc', eps_estimated: 1.78, revenue_estimated: null }] })
      case '/api/saved-summaries/':
      case '/api/watchlist/':
        return json(200, [])
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}

type Route = {
  name: string
  path: string
  status?: number
  open: (page: Page, baseURL: string) => Promise<void>
  ready: (page: Page) => Promise<void>
  /** Fold every ancestor's opacity into the text's ink, as Chromium paints it (the in-flight progress card,
      whose pending steps once sat at opacity-40, 2.1:1). Opt-in while the other routes' fades are unmeasured. */
  foldOpacity?: boolean
}
const ROUTES: Route[] = [
  { name: 'home', path: '/', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() },
  { name: 'pricing', path: '/pricing', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Pricing' })).toBeVisible() },
  { name: 'company', path: '/company/AAPL', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('button', { name: /^Report year 2025\b/ })).toBeVisible() },
  { name: 'filing', path: '/filing/3', open: (p, b) => answerApi(p, b, 'anon'), ready: (p) => expect(p.getByText('On this page')).toBeVisible() },
  {
    name: 'dashboard',
    path: '/dashboard',
    open: (p, b) => answerSiteApi(p, b, true),
    ready: async (p) => {
      await expect(p.getByRole('heading', { level: 2, name: 'Your companies' })).toBeVisible()
      await expect(p.getByText('Est. EPS $1.78', { exact: true })).toBeVisible()
    },
  },
  { name: 'not found', path: '/no-such-page', status: 404, open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible() },
  {
    // A signed-in run in flight on a filing with no summary: the stream request is held open, so the
    // progress card stays up with every step still pending (filing/F14). Its pending labels are tertiary
    // ink at full opacity; folded opacity makes the census see what a faded label would paint.
    name: 'filing, a summary in flight (pending steps)',
    path: '/filing/3',
    foldOpacity: true,
    open: async (p, b) => {
      await noSummary(p, b, 'pro')
      await p.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3/generate-stream', () => new Promise<void>(() => {}))
    },
    ready: async (p) => {
      await expect(p.getByRole('heading', { level: 2, name: 'Generating the summary' })).toBeVisible()
      await expect(p.getByText(PENDING_STEP, { exact: true })).toBeVisible()
      // The status line crossfades in on mount (animate-fadeIn): the census reads the header once that has finished, never mid-opacity.
      await settled(p.getByRole('heading', { level: 2, name: 'Generating the summary' }).locator('xpath=..'))
    },
  },
  {
    name: 'legacy markdown filing',
    path: '/filing/3',
    open: async (p, b) => {
      await answerApi(p, b, 'anon')
      await p.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3', (r) =>
        r.fulfill({
          status: 200,
          headers: corsFor(b),
          json: {
            ...SUMMARY,
            rendered_sections: [],
            business_overview: '## Executive Summary\n\nThe retained summary introduces the filing.\n\n## Financial highlights\n\nRevenue grew during the period.\n\n### Revenue context\n\nThe filing describes the sources of that growth.',
          },
        }),
      )
    },
    ready: async (p) => {
      await expect(p.getByRole('heading', { level: 2, name: 'Summary', exact: true })).toBeVisible()
      await expect(p.getByRole('heading', { level: 2, name: 'Financial highlights', exact: true })).toBeVisible()
      await expect(p.getByRole('heading', { level: 3, name: 'Revenue context', exact: true })).toBeVisible()
    },
  },
  {
    // The route error boundary (app/error.tsx) replaces the page, so its card opens the outline with the
    // page's h1 (UA-50). Forced by a malformed company: a numeric name on the coverage-unavailable state
    // makes formatCompanyName throw while the page renders.
    name: 'route error boundary',
    path: '/company/AAPL',
    open: async (p, b) => {
      await answerSiteApi(p, b, false)
      await p.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/companies/AAPL', (r) =>
        r.fulfill({ status: 200, headers: corsFor(b), json: { id: 1, cik: '320193', ticker: 'AAPL', name: 42, exchange: 'NASDAQ', coverage_status: 'unsupported_foreign' } }),
      )
    },
    ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Something went wrong' })).toBeVisible(),
  },
  {
    // Multi-Period Analysis for a Pro reader, read once a run has finished: META's coverage, dataset and narrative
    // are answered from the analysis layout fixtures (fixtures/analysisLayoutApi.ts).
    name: 'analysis',
    path: '/analysis?ticker=META',
    open: async (p, b) => {
      await answerAnalysisApi(p, b)
    },
    ready: (p) => runAnalysis(p, 'quarterly'),
  },
]

/**
 * The rest of the public pages (BG-29), each answered by answerSiteApi (no backend). With ROUTES, this list
 * covers every route the sitemap's static core names (STATIC_ENTRIES in app/sitemap.ts, which mirrors the
 * backend's STATIC_PAGES) and every AuthShell route (AUTH_ROUTES in lib/authShellRoutes.ts: /login,
 * /register, /check-email, /verify-email, /forgot-password and /reset-password), and the census cases below
 * hold it to both; beyond them it adds /waitlist, /delete-account (the public account-deletion page), /calendar
 * and /search. CI's e2e build turns the last two on: the calendar reads its own fixtures with the clock pinned to
 * one week (fixtures/calendarWeek.ts), and the search is answered here and run (fixtures/searchApi.ts), so each is
 * read with its rows painted. A third census case reads every page.tsx under app/, static or dynamic, and fails on one
 * that no entry visits (a dynamic route by a representative path) unless NOT_VISITED names it with its reason,
 * so a new public page cannot stay outside the gate in silence. Kept apart from ROUTES so the cases below that pick a route by its index keep theirs.
 * /waitlist's example falls back to its h2 card here; waitlistPage.spec.tsx reads the outline with the
 * example loaded.
 */
const PUBLIC_ROUTES: Route[] = [
  { name: 'waitlist', path: '/waitlist', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByLabel('Email address')).toBeVisible() },
  { name: 'login', path: '/login', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() },
  { name: 'register', path: '/register', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() },
  { name: 'check email', path: '/check-email', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Check your inbox' })).toBeVisible() },
  // Opened without the emailed token: /verify-email settles on its failure state, /reset-password shows its invalid-link notice.
  { name: 'verify email (no token)', path: '/verify-email', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Verification failed' })).toBeVisible() },
  { name: 'forgot password', path: '/forgot-password', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() },
  { name: 'reset password (no token)', path: '/reset-password', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Choose a new password' })).toBeVisible() },
  { name: 'contact', path: '/contact', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1 })).toBeVisible() },
  { name: 'privacy', path: '/privacy', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeVisible() },
  { name: 'terms', path: '/terms', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Terms of Service' })).toBeVisible() },
  { name: 'security', path: '/security', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Security' })).toBeVisible() },
  { name: 'delete account', path: '/delete-account', open: (p, b) => answerSiteApi(p, b, false), ready: (p) => expect(p.getByRole('heading', { level: 1, name: 'Delete your account' })).toBeVisible() },
  {
    name: 'calendar',
    path: '/calendar',
    open: async (p, b) => {
      await pinCalendarWeek(p)
      await answerSiteApi(p, b, false)
    },
    ready: calendarWeekReady,
  },
  {
    name: 'search',
    path: '/search',
    open: async (p, b) => {
      await answerSiteApi(p, b, false)
      await answerSearch(p, b)
    },
    ready: runSearch,
  },
]


/**
 * The pages under app/ that no entry visits, by route pattern, each with its reason. A pattern listed here that
 * the census does visit, or that no longer exists, fails the census case too, so a reason cannot outlive its page.
 */
const NOT_VISITED: Record<string, string> = {
  '/admin/feedback': 'admin only, no admin session in this e2e; admin-feedback-page.spec.tsx pins its outline',
  '/admin/invites': 'admin only, no admin session in this e2e; admin-invites-page.spec.tsx pins its outline',
  '/dashboard/settings': 'signed-in settings; its surface is brand-settings-subscriptions (#1291), which adds its entry',
  '/labs/filing-redlines': 'a labs prototype outside the brand series (tasks/todo.md E26)',
  '/labs/financial-refresh-review': 'a labs prototype outside the brand series (tasks/todo.md E26)',
  '/labs/research-evidence-packs': 'a labs prototype outside the brand series (tasks/todo.md E26)',
}

/**
 * Every route under app/ (a page.tsx) as its pattern: a dynamic segment stays as written (`/company/[ticker]`,
 * `/filing/[id]`), and a route group's parentheses add no segment.
 */
function appRoutePatterns(): string[] {
  const root = path.resolve(__dirname, '../../app')
  const routes: string[] = []
  const walk = (dir: string, segments: string[]) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        walk(path.join(dir, entry.name), /^\(.*\)$/.test(entry.name) ? segments : [...segments, entry.name])
      } else if (entry.name === 'page.tsx') routes.push('/' + segments.join('/'))
    }
  }
  walk(root, [])
  return routes.sort()
}

/**
 * Whether a visited path is an instance of a route pattern: segment by segment, a literal segment must match,
 * a dynamic one (`[id]`) takes any one segment, a catch-all (`[...rest]`) the rest, an optional catch-all
 * (`[[...rest]]`) the rest or nothing. A query string is not a segment (/analysis?ticker=META visits /analysis).
 */
function isInstance(pattern: string, visitedPath: string): boolean {
  const want = pattern.split('/').filter(Boolean)
  const have = visitedPath.split('?')[0].split('/').filter(Boolean)
  for (let i = 0; i < want.length; i += 1) {
    const segment = want[i]
    if (segment.startsWith('[[...')) return true
    if (segment.startsWith('[...')) return have.length > i
    if (have[i] === undefined) return false
    if (!segment.startsWith('[') && segment !== have[i]) return false
  }
  return have.length === want.length
}

async function visit(page: Page, baseURL: string, route: Route, theme: 'light' | 'dark' = 'light') {
  await page.addInitScript((theme) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await route.open(page, baseURL)
  const response = await page.goto(route.path)
  if (route.status) expect(response?.status()).toBe(route.status)
  await route.ready(page)
  // The auth pages render in AuthShell, which has no site footer: the shell's own route list says which.
  if (!isAuthRoute(route.path)) await expect(page.getByRole('contentinfo')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

/** Every visible text element painted in `ink`, with its WCAG contrast over the composited ground. */
const inkCensus = (page: Page, ink: string, foldOpacity = false) =>
  page.evaluate(({ ink, foldOpacity }) => {
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
      // An ancestor's opacity fades the text into what is behind it (an approximation that ignores any
      // ground inside the faded group, which the progress card's step rows do not have).
      let fade = 1
      if (foldOpacity) for (let n: Element | null = el; n; n = n.parentElement) fade *= Number(getComputedStyle(n).opacity)
      const textInk = parse(s.color)
      const [hi, lo] = [lum(over({ ...textInk, a: textInk.a * fade }, ground)), lum(ground)].sort((x, y) => y - x)
      found.push({ text: text.slice(0, 48), ratio: Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100 })
    }
    return found
  }, { ink, foldOpacity })

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

  for (const route of [...ROUTES, ...PUBLIC_ROUTES]) {
    test(`${route.name}: muted ink clears AA and the heading outline skips no level`, async ({ page, baseURL }) => {
      await visit(page, baseURL!, route)
      await page.mouse.move(0, 0)

      const census = await inkCensus(page, TERTIARY_INK, route.foldOpacity)
      // Anti-vacuity: the homepage keeps tertiary labels inside its sample cards (on panel and white), and
      // the in-flight card its pending step labels.
      if (route.name === 'home') expect(census.length, `tertiary text found on ${route.name}`).toBeGreaterThan(10)
      // The census keeps a text's first 48 characters (inkCensus), so the step is matched on as much.
      if (route.foldOpacity) expect(census.map((c) => c.text), `pending steps measured on ${route.name}`).toContain(PENDING_STEP.slice(0, 48))
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
      if (isAuthRoute(route.path) || route.name === 'route error boundary') {
        // DS-04: AuthShell's form pane and the page-replacing boundary own the landmark, under
        // the root's div#main skip target. A universal main in the root would fail this count.
        await expect(page.getByRole('main')).toHaveCount(1)
        await expect(page.getByRole('main').getByRole('heading', { level: 1 })).toHaveCount(1)
        await expect(page.getByRole('main')).toBeVisible()
      }
      if (!isAuthRoute(route.path)) expect.soft(outline.footer.join(' '), 'the footer opens its own h2 before its h3 column titles').toMatch(/^H2( H3)+$/)
    })
  }

  // The declared scope: a route added to the sitemap's static core fails this case until the census visits it.
  test('the census visits every route in the sitemap static core', () => {
    const visited = [...ROUTES, ...PUBLIC_ROUTES].map((route) => route.path)
    for (const { url } of STATIC_ENTRIES) {
      const path = new URL(url).pathname
      expect.soft(visited, `${path} is in STATIC_ENTRIES (app/sitemap.ts) but no ROUTES or PUBLIC_ROUTES entry visits it`).toContain(path)
    }
  })

  // Likewise for the auth pages: a route added to the AuthShell list fails this case until the census visits it.
  test('the census visits every route in the auth list', () => {
    const visited = [...ROUTES, ...PUBLIC_ROUTES].map((route) => route.path)
    for (const path of AUTH_ROUTES) {
      expect.soft(visited, `${path} is in AUTH_ROUTES (lib/authShellRoutes.ts) but no ROUTES or PUBLIC_ROUTES entry visits it`).toContain(path)
    }
  })

  // And the whole app: every page.tsx under app/, static or dynamic, has a visited path that is an instance of
  // its route pattern (ROUTES, PUBLIC_ROUTES or a card state; /company/AAPL for /company/[ticker], /filing/3 for
  // /filing/[id]), or NOT_VISITED names the pattern with its reason; a reason for a pattern that is visited or
  // gone fails too. Codex's reviews of 80bb520e, 79336f81, 26478baa and 62d3fbe0 each found a route the lists
  // above had missed or could miss; this case reads the inventory itself instead of a list retyped from it.
  test('the census visits every page under app/, static or dynamic, or names why not', () => {
    const visited = [...ROUTES, ...PUBLIC_ROUTES, ...CARD_STATES.map((state) => state.route)].map((route) => route.path)
    const patterns = appRoutePatterns()
    expect(patterns.length, 'the app directory walk reads the pages').toBeGreaterThan(20)
    expect(patterns, 'the walk keeps a dynamic segment as written').toContain('/company/[ticker]')
    const covered = (pattern: string) => visited.some((visitedPath) => isInstance(pattern, visitedPath))
    for (const pattern of patterns) {
      if (covered(pattern)) continue
      expect.soft(NOT_VISITED[pattern], `${pattern} has a page.tsx but no ROUTES, PUBLIC_ROUTES or card-state path is an instance of it, and NOT_VISITED gives no reason`).toBeTruthy()
    }
    for (const pattern of Object.keys(NOT_VISITED)) {
      expect.soft(patterns, `${pattern} is in NOT_VISITED but has no page.tsx: delete its reason`).toContain(pattern)
      expect.soft(covered(pattern), `${pattern} is in NOT_VISITED and the census visits it: delete its reason`).toBe(false)
    }
    // Anti-vacuity for the matcher: a literal mismatch, a dynamic segment, a catch-all and an optional catch-all.
    expect(isInstance('/company/[ticker]', '/company/AAPL')).toBe(true)
    expect(isInstance('/company/[ticker]', '/filing/3')).toBe(false)
    expect(isInstance('/company/[ticker]', '/company')).toBe(false)
    expect(isInstance('/analysis', '/analysis?ticker=META')).toBe(true)
    expect(isInstance('/analysis', '/analysis/META')).toBe(false)
    expect(isInstance('/docs/[...slug]', '/docs/a/b')).toBe(true)
    expect(isInstance('/docs/[...slug]', '/docs')).toBe(false)
    expect(isInstance('/docs/[[...slug]]', '/docs')).toBe(true)
  })
})

/**
 * The census in dark (E202 (1)): muted ink there is tertiary's dark twin (gray-400, read from tailwind.config.js),
 * measured as the light census measures its ink, against what is behind each text, tints included, on the same routes
 * at the same width, the company page's hovered year header too. The heading outline and the census's route lists do
 * not change with the theme, so the light describe holds them alone.
 */
test.describe('main routes at 1440x900, dark theme', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const route of [...ROUTES, ...PUBLIC_ROUTES]) {
    test(`${route.name}: muted ink clears AA in dark`, async ({ page, baseURL }) => {
      await visit(page, baseURL!, route, 'dark')
      expect(await page.evaluate(() => document.documentElement.classList.contains('dark')), 'the dark theme took').toBe(true)
      await page.mouse.move(0, 0)

      const census = await inkCensus(page, TERTIARY_INK_DARK, route.foldOpacity)
      // Anti-vacuity, as in light: the homepage's sample cards and the in-flight card's pending steps.
      if (route.name === 'home') expect(census.length, `tertiary text found on ${route.name} in dark`).toBeGreaterThan(10)
      if (route.foldOpacity) expect(census.map((c) => c.text), `pending steps measured on ${route.name} in dark`).toContain(PENDING_STEP.slice(0, 48))
      expect.soft(census.filter((c) => c.ratio < 4.5), `tertiary text under 4.5:1 on ${route.name} in dark`).toEqual([])

      if (route.name === 'company') {
        const header = page.getByRole('button', { name: /^Report year 2025\b/ })
        await header.hover()
        await settled(header)
        expect.soft((await inkCensus(page, TERTIARY_INK_DARK)).filter((c) => c.ratio < 4.5), 'tertiary text under 4.5:1 with a year header hovered, in dark').toEqual([])
      }
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
    // No backend answers /api/auth/registration here, so the gate fails closed to its invite-only copy. The
    // header carries the same 'Request an invite' CTA in invite mode, so the gate's link is read inside #main.
    route: { ...ROUTES[3], open: (p, b) => noSummary(p, b, 'anon'), ready: (p) => expect(p.locator('#main').getByRole('link', { name: 'Request an invite' })).toBeVisible() },
    card: 'Summaries need an account',
  },
  {
    name: 'filing without a summary, signed in, the run fails',
    route: { ...ROUTES[3], open: (p, b) => noSummary(p, b, 'pro'), ready: (p) => expect(p.getByRole('button', { name: 'Try again', exact: true })).toBeVisible() },
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
      ready: (p) => expect(p.getByRole('button', { name: 'Try again', exact: true })).toBeVisible(),
    },
    card: 'This summary did not finish',
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

test.describe('the waitlist join link at 1440x900, both themes', () => {
  test.use({ viewport: { width: 1440, height: 900 } })
  const waitlist = PUBLIC_ROUTES.find((r) => r.path === '/waitlist')!

  for (const theme of ['light', 'dark'] as const) {
    test(`${theme}: the join link answers the pointer, and its label clears 4.5:1 at rest and hovered`, async ({ page, baseURL }) => {
      await visit(page, baseURL!, waitlist, theme)
      expect(await page.evaluate(() => document.documentElement.classList.contains('dark')), `the ${theme} theme took`).toBe(theme === 'dark')
      const link = page.getByRole('link', { name: 'Join the waitlist' })
      const look = () =>
        link.evaluate((el) => ({ hovered: el.matches(':hover'), ink: getComputedStyle(el).color, fill: getComputedStyle(el).backgroundColor }))

      await page.mouse.move(0, 0)
      await settled(link)
      const rest = await look()
      expect(rest.hovered, 'the pointer is off the link at rest').toBe(false)
      expect(rest.ink, 'the label is the secondary recipe ink').toBe(BRAND_INK[theme])
      expect(await textContrast(link, { exact: true }), `the ${theme} label at rest`).toBeGreaterThanOrEqual(4.5)

      await link.hover()
      await settled(link)
      const hovered = await look()
      expect(hovered.hovered, 'the pointer is on the link').toBe(true)
      expect(hovered.fill, 'the fill changes under the pointer').not.toBe(rest.fill)
      expect(hovered.ink, 'the label keeps the recipe ink').toBe(BRAND_INK[theme])
      expect(await textContrast(link, { exact: true }), `the ${theme} label hovered`).toBeGreaterThanOrEqual(4.5)
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

/**
 * The tone badge beside a section heading ("Management tone: cautious", filing/F20; the founder's
 * design review of #1293): the index and the heading are one group that never wraps, and the row wraps
 * only the badge, so where the badge does not fit beside its heading it moves beneath it instead of
 * squeezing the heading, its label wraps inside it rather than push the page wider, and a long heading
 * wraps its own words beside its index instead of dropping beneath it (the principal review of #1293).
 * Measured on the painted boxes at 320px with the default text size and at 390x844 with Chromium's text
 * doubled (standard 32px). Geometry only, so the light theme stands for both. The fixture's sections
 * carry no tone, so this case gives the first two one, and the second the schema's longest title
 * (summary_schema.py's "Earnings Quality & Cash Conversion"), which no 320px row holds on one line.
 */
const TONED_SUMMARY = {
  ...SUMMARY,
  rendered_sections: (SUMMARY.rendered_sections as Array<Record<string, unknown>>).map((section, i) =>
    i === 0 ? { ...section, tone: 'cautious' } : i === 1 ? { ...section, title: 'Earnings Quality & Cash Conversion', tone: 'positive' } : section,
  ),
}
const TONED_FILING: Route = {
  name: 'filing with toned sections',
  path: '/filing/3',
  open: async (p, b) => {
    await answerApi(p, b, 'anon')
    await p.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3', (r) =>
      r.fulfill({ status: 200, headers: corsFor(b), json: TONED_SUMMARY }),
    )
  },
  ready: (p) => expect(p.getByText('Management tone: cautious', { exact: true })).toBeVisible(),
}

/** Each summary section's heading row (the section's first child, holding its "01" index): whether the
    heading sits beside its index, and for a toned row whether its badge's box meets the heading's, sits
    wholly beneath it, and how far either reaches past the row or the viewport. Read from the section, so
    any arrangement of the row's items is measured, not only the one the page ships. */
const headingRows = (page: Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll('section h2')].flatMap((heading) => {
      const row = heading.closest('section')?.firstElementChild
      const index = row?.querySelector('span[aria-hidden="true"]')
      if (!row || !index || !row.contains(heading) || !/^\d{2}$/.test((index.textContent ?? '').trim())) return []
      const h = heading.getBoundingClientRect()
      const i = index.getBoundingClientRect()
      const badge = [...row.children].find((child) => (child.textContent ?? '').startsWith('Management tone: '))
      const b = badge?.getBoundingClientRect()
      const rowRight = row.getBoundingClientRect().right
      const viewport = document.documentElement.clientWidth
      return [{
        heading: (heading.textContent ?? '').trim(),
        // Beside its index: the heading starts right of the index and its first line is the index's line.
        besideIndex: h.left >= i.right - 0.5 && h.top < i.bottom,
        toned: !!b,
        meets: !!b && h.left < b.right && b.left < h.right && h.top < b.bottom && b.top < h.bottom,
        beneath: !!b && b.top >= h.bottom - 1,
        pastRow: Math.max(0, Math.round(Math.max(h.right, b?.right ?? 0) - rowRight)),
        pastViewport: Math.max(0, Math.round(Math.max(h.right, b?.right ?? 0, rowRight) - viewport)),
      }]
    }),
  )

test('the tone badge moves beneath its heading at 320px, and the page stays 320px wide', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 320, height: 720 })
  await visit(page, baseURL!, TONED_FILING)
  const rows = await headingRows(page)
  expect(rows.filter((r) => r.toned).map((r) => r.heading), 'both toned sections were measured').toEqual(['The Print', 'Earnings Quality & Cash Conversion'])
  expect(rows.filter((r) => !r.besideIndex).map((r) => r.heading), 'a heading dropped beneath its index').toEqual([])
  expect(
    rows.filter((r) => r.toned && (r.meets || !r.beneath || r.pastRow > 0 || r.pastViewport > 0)),
    'a badge meets its heading, stays beside it, runs past its row, or its row runs past the viewport',
  ).toEqual([])
  // The founder's ask at 320px with the default text size: no sideways scroll.
  const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }))
  expect(width.scroll, `the document is ${width.scroll}px wide against a ${width.client}px viewport`).toBeLessThanOrEqual(width.client)
})

// The page's own width at 200% is reflow-200.spec.ts's gate (#1278): on main the site header's phone
// cluster and the "Ask this filing" Button still run past 390px at that size, which no filing-page
// change can bring in. This case holds what the heading row controls: its heading, its badge and its row.
test('the tone badge stays inside its row and the viewport at 390px and 200% text', async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await visit(page, baseURL!, TONED_FILING)
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took' })
    .toBe('32px')
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  const rows = await headingRows(page)
  expect(rows.filter((r) => r.toned).map((r) => r.heading), 'both toned sections were measured').toEqual(['The Print', 'Earnings Quality & Cash Conversion'])
  expect(rows.filter((r) => !r.besideIndex).map((r) => r.heading), 'a heading dropped beneath its index').toEqual([])
  expect(
    rows.filter((r) => r.toned && (r.meets || !r.beneath || r.pastRow > 0 || r.pastViewport > 0)),
    'a badge meets its heading, stays beside it, runs past its row, or its row runs past the viewport',
  ).toEqual([])
})
