import type { Page } from '@playwright/test'
import type { CurrentUser } from '../../../features/auth/api/auth-api'
import type { InsiderActivityResponse, InsiderTransaction } from '../../../features/insiders/api/insiders-api'
import { API_ORIGIN } from './filing3Api'
import { legalReady } from './legalReady'
import type { Theme } from './companyPeersApi'

/**
 * The company page answered in the browser for the Insider activity panel (ADR 0009): CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md), so the page's company, its filings, its reader and its insider trades
 * are answered here. The reader is a beta account unless `reader` says otherwise (null: a guest, /me answers 401);
 * the insiders endpoint answers a guest 401 and any other account 403, as the backend does. Every other path 404.
 */

export const TICKER = 'INSX'
const COMPANY = { id: 1, cik: '9999101', ticker: TICKER, name: 'Insider Example Corp', exchange: 'NASDAQ' }
const FOLDER = 'https://www.sec.gov/Archives/edgar/data/9999101/000999910126000001/'
const FILINGS = [{
  id: 1, filing_type: '10-K', filing_date: '2026-02-20T00:00:00+00:00', report_date: '2025-12-31',
  accession_number: '0009999101-26-000001', document_url: `${FOLDER}doc-1.htm`, sec_url: FOLDER,
}]

export const BETA_READER: CurrentUser = {
  id: 7, email: 'reader@example.test', full_name: 'Beta Reader', is_pro: false, is_beta: true, is_admin: false, email_verified: true,
}

const trade = (over: Partial<InsiderTransaction>): InsiderTransaction => ({
  insider_name: 'Jane Doe', insider_title: 'Chief Financial Officer', is_director: false, is_officer: true,
  is_ten_pct_owner: false, ticker: TICKER, transaction_date: '2026-10-01', transaction_code: 'P', transaction_label: 'Purchase',
  shares: 12000, price: 150.25, value: 1803000, acquired_disposed: 'A', is_10b5_1: false,
  accession: '0009999101-26-000011', filed_date: '2026-10-03', ...over,
})

/** A scan part-way through, with trades stored: what a reader sees about half a minute into a company's first visit. */
export const SCANNING: InsiderActivityResponse = {
  ticker: TICKER, company_name: COMPANY.name, cik: COMPANY.cik, window_days: 90,
  summary: {
    window_days: 90, buy_count: 1, sell_count: 2, buy_shares: 12000, sell_shares: 9500, buy_value: 1803000, sell_value: 1461500,
    net_shares: 2500, net_value: 341500, discretionary_net_shares: 8500, plan_10b5_1_sell_shares: 6000,
    last_transaction_date: '2026-10-01',
  },
  transactions: [
    trade({}),
    trade({ insider_name: 'John Roe', insider_title: 'Director', is_officer: false, is_director: true, transaction_date: '2026-09-18',
            transaction_code: 'S', transaction_label: 'Sale', shares: 6000, price: 154.0, value: 924000, acquired_disposed: 'D', is_10b5_1: true,
            filed_date: '2026-09-21' }),
    trade({ insider_name: 'Alexandria Montgomery-Fitzgerald', insider_title: 'Executive Vice President, Worldwide Operations',
            transaction_date: '2026-09-02', transaction_code: 'S', transaction_label: 'Sale', shares: 3500, price: 153.57, value: 537500,
            acquired_disposed: 'D', filed_date: '2026-09-04' }),
  ],
  total_transactions: 3,
  scan: { status: 'scanning', filings_listed: 60, filings_read: 16, oldest_filed_date: '2026-09-04', refreshed_at: '2026-11-14T12:00:00Z', retry_after_seconds: 8 },
}

/** Answers the page of TICKER for `reader`, its insider trades with `insiders`; counts the insider requests made. */
export async function answerInsiders(page: Page, baseURL: string, insiders: InsiderActivityResponse, reader: CurrentUser | null = BETA_READER) {
  const asked = { insiders: 0 }
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, async (route) => {
    const url = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (url.pathname) {
      case '/api/legal/readiness':
        return json(200, legalReady)
      case `/api/companies/${TICKER}`:
        return json(200, COMPANY)
      case `/api/filings/company/${TICKER}`:
        return json(200, FILINGS)
      case '/api/auth/me':
        return reader ? json(200, reader) : json(401, { detail: 'Not authenticated' })
      case `/api/companies/${TICKER}/insiders`:
        asked.insiders += 1
        if (!reader) return json(401, { detail: 'Not authenticated' })
        return reader.is_beta ? json(200, insiders) : json(403, { detail: 'This is available to beta testers.' })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
  return asked
}

/** Consent answered and the first-run coachmark seen (neither belongs to the panel), the theme chosen, then the page.
 *  Given `doubled`, the page opens under 200% text (Chromium's own text setting, as reflow-200.spec.ts doubles it). */
export async function openInsiders(page: Page, baseURL: string, theme: Theme, { insiders = SCANNING, reader = BETA_READER as CurrentUser | null, doubled = false } = {}) {
  const asked = await answerInsiders(page, baseURL, insiders, reader)
  if (doubled) await (await page.context().newCDPSession(page)).send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await page.addInitScript((chosen: Theme) => {
    try {
      localStorage.setItem('theme', chosen)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto(`/company/${TICKER}`)
  return asked
}
