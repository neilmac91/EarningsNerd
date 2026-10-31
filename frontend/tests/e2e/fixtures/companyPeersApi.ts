import { readFileSync } from 'node:fs'
import path from 'node:path'
import type { Page } from '@playwright/test'
import type { PeerComparisonResponse } from '../../../features/peers/api/peers-api'
import { API_ORIGIN } from './filing3Api'
import { legalReady } from './legalReady'

/**
 * The company page answered in the browser for the Sector peers panel's cases (E251): CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md), so the page's company, its filings and its peers are answered here. The
 * peers come from tests/unit/fixtures/peers-cohorts.json, which backend/tests/unit/test_peers_fixture_contract.py holds
 * to the service, so the page is answered with what the endpoint would serve. Every other path answers 404, as
 * text-floors.spec.ts's answers do.
 */

export type Theme = 'light' | 'dark'

/** One fixture case: the metric its request named and the answer. */
export interface PeerCase {
  case: string
  metric: string
  response: PeerComparisonResponse & { sic: string | null }
}

export const PEERS = JSON.parse(readFileSync(path.join(__dirname, '../../unit/fixtures/peers-cohorts.json'), 'utf8')) as {
  source: string
  cases: Record<string, PeerCase>
}

const SOURCE = /^https:\/\/www\.sec\.gov\/Archives\/edgar\/data\/(\d+)\//

/** A case's subject as the company read answers it: production's CIK where its entry links its filing, else one of
 *  the synthetic companies' own. */
export function companyOf(response: PeerComparisonResponse) {
  const cik = SOURCE.exec(response.subject.provenance?.source_url ?? '')?.[1] ?? '9999001'
  return { id: 1, cik, ticker: response.ticker, name: response.company_name, exchange: 'NASDAQ' }
}

/** The company's filings: an annual report and the quarter after it. */
export function filingsOf(response: PeerComparisonResponse) {
  const { cik } = companyOf(response)
  const filing = (id: number, filing_type: string, filing_date: string, report_date: string) => {
    const folder = `https://www.sec.gov/Archives/edgar/data/${cik}/0000${cik.padStart(6, '0').slice(-6)}2600000${id}/`
    return {
      id, filing_type, filing_date: `${filing_date}T00:00:00+00:00`, report_date, accession_number: `0000${cik}-26-00000${id}`,
      document_url: `${folder}doc-${id}.htm`, sec_url: folder,
    }
  }
  return [filing(2, '10-Q', '2026-04-30', '2026-03-31'), filing(1, '10-K', '2026-02-20', '2025-12-31')]
}

/** An answer moved onto another company, for a page that is not the case's subject's own (text-floors.spec.ts's Apple
 *  page): the subject's entry takes the company's ticker and name, and its values and order stay the fixture's. */
export function asCompany(response: PeerComparisonResponse, ticker: string, name: string): PeerComparisonResponse {
  const move = (entry: PeerComparisonResponse['subject']) => (entry.is_subject ? { ...entry, ticker, company_name: name } : entry)
  return { ...response, ticker, company_name: name, subject: move(response.subject), peers: response.peers.map(move) }
}

/** Answers the company page of a case's subject: its company, its filings, the legal readiness the shell reads, a
 *  guest's session, and its peers by the metric each request names (the case's own metric its answer, and `more` for
 *  the others); every other path 404. */
export async function answerCompany(page: Page, baseURL: string, name: string, more: Record<string, PeerComparisonResponse> = {}) {
  const { metric, response } = PEERS.cases[name]
  const peers: Record<string, PeerComparisonResponse> = { ...more, [metric]: response }
  const ticker = response.ticker
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const url = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (url.pathname) {
      case '/api/legal/readiness':
        return json(200, legalReady)
      case `/api/companies/${ticker}`:
        return json(200, companyOf(response))
      case `/api/filings/company/${ticker}`:
        return json(200, filingsOf(response))
      case `/api/companies/${ticker}/peers`: {
        const answer = peers[url.searchParams.get('metric') ?? 'revenue']
        return answer ? json(200, answer) : json(404, { detail: 'Not found' })
      }
      case '/api/auth/me':
        return json(401, { detail: 'Not authenticated' })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
  return response
}

/** Consent answered and the first-run coachmark seen (neither belongs to the panel), the theme chosen, then the page of
 *  a case's subject. Given `doubled`, the page opens under 200% text (Chromium's own text setting, as reflow-200.spec.ts
 *  doubles it). */
export async function openCompany(page: Page, baseURL: string, name: string, theme: Theme, { more, doubled = false }: { more?: Record<string, PeerComparisonResponse>; doubled?: boolean } = {}) {
  const response = await answerCompany(page, baseURL, name, more)
  if (doubled) await (await page.context().newCDPSession(page)).send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await page.addInitScript((chosen: Theme) => {
    try {
      localStorage.setItem('theme', chosen)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto(`/company/${response.ticker}`)
  return response
}
