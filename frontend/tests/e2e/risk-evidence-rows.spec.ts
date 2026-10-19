import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'
import { textContrast } from './fixtures/contrast'
import { API_ORIGIN, DOCUMENT, EXCERPT, SUMMARY, answerApi, type Theme } from './fixtures/filing3Api'

/**
 * Risk evidence rows on the filing page (2026-10 critique P-03, founder option b), as a marked copy
 * (D-044), and the summary's quotes: what only a real layout shows, in Chromium at 320, 390 and 1440 in both
 * themes, at the default text size and with the browser's text doubled. Which heading a row gets, that its blockquote holds the
 * whole span, and which rows the device marks are pinned once, in jsdom (riskHeadline.spec.ts,
 * riskTitle.spec.ts, SummaryRisks.spec.tsx; one test per rule, AGENTS.md §4). Here:
 *
 *   - each row's h3 and blockquote text sits inside the row and the viewport, and the page does not
 *     scroll sideways, a long unbreakable token (a URL) included at 390;
 *   - each located excerpt is a marked block in the filing's face at 16px (1rem), on the device's tint,
 *     and no word in it breaks mid-word, read a character at a time (at 320px under 200% text the margin
 *     and the rows' rem insets left 101px of 32px serif, and 45 of 134 words broke);
 *   - below a measure the margin gives way (MarkedCopy, a query container in em): it stays at the default
 *     size on a 320px phone and goes under 200% text at 390px and below, the rows' inset with it, and
 *     every marker stays in its heading;
 *   - where the margin shows, every marker has its twin in it, centred on the marker's line, no two twins
 *     overprint, and the margin holds (2.25rem at 320 and 390, 2.75rem from sm) with each twin inside it;
 *   - the marker, the twin and the excerpt's ink clear 4.5:1 on what is behind them (text-floors' rule,
 *     the composited ground of fixtures/contrast.ts), in both themes;
 *   - a quote whose evidence the server located is a marked block in the filing's face at 1rem on the
 *     tint, its words and its speaker (in the body face) at 4.5:1 or more, with no marker and no twin;
 *     a quote whose evidence was not located keeps the neutral 2px hairline in the body face; each
 *     quote's words, speaker and chip stay inside its block (the chip wraps under the speaker where
 *     the marked block's padding leaves too little room, as at 390 under 200% text).
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
const QUOTES = '#forward-signals'
/** The summary's quotes (D-044), in a section of their own after the risks: the first is a sentence of filing 3
    (fixtures/filing3Api.ts EXCERPT) whose evidence the server located; the second is synthetic, cited without a match. */
const QUOTE_SECTION = {
  id: 'forward-signals',
  title: 'Forward Signals',
  blocks: [
    { kind: 'quote', text: EXCERPT, speaker: 'Filing statement', evidence: { excerpt: EXCERPT, section_ref: 'Item 7', verified: true, fragment_url: `${DOCUMENT}#:~:text=Americas%20net%20sales` } },
    { kind: 'quote', text: 'We expect the year ahead to bring steady demand.', speaker: 'CEO', evidence: { excerpt: null, section_ref: 'Item 7', verified: false, fragment_url: DOCUMENT } },
  ],
}

