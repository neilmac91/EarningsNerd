import { expect, test } from '@playwright/test'

// Exercise the real font and the enlarged-text fallback: a nonbreaking decorative span can
// pass the default phone capture while pushing its words outside a 200% reader's viewport.
for (const theme of ['light', 'dark'] as const) {
  for (const width of [320, 354, 390, 1440]) {
    for (const doubled of [false, true]) {
      test(`source emphasis fits at ${width}px, ${theme}, ${doubled ? '200%' : '100%'} text`, async ({ page }) => {
        await page.setViewportSize({ width, height: 1000 })
        await page.addInitScript((mode) => {
          localStorage.setItem('theme', mode)
          localStorage.setItem('cookie_consent', JSON.stringify({
            essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString(),
          }))
        }, theme)
        await page.goto('/')
        const phrase = page.locator('#hero-h .en-hero-emphasis')
        await expect(phrase).toHaveText('the source')
        const cdp = await page.context().newCDPSession(page)
        if (doubled) {
          await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
          await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('32px')
        }
        await page.evaluate(() => document.fonts.ready)

        const layout = await phrase.evaluate((element) => {
          const text = element.firstChild!
          const words = [...(text.textContent ?? '').matchAll(/\S+/g)].map((word) => {
            const range = document.createRange()
            range.setStart(text, word.index!)
            range.setEnd(text, word.index! + word[0].length)
            const rects = [...range.getClientRects()].filter((r) => r.width > 0)
            return { word: word[0], rects: rects.map((r) => ({ left: r.left, right: r.right, top: r.top })) }
          })
          const style = getComputedStyle(element)
          return {
            words,
            viewport: document.documentElement.clientWidth,
            fontStyle: style.fontStyle,
            box: element.getBoundingClientRect().toJSON(),
          }
        })
        expect(layout.words.map((word) => word.word)).toEqual(['the', 'source'])
        expect(layout.fontStyle).toBe('italic')
        expect(layout.box.left).toBeGreaterThanOrEqual(0)
        expect(layout.box.right).toBeLessThanOrEqual(layout.viewport)
        for (const word of layout.words) {
          expect(word.rects, `${word.word} must not break inside a word`).toHaveLength(1)
          expect(word.rects[0].left).toBeGreaterThanOrEqual(0)
          expect(word.rects[0].right).toBeLessThanOrEqual(layout.viewport)
        }
        if (!doubled) {
          expect(layout.words[0].rects[0].top).toBe(layout.words[1].rects[0].top)
        }

        // The face must really load; font-style:italic on the roman face would synthesize a slant.
        await cdp.send('DOM.enable')
        await cdp.send('CSS.enable')
        const document = await cdp.send('DOM.getDocument')
        const node = await cdp.send('DOM.querySelector', { nodeId: document.root.nodeId, selector: '#hero-h .en-hero-emphasis' })
        const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId: node.nodeId })
        expect(fonts.some((font) => font.isCustomFont && font.postScriptName === 'Inter-Italic')).toBe(true)
      })
    }
  }
}
