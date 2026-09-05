import { test, expect } from '@playwright/test'
import { CITATION_HIGHLIGHT_CSS } from '../../features/filings/components/copilot/highlightInDom'

// The copilot citation paint (`::highlight(copilot-citation)`) is registered at runtime as a
// constructed stylesheet (highlightInDom.ts) because Next 16.3's CSS pipeline (lightningcss) does
// not recognise the pseudo-element and warns on it in globals.css. This guards the two things that
// fix depends on in the shipped Chromium build — the CSS Custom Highlight API exists, and the exact
// rule text the module adopts parses as a real ::highlight() rule — and that the rule has not crept
// back into globals.css. Runs against `next start` with NO backend: the filing page's dead-API
// fallback is fine, only the global stylesheet and the browser matter here.
test.describe('Copilot citation highlight', () => {
  test('Chromium exposes CSS.highlights and accepts the constructed ::highlight rule', async ({ page }) => {
    await page.goto('/filing/3')
    await page.waitForLoadState('domcontentloaded')

    const result = await page.evaluate((css) => {
      const w = window as unknown as { Highlight?: unknown }
      const hasApi = typeof CSS !== 'undefined' && 'highlights' in CSS && typeof w.Highlight === 'function'

      const sheet = new CSSStyleSheet()
      sheet.replaceSync(css)
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]
      const rule = sheet.cssRules[0] as CSSStyleRule | undefined

      const inLinkedSheets = Array.from(document.styleSheets).some((s) => {
        try {
          return Array.from(s.cssRules).some((r) => r.cssText.includes('::highlight('))
        } catch {
          return false
        }
      })

      return {
        hasApi,
        adopted: document.adoptedStyleSheets.includes(sheet),
        selector: rule?.selectorText ?? null,
        background: rule?.style.backgroundColor ?? null,
        inLinkedSheets,
      }
    }, CITATION_HIGHLIGHT_CSS)

    expect(result.hasApi).toBe(true)
    expect(result.adopted).toBe(true)
    // 'copilot-citation' is the key highlightInDom.ts passes to CSS.highlights.set().
    expect(result.selector).toBe('::highlight(copilot-citation)')
    expect(result.background).toBe('rgba(79, 122, 99, 0.22)')
    // The rule must not ride through globals.css again — that is what trips the build warning.
    expect(result.inLinkedSheets).toBe(false)
  })
})
