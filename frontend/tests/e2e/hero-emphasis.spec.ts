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

        if (doubled) {
          // Word bounds alone miss a wrapped inline block painting over the preceding descender.
          // Hide only phrase ink in both captures, then compare every neighboring ink pixel,
          // including antialias edges, with the decorative background removed in place.
          const heading = page.locator('#hero-h')
          const background = await page.locator('body').evaluate((element) => getComputedStyle(element).backgroundColor)
          expect(background).toMatch(/^rgb\(/)
          const paper = background.match(/\d+/g)!.slice(0, 3).map(Number)
          const hiddenPhrase = await page.addStyleTag({
            content: '#hero-h .en-hero-emphasis { color: transparent !important; }',
          })
          let painted: Buffer
          let unpainted: Buffer
          try {
            painted = await heading.screenshot({ animations: 'disabled' })
            const diagnostic = await page.addStyleTag({
              content: '#hero-h .en-hero-emphasis, #hero-h .en-hero-emphasis::before { background: transparent !important; box-shadow: none !important; }',
            })
            try {
              unpainted = await heading.screenshot({ animations: 'disabled' })
            } finally {
              await diagnostic.evaluate((element) => element.remove())
            }
          } finally {
            await hiddenPhrase.evaluate((element) => element.remove())
          }
          const lostInk = await page.evaluate(async ({ painted, unpainted, paper }) => {
            const read = async (png: string) => {
              const image = new Image()
              image.src = `data:image/png;base64,${png}`
              await image.decode()
              const canvas = document.createElement('canvas')
              canvas.width = image.width
              canvas.height = image.height
              const context = canvas.getContext('2d')!
              context.drawImage(image, 0, 0)
              return context.getImageData(0, 0, canvas.width, canvas.height)
            }
            const [withFill, withoutFill] = await Promise.all([read(painted), read(unpainted)])
            if (withFill.width !== withoutFill.width || withFill.height !== withoutFill.height) {
              throw new Error('The paint-only diagnostic changed the headline layout')
            }
            let count = 0
            for (let i = 0; i < withoutFill.data.length; i += 4) {
              if (paper.some((channel, j) => withoutFill.data[i + j] !== channel)
                && paper.some((_, j) => withFill.data[i + j] !== withoutFill.data[i + j])) count++
            }
            return count
          }, { painted: painted!.toString('base64'), unpainted: unpainted!.toString('base64'), paper })
          expect(lostInk, 'The highlight must not cover neighboring heading ink').toBe(0)
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