async function openRisks(page: Page, baseURL: string, theme: Theme, risks: Risk[] = RISKS) {
  await answerApi(page, baseURL)
  const summary = structuredClone(SUMMARY) as { raw_summary: { sections: Record<string, unknown> }; rendered_sections: unknown[] }
  summary.raw_summary.sections.risks = risks
  summary.rendered_sections.push(QUOTE_SECTION)
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

/** Chromium's own text setting doubled (standard 32, fixed 26), as reflow-200.spec.ts sets it, then a beat for the
    margin to measure its markers again (MarkedCopy re-reads them when its body resizes). */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took' })
    .toBe('32px')
  await page.evaluate(() => document.fonts.ready)
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
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
    /** The words a block breaks mid-word, read a character at a time as painted (reflow-200's method): two
        characters of one text node that are not spaces, on different lines, the first not a hyphen or a dash. A
        word never spans text nodes here, and a quote's words, its speaker and its chip are nodes of their own. */
    const midWordBreaks = (el: Element) => {
      const broken: string[] = []
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
        const chars: { c: string; top: number | null }[] = []
        for (let i = 0; i < node.length; i++) {
          const char = document.createRange()
          char.setStart(node, i)
          char.setEnd(node, i + 1)
          const r = char.getBoundingClientRect()
          chars.push({ c: node.data[i], top: r.width || r.height ? r.top : null })
        }
        for (let i = 1; i < chars.length; i++) {
          const [a, b] = [chars[i - 1], chars[i]]
          if (a.top === null || b.top === null || /\s/.test(a.c) || /\s/.test(b.c) || /[-\u2010\u2011\u2013\u2014]/.test(a.c) || b.top <= a.top + 4) continue
          let start = i - 1
          while (start > 0 && !/\s/.test(chars[start - 1].c)) start--
          let end = i
          while (end < chars.length && !/\s/.test(chars[end].c)) end++
          broken.push(`${chars.slice(start, i).map((c) => c.c).join('')} / ${chars.slice(i, end).map((c) => c.c).join('')}`)
        }
      }
      return broken
    }
    const root = document.querySelector(section)!
    const margin = root.querySelector('.en-margin')
    const marginBox = margin?.getBoundingClientRect()
    const mid = (r: DOMRect) => (r.top + r.bottom) / 2
    return {
      dark: document.documentElement.classList.contains('dark'),
      rootPx: parseFloat(getComputedStyle(document.documentElement).fontSize),
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      marginShown: !!margin && getComputedStyle(margin).display !== 'none',
      marginWidth: marginBox?.width ?? null,
      rowInsets: Array.from(root.querySelectorAll('li')).filter((li) => li.querySelector('h3')).map((li) => getComputedStyle(li).paddingLeft),
      // Every marked block on the page: the located Risks excerpts and the located quote.
      midWordBreaks: Array.from(document.querySelectorAll('blockquote.en-marked')).flatMap(midWordBreaks),
      markers: Array.from(root.querySelectorAll<HTMLElement>('[data-en-ref]')).map((el) => ({ label: el.textContent, mid: mid(el.getBoundingClientRect()) })),
      twins: Array.from(root.querySelectorAll<HTMLElement>('.en-margin-mark')).map((el) => {
        const r = textBox(el)
        return {
          label: el.textContent,
          mid: mid(el.getBoundingClientRect()),
          top: r.top,
          bottom: r.bottom,
          inMargin: !!marginBox && r.left >= marginBox.left - 0.5 && r.right <= marginBox.right + 0.5,
        }
      }),
      rows: Array.from(root.querySelectorAll('li'))
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
          const style = getComputedStyle(quote)
          return {
            heading: h3.textContent ?? '',
            headingInside: inside(h3),
            quoteInside: inside(quote),
            marked: quote.classList.contains('en-marked'),
            quotePx: parseFloat(style.fontSize),
            quoteFace: style.fontFamily,
            quoteTint: style.backgroundColor,
          }
        }),
    }
  }, SECTION)

