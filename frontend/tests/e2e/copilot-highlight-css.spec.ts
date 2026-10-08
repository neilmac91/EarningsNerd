import { readFileSync } from 'node:fs'
import path from 'node:path'
import * as ts from 'typescript'
import { test, expect } from '@playwright/test'

// The copilot citation paint (`::highlight(copilot-citation)`) is registered at runtime as a
// constructed stylesheet by highlightInDom.ts, because lightningcss (Next 16.3's CSS pipeline) does
// not know the pseudo-element: it emits a SelectorError warning and, with error recovery, keeps the
// rule, but Next's build surfaces that as "Parsing CSS source code failed" on every build.
//
// This spec exercises the REAL module in real Chromium — the Copilot UI itself needs a backend, and
// CI runs Playwright against `next start` with none (lessons/test-e2e-runs-without-backend.md). The
// module graph (4 files, no framework imports) is transpiled with the repo's own `typescript` and
// loaded as data: ES modules on the shipped filing page, then driven exactly as CitationChip does.
// Observable contract: after a highlight, `document.adoptedStyleSheets` carries a sheet whose rules
// include `::highlight(copilot-citation)`, and `CSS.highlights.get('copilot-citation')` exists.

const FRONTEND = path.resolve(__dirname, '../..')

/** Transpile one TS module to ESM and return a data: URL for it, with imports rewritten to `deps`. */
function moduleUrl(file: string, deps: Record<string, string>): string {
  const src = readFileSync(path.join(FRONTEND, file), 'utf8')
  let js = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText
  for (const [spec, url] of Object.entries(deps)) {
    js = js.replace(new RegExp(`from ['"]${spec.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}['"]`), `from '${url}'`)
  }
  return `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`
}

const motion = moduleUrl('lib/motion.ts', {})
const citationFlash = moduleUrl('lib/citationFlash.ts', { '@/lib/motion': motion })
const excerptMatch = moduleUrl('features/filings/components/copilot/excerptMatch.ts', {})
const highlightInDom = moduleUrl('features/filings/components/copilot/highlightInDom.ts', {
  './excerptMatch': excerptMatch,
  '@/lib/citationFlash': citationFlash,
})

