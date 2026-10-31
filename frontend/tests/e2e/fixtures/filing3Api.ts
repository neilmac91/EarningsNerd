import { readFileSync } from 'node:fs'
import path from 'node:path'
import type { Page } from '@playwright/test'

/**
 * The filing page's API, answered inside the browser: CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md), so every request to the API origin is fulfilled from
 * these fixtures — the public Apple FY2025 10-K as filing 3, its summary a trimmed copy in
 * filing-3-summary.json, its Financial trends series a trimmed copy in filing-3-fundamentals.json,
 * and the session / subscription endpoints for an anonymous visitor or a Pro
 * user. Shared by every e2e spec that imports it (from the repository root,
 * `git grep -l "fixtures/filing3Api'" frontend/tests/e2e` lists them: the filing page's chips, links,
 * panes and Ask stream, the layout and contrast gates reflow-200.spec.ts and text-floors.spec.ts, and
 * filing-fundamentals-chart.spec.ts among them);
 * a spec seeds its own browser state (theme, consent, coachmark) in its own addInitScript.
 */
export const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
export const SUMMARY = JSON.parse(readFileSync(path.join(__dirname, 'filing-3-summary.json'), 'utf8')) as Record<string, unknown>
/** GET /api/filings/3/fundamentals as production served it on 2026-10-29 (body sha256 4e867249…, 25 series), with
 *  four series kept whole, copied by a script rather than retyped
 *  (lessons/test-verbatim-fixtures-keep-the-source-bytes.md): revenue, the card's default metric, reported, each point
 *  linking its SEC folder; net margin, a percent; the current ratio, a multiple; and working capital, negative in both
 *  years. The last three are calculated and need a source check, so the card shows its badge on them and Sources &
 *  checks gives their reasons. CI's e2e build turns the card on, as production's does
 *  (NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS), so a spec that opens /filing/3 on its stored summary from here meets it drawn;
 *  one that withholds the summary, or opens another page, does not. */
export const FUNDAMENTALS = JSON.parse(readFileSync(path.join(__dirname, 'filing-3-fundamentals.json'), 'utf8')) as {
  ticker: string
  company_name: string
  concepts: { concept: string; unit: string; points: { fiscal_year: number; value: number }[] }[]
}

export const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
export const DOCUMENT = `${FOLDER}aapl-20250927.htm`
export const FILING = {
  id: 3,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  accession_number: '0000320193-25-000079',
  document_url: DOCUMENT,
  sec_url: FOLDER,
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
}
/** The takeaway chip's verified excerpt (filing-3-summary.json, Total net sales). */
export const EXCERPT = 'Americas net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services.'
/** The research pane (2026-10 critique P-06): a dialog below lg, an aside (complementary) on lg+, named
    "Source" by its header. */
export const PANE = '[aria-labelledby="source-pane-title"]'
/** The synthetic filing text with wide statement tables (see the fixture's header comment); its
 * header comment is stripped, because react-markdown renders an HTML comment as literal text. */
export const TABLES_TEXT = readFileSync(path.join(__dirname, 'filing-3-content.md'), 'utf8').replace(/^<!--[\s\S]*?-->\n\n/, '')

export type Who = 'anon' | 'pro'
export type Content = 'none' | 'matched' | 'unmatched' | 'error' | 'tables'
export type Theme = 'light' | 'dark'

/** Routes every request to the API origin to a fixture; a Pro `who` also carries the session cookie. */
export async function answerApi(page: Page, baseURL: string, who: Who = 'anon', content: Content = 'none') {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  if (who === 'pro') await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (pathname) {
      case '/api/filings/3':
        return json(200, FILING)
      case '/api/summaries/filing/3':
        return json(200, SUMMARY)
      case '/api/filings/3/fundamentals':
        return json(200, FUNDAMENTALS)
      case '/api/filings/3/content':
        if (content === 'error') return json(500, { detail: 'content unavailable' })
        if (content === 'none') return json(200, { filing_id: 3, has_content: false, markdown_content: null })
        return json(200, {
          filing_id: 3,
          has_content: true,
          markdown_content:
            content === 'tables'
              ? TABLES_TEXT
              : content === 'matched'
                ? `# Item 8. Financial Statements\n\nNet sales by reportable segment. ${EXCERPT} Europe net sales also increased.\n`
                : '# Item 8. Financial Statements\n\nNothing cited in the summary appears in this text.\n',
        })
      case '/api/auth/me':
        return who === 'anon'
          ? json(401, { detail: 'Not authenticated' })
          : json(200, { id: 1, email: 'pro@example.com', full_name: 'Pro User', is_pro: true, is_beta: false, is_admin: false, email_verified: true })
      case '/api/feedback/capabilities':
        // These shared cases use the healthy text-only composer, not a capabilities failure.
        return json(200, {
          attachments_enabled: false,
          max_files: 3,
          max_file_bytes: 5 * 1024 * 1024,
          max_total_bytes: 16 * 1024 * 1024,
          accepted_content_types: ['image/png', 'image/jpeg', 'image/webp'],
        })
      case '/api/subscriptions/subscription':
        return json(200, { is_pro: true, stripe_customer_id: 'cus_1', stripe_subscription_id: 'sub_1', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: 0, summaries_limit: 100, is_pro: true, month: '2026-10', qa_used: 0, qa_limit: 300, copilot_free_taste_used: 0, copilot_free_taste_total: 0, analysis_used: 0, analysis_limit: 50 })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}