const VIEWPORTS = [
  { width: 320, height: 640 },
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const

for (const viewport of VIEWPORTS) {
  test.describe(`risk evidence rows at ${viewport.width}`, () => {
    test.use({ viewport })

    for (const theme of ['light', 'dark'] as const) {
      for (const text of ['default', '200%'] as const) {
        test(`${theme}, ${text} text: the rows inside the page, a marked block per located excerpt, each marker's twin on its line`, async ({ page, baseURL }) => {
          await openRisks(page, baseURL!, theme)
          if (text === '200%') await doubleText(page)
          // Below a measure the margin gives way: it stays at the default size on a 320px phone and goes under 200% text
          // at 390px and below (a marked copy narrower than 13em of its own width).
          const marginShown = !(text === '200%' && viewport.width <= 390)
          // The margin re-measures after layout settles (fonts, the text setting): wait for every twin to reach its marker,
          // or, where the margin gives way, for it to go.
          await expect
            .poll(async () => {
              const { markers, twins, marginShown: shown } = await measure(page)
              if (!marginShown) return markers.length === RISKS.length && !shown
              return markers.length === RISKS.length && twins.length === markers.length && markers.every((m, i) => Math.abs(twins[i].mid - m.mid) <= 1)
            }, { message: marginShown ? 'each twin settles on its marker' : 'the margin gives way' })
            .toBe(true)
          const m = await measure(page)
          expect(m.dark).toBe(theme === 'dark')
          expect(m.rootPx).toBe(text === '200%' ? 32 : 16)
          expect(m.rows).toHaveLength(RISKS.length)
          for (const row of m.rows) {
            expect.soft(row.headingInside, `heading inside: ${row.heading}`).toEqual({ row: true, page: true })
            expect.soft(row.quoteInside, `excerpt inside: ${row.heading}`).toEqual({ row: true, page: true })
            // A located excerpt is a marked block in the filing's face, at 1rem, on the device's tint.
            expect.soft(row.marked, `marked block: ${row.heading}`).toBe(true)
            expect.soft(row.quotePx).toBe(m.rootPx)
            expect.soft(row.quoteFace).toMatch(/Newsreader/)
            expect.soft(row.quoteTint).toBe(theme === 'dark' ? 'rgba(127, 178, 149, 0.14)' : 'rgb(236, 242, 238)')
          }
          // No word of a marked block (a located excerpt or the located quote) breaks mid-word.
          expect.soft(m.midWordBreaks, 'words broken mid-word in the marked blocks').toEqual([])
          // One marker per located row, numbered in reading order, in its heading whether or not the margin shows.
          expect(m.markers.map((marker) => marker.label)).toEqual(RISKS.map((_, i) => `[${i + 1}]`))
          expect.soft(m.marginShown, marginShown ? 'the margin shows' : 'the margin gives way').toBe(marginShown)
          if (marginShown) {
            // Each marker's twin on its line in the margin.
            expect(m.twins.map((twin) => twin.label)).toEqual(m.markers.map((marker) => marker.label))
            m.markers.forEach((marker, i) => expect.soft(Math.abs(m.twins[i].mid - marker.mid), `${marker.label} twin on its line`).toBeLessThanOrEqual(1))
            expect.soft(m.twins.every((twin) => twin.inMargin), 'every twin inside the margin').toBe(true)
            for (let i = 1; i < m.twins.length; i += 1) {
              expect.soft(m.twins[i].top, `${m.twins[i].label} clear of ${m.twins[i - 1].label}`).toBeGreaterThanOrEqual(m.twins[i - 1].bottom)
            }
            // The margin holds: 2.25rem on a phone, 2.75rem from sm, and each row sits inset beside it.
            expect.soft(m.marginWidth).toBeCloseTo((viewport.width >= 640 ? 2.75 : 2.25) * m.rootPx, 0)
            expect.soft(m.rowInsets.every((inset) => parseFloat(inset) > 0), 'each row inset beside the margin').toBe(true)
          } else {
            // The rows drop their inset with the margin.
            expect.soft(m.rowInsets.every((inset) => inset === '0px'), 'no row inset without the margin').toBe(true)
          }
          expect.soft(m.pageOverflow, 'page scrolls sideways').toBeLessThanOrEqual(0)

          // The marker, the twin (where the margin shows) and the excerpt's ink on the marked block's tint: text-floors'
          // 4.5:1, measured on the ground each one is painted over.
          const section = page.locator(SECTION)
          for (const [name, locator] of [
            ['marker', section.locator('[data-en-ref]').first()],
            ...(marginShown ? ([['twin', section.locator('.en-margin-mark').first()]] as const) : []),
            ['excerpt', section.locator('blockquote.en-marked').first()],
          ] as const) {
            expect.soft(await textContrast(locator), `${name} contrast`).toBeGreaterThanOrEqual(4.5)
          }

          // The summary's quotes: the located one a marked block with no marker or twin, the other on the neutral hairline.
          const quotes = page.locator(QUOTES)
          await quotes.scrollIntoViewIfNeeded()
          const q = await quotes.evaluate((root) => {
            const [located, cited] = Array.from(root.querySelectorAll('blockquote'))
            const style = (el: Element) => getComputedStyle(el)
            const r = located.getBoundingClientRect()
            /** What a quote holds (its words, the speaker, the chip) that runs past the block's own edges. */
            const outside = (block: Element) => {
              const b = block.getBoundingClientRect()
              return Array.from(block.querySelectorAll('*'))
                .filter((el) => { const e = el.getBoundingClientRect(); return e.width > 0 && (e.left < b.left - 0.5 || e.right > b.right + 0.5) })
                .map((el) => `${el.tagName.toLowerCase()}: ${(el.textContent ?? '').trim().slice(0, 40)}`)
            }
            return {
              outside: { located: outside(located), cited: outside(cited) },
              located: {
                marked: located.classList.contains('en-marked'),
                face: style(located).fontFamily,
                px: parseFloat(style(located).fontSize),
                tint: style(located).backgroundColor,
                speakerFace: style(located.querySelector('cite')!).fontFamily,
                inside: r.left >= -0.5 && r.right <= window.innerWidth + 0.5,
              },
              cited: { marked: cited.classList.contains('en-marked'), face: style(cited).fontFamily, rule: style(cited).borderLeftWidth, tint: style(cited).backgroundColor },
              device: root.querySelectorAll('[data-en-ref], .en-margin, .en-margin-mark').length,
            }
          })
          expect.soft(q.located).toEqual({
            marked: true,
            face: expect.stringMatching(/Newsreader/),
            px: m.rootPx,
            tint: theme === 'dark' ? 'rgba(127, 178, 149, 0.14)' : 'rgb(236, 242, 238)',
            speakerFace: expect.not.stringMatching(/Newsreader/),
            inside: true,
          })
          expect.soft(q.cited).toEqual({ marked: false, face: expect.not.stringMatching(/Newsreader/), rule: '2px', tint: 'rgba(0, 0, 0, 0)' })
          expect.soft(q.device, 'a quote block takes no marker and no twin').toBe(0)
          expect.soft(q.outside, "a quote's words, speaker and chip stay inside its block").toEqual({ located: [], cited: [] })
          for (const [name, locator] of [
            ['quote', quotes.locator('blockquote.en-marked p').first()],
            ['speaker', quotes.locator('blockquote.en-marked cite').first()],
          ] as const) {
            expect.soft(await textContrast(locator), `located ${name} contrast`).toBeGreaterThanOrEqual(4.5)
          }
          expect.soft((await measure(page)).pageOverflow, 'page scrolls sideways').toBeLessThanOrEqual(0)
        })
      }
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
