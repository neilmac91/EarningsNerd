import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, SUMMARY, answerApi, type Theme } from './fixtures/filing3Api'

/**
 * Risk evidence rows on the filing page (2026-10 critique P-03, founder option b): what only a real
 * layout shows, in Chromium at 390 and 1440 in both themes. Which heading a row gets and that its
 * blockquote holds the whole span are pinned once, in jsdom (riskHeadline.spec.ts, riskTitle.spec.ts,
 * SummaryRisks.spec.tsx; one test per rule, AGENTS.md §4). Here:
 *
 *   - each row's h3 and blockquote text sits inside the row and the viewport, and the page does not
 *     scroll sideways, a long unbreakable token (a URL) included at 390;
 *   - the blockquote computes to 14px.
 *
 * The four risks are the production filing-3 spans (fixtures/filing-3-risks.json, copied verbatim
 * from raw_summary.sections.risks of the critique harness's cached GET /api/summaries/filing/3,
 * body sha256 1412895e…, fetched 2026-10-04), served into the shared summary fixture, whose own
 * risks list is empty. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the
 * API is answered inside the browser with page.route. DOM and computed-style probes only: this is
 * not a screen-reader test.
 */

type Risk = { supporting_evidence: string } & Record<string, unknown>
const RISKS = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-risks.json'), 'utf8')) as Risk[]
const SECTION = '#risks'

async function openRisks(page: Page, baseURL: string, theme: Theme, risks: Risk[] = RISKS) {
  await answerApi(page, baseURL)
  const summary = structuredClone(SUMMARY) as { raw_summary: { sections: Record<string, unknown> } }
  summary.raw_summary.sections.risks = risks
  const origin = new URL(baseURL).origin
  // Registered after answerApi, so it answers the summary first; everything else falls through.
  await page.route(
    (url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3',
    (route) =>
      route.fulfill({
        status: 200,
        headers: { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' },
        json: summary,
      }),
  )
  await page.addInitScript((t: string) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  await expect(page.locator(`${SECTION} li h3`).first()).toBeVisible()
  await page.locator(SECTION).scrollIntoViewIfNeeded()
}

/** Every measurement the assertions need, read from the rendered rows. */
const measure = (page: Page) =>
  page.evaluate((section) => {
    /** The box the element's text actually paints in, which overflows the element when a token cannot wrap. */
    const textBox = (el: Element) => {
      const range = document.createRange()
      range.selectNodeContents(el)
      return range.getBoundingClientRect()
    }
    return {
      dark: document.documentElement.classList.contains('dark'),
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      rows: Array.from(document.querySelectorAll(`${section} li`))
        .filter((li) => li.querySelector('h3'))
        .map((li) => {
          const row = li.getBoundingClientRect()
          const inside = (el: Element) => {
            const r = textBox(el)
            return {
              row: r.left >= row.left - 0.5 && r.right <= row.right + 0.5,
              page: r.left >= -0.5 && r.right <= window.innerWidth + 0.5,
            }
          }
          const h3 = li.querySelector('h3')!
          const quote = li.querySelector('blockquote')!
          return {
            heading: h3.textContent ?? '',
            headingInside: inside(h3),
            quoteInside: inside(quote),
            quotePx: getComputedStyle(quote).fontSize,
          }
        }),
    }
  }, SECTION)

const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const

for (const viewport of VIEWPORTS) {
  test.describe(`risk evidence rows at ${viewport.width}`, () => {
    test.use({ viewport })

    for (const theme of ['light', 'dark'] as const) {
      test(`${theme}: heading and excerpt inside the row and the page, the excerpt at 14px`, async ({ page, baseURL }) => {
        await openRisks(page, baseURL!, theme)
        const m = await measure(page)
        expect(m.dark).toBe(theme === 'dark')
        expect(m.rows).toHaveLength(RISKS.length)
        for (const row of m.rows) {
          expect.soft(row.headingInside, `heading inside: ${row.heading}`).toEqual({ row: true, page: true })
          expect.soft(row.quoteInside, `excerpt inside: ${row.heading}`).toEqual({ row: true, page: true })
          expect.soft(row.quotePx).toBe('14px')
        }
        expect.soft(m.pageOverflow, 'page scrolls sideways').toBeLessThanOrEqual(0)
      })
    }
  })
}

// A heading cut from a filing can carry one long unbreakable token. The span is synthetic: no
// production risk span has one, but nothing in the rule stops it.
const LONG_TOKEN: Risk = {
  ...RISKS[0],
  supporting_evidence: 'Risk disclosures are posted at investor.example.com/secfilings/annualreports/form10k/riskfactors2025 every quarter.',
}

test.describe('a risk row with a long unbreakable token at 390', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('wraps the token inside the row and the page, in the heading and the excerpt', async ({ page, baseURL }) => {
    await openRisks(page, baseURL!, 'light', [LONG_TOKEN])
    const m = await measure(page)
    expect(m.rows).toHaveLength(1)
    const [row] = m.rows
    expect(row.heading).toContain('investor.example.com/secfilings/annualreports/form10k/riskfactors2025')
    expect.soft(row.headingInside, 'heading inside').toEqual({ row: true, page: true })
    expect.soft(row.quoteInside, 'excerpt inside').toEqual({ row: true, page: true })
    expect.soft(m.pageOverflow, 'page scrolls sideways').toBeLessThanOrEqual(0)
  })
})