test.describe('Copilot citation highlight', () => {
  test('adopts the ::highlight(copilot-citation) sheet and registers the highlight in Chromium', async ({ page }) => {
    await page.goto('/filing/3')
    await page.waitForLoadState('domcontentloaded')

    await page.addScriptTag({
      type: 'module',
      content: `import * as m from '${highlightInDom}'; window.__copilotHighlight = m`,
    })
    await page.waitForFunction(() => '__copilotHighlight' in window)

    const result = await page.evaluate(() => {
      const m = (window as unknown as {
        __copilotHighlight: {
          highlightExcerptInDom: (c: HTMLElement, e: string) => boolean
          clearCitationHighlight: () => void
        }
      }).__copilotHighlight
      const highlights = (CSS as unknown as { highlights: Map<string, { size: number }> }).highlights

      // Adjacent blocks share a flat-text boundary. The second excerpt must flash paragraph 2,
      // not paragraph 1's end, and must still match through the document's final character.
      const container = document.createElement('div')
      container.innerHTML =
        '<p data-para="1">Net income rose on higher services revenue during the quarter.</p>' +
        '<p data-para="2">Operating expenses declined as headcount stayed flat through the period</p>'
      document.body.appendChild(container)
      const flashedParas = () =>
        Array.from(container.querySelectorAll<HTMLElement>('.citation-flash')).map((el) => el.dataset.para ?? el.tagName)

      const found = m.highlightExcerptInDom(container, 'Net income rose on higher services revenue during the quarter')
      const flashedAfterFirst = flashedParas()
      const rule = document.adoptedStyleSheets
        .flatMap((s) => Array.from(s.cssRules))
        .find((r): r is CSSStyleRule => r instanceof CSSStyleRule && r.selectorText === '::highlight(copilot-citation)')
      const registered = highlights.get('copilot-citation')

      const foundSecond = m.highlightExcerptInDom(container, 'Operating expenses declined as headcount stayed flat through the period')
      const flashedAfterSecond = flashedParas()
      const sheetsAfterSecond = document.adoptedStyleSheets.length

      m.clearCitationHighlight()
      const clearedStillRegistered = highlights.has('copilot-citation')
      document.body.removeChild(container)

      return {
        found,
        foundSecond,
        ruleText: rule?.cssText ?? null,
        background: rule?.style.backgroundColor ?? null,
        registeredRanges: registered?.size ?? null,
        sheetsAfterSecond,
        clearedStillRegistered,
        flashedAfterFirst,
        flashedAfterSecond,
      }
    })

    expect(result.found).toBe(true)
    expect(result.foundSecond).toBe(true)
    expect(result.ruleText).toContain('::highlight(copilot-citation)')
    expect(result.background).toBe('rgba(79, 122, 99, 0.22)')
    // One Highlight holding exactly the matched Range.
    expect(result.registeredRanges).toBe(1)
    // A second highlight reuses the adopted sheet rather than adding another.
    expect(result.sheetsAfterSecond).toBe(1)
    expect(result.clearedStillRegistered).toBe(false)
    // The block flash lands on the paragraph that holds the excerpt — and only that one — and the
    // first paragraph's flash (1.8 s) is still running when the second lands.
    expect(result.flashedAfterFirst).toEqual(['1'])
    expect(result.flashedAfterSecond).toEqual(['1', '2'])
  })

  // EN-04: the jump scrolls the container it is given and the scroll boxes inside it, never the page.
  // scrollIntoView scrolled every scrollable ancestor, the page included: with a reader wider than its
  // pane that slid the filing page sideways. Real layout here (jsdom has none): a reader-like scroller
  // placed below the fold of a page that can scroll both ways, holding a wide table in its own
  // horizontal scroll box, with the cited sentence in the table's far-right cell.
  test('scrolls only inside the container: a far-right table cell is brought into its own box, the page never moves', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/filing/3')
    await page.waitForLoadState('domcontentloaded')
    await page.addScriptTag({
      type: 'module',
      content: `import * as m from '${highlightInDom}'; window.__copilotHighlight = m`,
    })
    await page.waitForFunction(() => '__copilotHighlight' in window)

    const cited = 'Reportable since FY2013'
    await page.evaluate((sentence) => {
      const spacer = document.createElement('div')
      spacer.id = 'en04-spacer'
      spacer.style.cssText = 'position:absolute;top:0;left:0;width:4000px;height:4000px;pointer-events:none'
      document.body.appendChild(spacer)
      const reader = document.createElement('div')
      reader.id = 'en04-reader'
      reader.style.cssText = 'position:absolute;top:2000px;left:2000px;width:400px;height:300px;overflow-y:auto'
      const rows = Array.from({ length: 12 }, (_, i) => `<p>Paragraph ${i + 1} of the filing before the table.</p>`).join('')
      const cells = Array.from({ length: 8 }, (_, i) => `<td style="white-space:nowrap;padding:0 24px">Column ${i + 1} value</td>`).join('')
      reader.innerHTML = `${rows}<div id="en04-box" style="overflow-x:auto"><table><tbody><tr>${cells}<td id="en04-cell" style="white-space:nowrap">${sentence}</td></tr></tbody></table></div>${rows}`
      document.body.appendChild(reader)
      window.scrollTo(0, 0)
    }, cited)

    const result = await page.evaluate(async (sentence) => {
      const m = (window as unknown as { __copilotHighlight: { highlightExcerptInDom: (c: HTMLElement, e: string) => boolean } }).__copilotHighlight
      const reader = document.getElementById('en04-reader')!
      const box = document.getElementById('en04-box')!
      const cell = document.getElementById('en04-cell')!
      const found = m.highlightExcerptInDom(reader, sentence)
      // Let the smooth scroll finish: nothing moves for three frames running.
      let last = ''
      for (let stable = 0, i = 0; stable < 3 && i < 300; i++) {
        await new Promise((r) => requestAnimationFrame(r))
        const now = [window.scrollX, window.scrollY, reader.scrollTop, box.scrollLeft].join()
        stable = now === last ? stable + 1 : 0
        last = now
      }
      const b = box.getBoundingClientRect()
      const c = cell.getBoundingClientRect()
      const r = reader.getBoundingClientRect()
      const out = {
        found,
        windowScroll: [window.scrollX, window.scrollY],
        boxScrollLeft: box.scrollLeft,
        readerScrollTop: reader.scrollTop,
        // The cell, against the box's and the reader's scrollports (both narrower than the cell's travel).
        cell: { left: c.left, right: c.right, top: c.top, bottom: c.bottom },
        boxPort: { left: b.left, right: b.left + box.clientWidth },
        readerPort: { top: r.top, bottom: r.top + reader.clientHeight },
      }
      reader.remove()
      document.getElementById('en04-spacer')?.remove()
      return out
    }, cited)

    expect(result.found).toBe(true)
    expect(result.windowScroll).toEqual([0, 0])
    expect(result.boxScrollLeft).toBeGreaterThan(0)
    expect(result.readerScrollTop).toBeGreaterThan(0)
    expect(result.cell.left).toBeGreaterThanOrEqual(result.boxPort.left - 0.5)
    expect(result.cell.right).toBeLessThanOrEqual(result.boxPort.right + 0.5)
    expect(result.cell.top).toBeGreaterThanOrEqual(result.readerPort.top - 0.5)
    expect(result.cell.bottom).toBeLessThanOrEqual(result.readerPort.bottom + 0.5)
  })
})
