import { readFileSync } from 'node:fs'
import path from 'node:path'
import { createElement, type ComponentType } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, SUMMARY, answerApi, type Theme } from './fixtures/filing3Api'

/**
 * Risk cards on the filing page (founder option b), in a real Chromium at 390 and 1440 in both themes:
 *
 *   - each card is titled with a verbatim prefix of its own verified excerpt (an h4, as before), not
 *     "Filing excerpt n", and the full excerpt still renders below it as the evidence;
 *   - the glyph beside the title is the neutral quotation mark, not the bearish trend arrow, level with
 *     the first line of a headline that wraps;
 *   - the evidence text computes to 14px, and its "Evidence" eyebrow reaches 4.5:1 against the box
 *     it sits on (computed colours, WCAG relative luminance);
 *   - headings and evidence wrap inside their card: nothing scrolls sideways.
 *
 * The four risks are the production filing-3 spans (fixtures/filing-3-risks.json, copied verbatim
 * from raw_summary.sections.risks of the critique harness's cached GET /api/summaries/filing/3,
 * body sha256 1412895e…, fetched 2026-10-04), served into the shared summary fixture, whose own
 * risks list is empty. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the
 * API is answered inside the browser with page.route. DOM and computed-style probes only: this is
 * not a screen-reader test.
 */

const RISKS = JSON.parse(readFileSync(path.join(__dirname, 'fixtures/filing-3-risks.json'), 'utf8')) as Array<{
  supporting_evidence: string
}>
const HEADLINES = [
  'Tariffs and other measures that are applied to the Company’s products or their components…',
  'Substantially all of the Company’s hardware products are manufactured by outsourcing partners…',
  'As of September\u00a027, 2025, the total amount of gross unrecognized tax benefits was $23.2 billion…',
  'Regardless of the merit of particular claims, defending against litigation or responding…',
]
const SECTION = '#risks'

/** The path geometry of a Phosphor glyph, as the installed package renders it. */
const pathsOf = (icon: ComponentType): string[] =>
  Array.from(renderToStaticMarkup(createElement(icon)).matchAll(/\sd="([^"]+)"/g), (m) => m[1])
let QUOTES: string[] = []
let TREND_DOWN: string[] = []

// The package is ESM-only in practice (its CJS entry sits under "type": "module"), so it is loaded
// with a dynamic import rather than the spec's transpiled require.
test.beforeAll(async () => {
  const icons = await import('@phosphor-icons/react')
  QUOTES = pathsOf(icons.QuotesIcon)
  TREND_DOWN = pathsOf(icons.TrendDownIcon)
  expect(QUOTES.length).toBeGreaterThan(0)
  expect(QUOTES).not.toEqual(TREND_DOWN)
})

async function openRisks(page: Page, baseURL: string, theme: Theme) {
  await answerApi(page, baseURL)
  const summary = structuredClone(SUMMARY) as { raw_summary: { sections: Record<string, unknown> } }
  summary.raw_summary.sections.risks = RISKS
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
          level: h4.tagName,
          headline: h4.textContent ?? '',
          glyph: Array.from(h4.parentElement!.querySelectorAll('svg path'), (p) => p.getAttribute('d') ?? ''),
          glyphHidden: h4.parentElement!.querySelector('svg')?.getAttribute('aria-hidden') ?? null,
          evidence: box ? Array.from(box.childNodes).filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent).join('').trim() : '',
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
      test(`${theme}: excerpt headlines, neutral glyph, 14px evidence, AA eyebrow, no sideways scroll`, async ({ page, baseURL }) => {
        await openRisks(page, baseURL!, theme)
        const m = await measure(page)
        expect(m.dark).toBe(theme === 'dark')
        expect(m.cards).toHaveLength(RISKS.length)
        expect.soft(m.cards.map((c) => c.headline)).toEqual(HEADLINES)
        for (const [i, card] of m.cards.entries()) {
          const excerpt = RISKS[i].supporting_evidence
          expect.soft(card.level).toBe('H4')
          // Verbatim: the headline (without its ellipsis) opens the excerpt; the excerpt renders whole.
          expect.soft(excerpt.startsWith(card.headline.replace(/…$/, '')), card.headline).toBe(true)
          expect.soft(card.evidence).toBe(excerpt)
          expect.soft(card.glyph, 'quotation glyph').toEqual(QUOTES)
          expect.soft(card.glyph, 'not the bearish arrow').not.toEqual(TREND_DOWN)
          expect.soft(card.glyphHidden).toBe('true')
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
