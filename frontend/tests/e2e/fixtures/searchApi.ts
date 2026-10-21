import { expect, type Page } from '@playwright/test'
import type { FullTextSearchHit, FullTextSearchResponse } from '../../../features/search/api/search-api'
import { API_ORIGIN, DOCUMENT, FOLDER } from './filing3Api'

/**
 * /search in CI's e2e build (NEXT_PUBLIC_ENABLE_FULLTEXT_SEARCH), answered in the browser: the job runs no backend
 * (lessons/test-e2e-runs-without-backend.md). Three hits, one of each row kind the list draws: a filing with a ticker
 * and a document link (filing 3's 10-K), a long filer name with no ticker, and a hit with neither a name nor a link,
 * which renders as a plain row. Shared by text-floors.spec.ts and reflow-200.spec.ts.
 */
export const SEARCH_QUERY = 'going concern'
const EXAMPLE = 'https://www.sec.gov/Archives/edgar/data/1000001/000100000125000017/'
export const SEARCH_HITS: FullTextSearchHit[] = [
  { accession_no: '0000320193-25-000079', form: '10-K', filed_date: '2025-10-31', period_ending: '2025-09-27', cik: '320193', company: 'Apple Inc.', ticker: 'AAPL', document: 'aapl-20250927.htm', sec_url: FOLDER, document_url: DOCUMENT },
  { accession_no: '0001000001-25-000017', form: '8-K', filed_date: '2025-08-14', period_ending: null, cik: '1000001', company: 'Example Infrastructure Holdings and Utilities Partners Limited Partnership', ticker: null, document: 'ex99-1.htm', sec_url: EXAMPLE, document_url: `${EXAMPLE}ex99-1.htm` },
  { accession_no: '0001000002-25-000004', form: '10-Q', filed_date: '2025-05-02', period_ending: '2025-03-31', cik: '1000002', company: null, ticker: null, document: null, sec_url: null, document_url: null },
]
const RESPONSE: FullTextSearchResponse = { query: SEARCH_QUERY, total: 1284, count: SEARCH_HITS.length, hits: SEARCH_HITS }

export async function answerSearch(page: Page, baseURL: string) {
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/search/full-text', (route) =>
    route.fulfill({ status: 200, headers: cors, json: RESPONSE }),
  )
}

/** Types the query, then waits for what only an answered search shows: the count line, from the response's numbers. */
export async function runSearch(page: Page) {
  await page.getByRole('textbox', { name: 'Search the full text of SEC filings' }).fill(SEARCH_QUERY)
  await expect(page.getByText(`1,284 filings match · showing ${SEARCH_HITS.length}`, { exact: true })).toBeVisible()
}
