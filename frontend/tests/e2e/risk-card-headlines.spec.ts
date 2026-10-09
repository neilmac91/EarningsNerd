import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, SUMMARY, answerApi, type Theme } from './fixtures/filing3Api'

/**
 * Risk cards on the filing page (founder option b): what only a real layout shows, in Chromium at 390
 * and 1440 in both themes. Which headline, glyph and evidence a card renders is pinned once, in
 * jsdom (tests/unit/riskHeadline.spec.ts and SummaryRisks.spec.tsx; one test per rule, AGENTS.md §4).
 * Here:
 *
 *   - the glyph beside the title sits level with the first line of a headline that wraps;
 *   - the evidence text computes to 14px, and its "Evidence" eyebrow reaches 4.5:1 against the box
 *     it sits on (computed colours, WCAG relative luminance);
 *   - the cards keep the panel fill (rule 11);
 *   - headings and evidence wrap inside their card, a long unbreakable token (a URL) included:
 *     nothing scrolls sideways.
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
  await expect(page.locator(`${SECTION} h4`).first()).toBeVisible()
  await page.locator(SECTION).scrollIntoViewIfNeeded()
}

/** Every measurement the assertions need, read from the rendered cards. */
const measure = (page: Page) =>
  page.evaluate((section) => {
    const rgb = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number)
    const luminance = ([r, g, b]: number[]) => {
      const lin = (v: number) => {
        const s = v / 255
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      }
      return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    }
    /** The first ancestor-or-self background that paints (alpha > 0). */
    const groundOf = (el: Element | null): string => {
      for (let node = el; node; node = node.parentElement) {
        const bg = getComputedStyle(node).backgroundColor
        const [, , , a = 1] = rgb(bg)
        if (bg !== 'transparent' && a > 0) return bg
      }
      return getComputedStyle(document.body).backgroundColor
    }
    const contrast = (fg: string, bg: string) => {
      const [l1, l2] = [luminance(rgb(fg)), luminance(rgb(bg))].sort((a, b) => b - a)
      return Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100
    }
    const root = document.querySelector(section)!
    return {
      dark: document.documentElement.classList.contains('dark'),
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      cards: Array.from(root.querySelectorAll('h4')).map((h4) => {
        const card = h4.closest('[data-summary-block]') ?? h4.parentElement!.parentElement!.parentElement!
        const eyebrow = Array.from(card.querySelectorAll('span')).find((s) => s.textContent?.trim() === 'Evidence') ?? null
        const box = eyebrow?.parentElement ?? null
        const cardRect = card.getBoundingClientRect()
        const within = (el: Element | null) => {
          if (!el) return false
          const r = el.getBoundingClientRect()
          return r.left >= cardRect.left - 0.5 && r.right <= cardRect.right + 0.5
        }
        return {
          headline: h4.textContent ?? '',
          evidencePx: box ? getComputedStyle(box).fontSize : '',
          eyebrowContrast: eyebrow ? contrast(getComputedStyle(eyebrow).color, groundOf(eyebrow)) : 0,
          cardFill: getComputedStyle(card).backgroundColor,
          headlineInside: within(h4),
          boxInside: within(box),
          cardOverflow: card.scrollWidth - card.clientWidth,
          headlineLines: Math.round(h4.getBoundingClientRect().height / parseFloat(getComputedStyle(h4).lineHeight)),
          // Glyph centre minus the centre of the heading's first line (0 = level with the opening words).
          glyphOffset: (() => {
            const icon = h4.parentElement!.querySelector('svg')!.getBoundingClientRect()
            const top = h4.getBoundingClientRect().top
            return Math.round(icon.top + icon.height / 2 - (top + parseFloat(getComputedStyle(h4).lineHeight) / 2))
          })(),
        }
      }),
    }
  }, SECTION)

const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const

for (const viewport of VIEWPORTS) {
  test.describe(`risk cards at ${viewport.width}`, () => {
    test.use({ viewport })

    for (const theme of ['light', 'dark'] as const) {
      test(`${theme}: glyph level with the first line, 14px evidence, AA eyebrow, panel fill, no sideways scroll`, async ({ page, baseURL }) => {
        await openRisks(page, baseURL!, theme)
        const m = await measure(page)
        expect(m.dark).toBe(theme === 'dark')
        expect(m.cards).toHaveLength(RISKS.length)
        for (const card of m.cards) {
          expect.soft(Math.abs(card.glyphOffset), 'glyph level with the first line of a wrapped headline').toBeLessThanOrEqual(2)
          expect.soft(card.evidencePx).toBe('14px')
          expect.soft(card.eyebrowContrast, `eyebrow contrast ${card.eyebrowContrast}:1`).toBeGreaterThanOrEqual(4.5)
          expect.soft(card.headlineInside && card.boxInside, 'heading and evidence inside the card').toBe(true)
          expect.soft(card.cardOverflow).toBeLessThanOrEqual(0)
        }
        // Rule 11: the cards keep the panel fill (light #FBFAF6, dark #1F2937).
        expect.soft(new Set(m.cards.map((c) => c.cardFill))).toEqual(new Set([theme === 'dark' ? 'rgb(31, 41, 55)' : 'rgb(251, 250, 246)']))
        expect.soft(m.pageOverflow).toBeLessThanOrEqual(0)
        test.info().annotations.push({
          type: 'measured',
          description: JSON.stringify(m.cards.map(({ headline, evidencePx, eyebrowContrast, headlineLines, glyphOffset }) => ({ headline: headline.slice(0, 24), evidencePx, eyebrowContrast, headlineLines, glyphOffset }))),
        })
      })
    }
  })
}

// A heading quoted from a filing can carry one long unbreakable token. The span is synthetic: no
// production risk span has one, but nothing in the rule stops it.
const LONG_TOKEN: Risk = {
  ...RISKS[0],
  supporting_evidence: 'Risk disclosures are posted at investor.example.com/secfilings/annualreports/form10k/riskfactors2025 every quarter.',
}

test.describe('a risk heading with a long unbreakable token at 390', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('wraps the token inside the card in the heading and the evidence', async ({ page, baseURL }) => {
    await openRisks(page, baseURL!, 'light', [LONG_TOKEN])
    const m = await measure(page)
    expect(m.cards).toHaveLength(1)
    const [card] = m.cards
    expect(card.headline).toContain('investor.example.com/secfilings/annualreports/form10k/riskfactors2025')
    expect.soft(card.headlineInside, 'heading inside the card').toBe(true)
    expect.soft(card.boxInside, 'evidence inside the card').toBe(true)
    expect.soft(card.cardOverflow).toBeLessThanOrEqual(0)
    expect.soft(m.pageOverflow).toBeLessThanOrEqual(0)
  })
})
