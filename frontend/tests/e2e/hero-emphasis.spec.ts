import { expect, test } from '@playwright/test'
import { HEADLINES } from '../../features/marketing/lib/headline'

test.use({ deviceScaleFactor: 2 })

// Exercise every promotional surface with the real face and the enlarged-text fallback. The
// unit gate verifies that every experiment arm renders BrandEmphasis. Its B/C copy is also
// measured here as an explicit layout fixture on the built heading, without changing flags.
const SURFACES = [
  { name: 'home', path: '/', selector: '#hero-h', phrase: 'the source', widths: [320, 354, 390, 1440] },
  { name: 'waitlist', path: '/waitlist', selector: 'main h1', phrase: 'with receipts', widths: [320, 354, 390, 1440] },
  { name: 'auth pane', path: '/login', selector: 'h2:has(.en-hero-emphasis)', phrase: 'shows its work', widths: [1024, 1440] },
]

for (const surface of SURFACES) {
  for (const theme of ['light', 'dark'] as const) {
    for (const width of surface.widths) {
      for (const doubled of [false, true]) {
        test(`${surface.name} emphasis fits at ${width}px, ${theme}, ${doubled ? '200%' : '100%'} text`, async ({ page, baseURL }) => {
          await page.setViewportSize({ width, height: 1000 })
          // Settle the guest header before measuring: a retrying session check otherwise inserts
          // its account link between captures and moves the heading without changing its styling.
          await page.route('**/api/auth/me', (route) => route.fulfill({
            status: 401,
            headers: { 'access-control-allow-origin': new URL(baseURL!).origin, 'access-control-allow-credentials': 'true' },
            json: { detail: 'Not authenticated' },
          }))
          await page.addInitScript((mode) => {
            localStorage.setItem('theme', mode)
            localStorage.setItem('cookie_consent', JSON.stringify({
              essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString(),
            }))
          }, theme)
          await page.goto(surface.path)
          // Theme hydration can animate the page ground while fonts load. Freeze transitions so
          // the paint-only comparison uses one settled ground for both captures.
          await page.addStyleTag({ content: '*, *::before, *::after { transition: none !important; } html { scroll-behavior: auto !important; overflow-anchor: none !important; }' })
          const heading = page.locator(surface.selector)
          const phrase = heading.locator('.en-hero-emphasis')
          await expect(phrase).toHaveText(surface.phrase)
          await expect(phrase).toBeVisible()
          // A present SSR heading may still be replaced by hydration. Inspect React's attachment
          // before temporary copy fixtures, then require this same node throughout the paint pair.
          await expect.poll(() => heading.evaluate((element) => Object.keys(element).some((key) => key.startsWith('__reactFiber$')))).toBe(true)
          if (surface.path !== '/login') {
            await expect(page.getByRole('banner').getByRole('link', {
              // The compact bar's short account link below 72rem (1152px here), the full bar's from it.
              name: width < 1152 ? /^(Sign up|Request invite)$/ : /^(Create a free account|Request an invite)$/,
            })).toBeVisible()
          }
          const headingNode = await heading.elementHandle()
          const cdp = await page.context().newCDPSession(page)
          if (doubled) {
            await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
            await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('32px')
          }
          await page.evaluate(() => document.fonts.ready)
          expect(await page.evaluate(() => window.devicePixelRatio)).toBe(2)

          const copies = surface.path === '/'
            ? [null, HEADLINES.B, HEADLINES.C]
            : [null]
          for (const copy of copies) {
            if (copy) {
              await heading.evaluate((element, text) => {
                const emphasis = element.querySelector('.en-hero-emphasis')!
                emphasis.textContent = text.accent
                const group = document.createElement('span')
                group.className = 'en-hero-emphasis-group'
                group.append(emphasis, document.createTextNode(text.post))
                element.replaceChildren(document.createTextNode(text.pre), group)
              }, copy)
            }
            const words = (copy?.accent ?? surface.phrase).split(' ')
            await test.step(copy ? `layout fixture: ${copy.title}` : 'rendered route heading', async () => {
              await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
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
                let after = element.nextSibling
                while (after && (after.nodeType !== Node.TEXT_NODE || !after.textContent?.trim())) after = after.nextSibling
                let punctuation: { left: number; right: number; top: number } | null = null
                if (after?.nodeType === Node.TEXT_NODE && /^[.,:;!?]/.test(after.textContent ?? '')) {
                  const range = document.createRange()
                  range.setStart(after, 0)
                  range.setEnd(after, 1)
                  const rect = range.getBoundingClientRect()
                  punctuation = { left: rect.left, right: rect.right, top: rect.top }
                }
                return {
                  punctuation,
                  words,
                  heading: element.closest('h1,h2')!.getBoundingClientRect().toJSON(),
                  textAlign: getComputedStyle(element.closest('h1,h2')!).textAlign,
                  horizontalPadding: parseFloat(style.paddingLeft) + parseFloat(style.paddingRight),
                  viewport: document.documentElement.clientWidth,
                  fontStyle: style.fontStyle,
                  box: element.getBoundingClientRect().toJSON(),
                  group: element.closest('.en-hero-emphasis-group')?.getBoundingClientRect().toJSON() ?? null,
                }
              })
              expect(layout.words.map((word) => word.word)).toEqual(words)
              expect(layout.fontStyle).toBe('italic')
              expect(layout.punctuation !== null, 'Every phrase with a trailing stop keeps it in the measured group').toBe(Boolean(copy) || surface.path !== '/')
              expect(layout.box.left).toBeGreaterThanOrEqual(0)
              expect(layout.box.right).toBeLessThanOrEqual(layout.viewport)
              for (const word of layout.words) {
                expect(word.rects, `${word.word} must not break inside a word`).toHaveLength(1)
                expect(word.rects[0].left).toBeGreaterThanOrEqual(0)
                expect(word.rects[0].right).toBeLessThanOrEqual(layout.viewport)
                expect(word.rects[0].left, `${word.word} fits inside the fill's left edge`).toBeGreaterThanOrEqual(layout.box.left)
                expect(word.rects[0].right, `${word.word} fits inside the fill's right edge`).toBeLessThanOrEqual(layout.box.right)
              }
              if (layout.group) {
                expect(layout.group.left).toBeGreaterThanOrEqual(0)
                expect(layout.group.right).toBeLessThanOrEqual(layout.viewport)
                if (doubled && (width <= 390 || (surface.path === '/login' && width === 1024))) {
                  // A word and the grouped stop may need more than the narrow column. Give back
                  // only that excess; fitting phrases must retain their column and alignment.
                  const longestWord = Math.max(...layout.words.map((word) => word.rects[0].right - word.rects[0].left))
                  const stopWidth = layout.punctuation!.right - layout.punctuation!.left
                  const minimumFootprint = longestWord + layout.horizontalPadding + stopWidth
                  if (minimumFootprint <= layout.heading.width + 0.25) {
                    expect(layout.group.left, 'A fitting phrase stays inside the headline column').toBeGreaterThanOrEqual(layout.heading.left - 0.25)
                    expect(layout.group.right, 'A fitting phrase stays inside the headline column').toBeLessThanOrEqual(layout.heading.right + 0.25)
                    if (layout.textAlign !== 'center' && new Set(layout.words.map((word) => word.rects[0].top)).size > 1) {
                      expect(Math.abs(layout.group.left - layout.heading.left), 'A fitting wrapped phrase keeps the heading alignment').toBeLessThanOrEqual(0.25)
                    }
                  } else {
                    const leftExcess = layout.heading.left - layout.group.left
                    const rightExcess = layout.group.right - layout.heading.right
                    expect(Math.abs(leftExcess - rightExcess), 'An oversized phrase borrows equally from both gutters').toBeLessThanOrEqual(0.25)
                  }
                  expect(layout.group.left, 'The group keeps a visible viewport inset').toBeGreaterThanOrEqual(4)
                  expect(layout.viewport - layout.group.right, 'The group keeps a visible viewport inset').toBeGreaterThanOrEqual(4)
                }
              }
              if (layout.punctuation) {
                expect(layout.punctuation.top, 'A following stop stays on the phrase’s final line').toBe(layout.words.at(-1)!.rects[0].top)
                expect(layout.punctuation.left, 'A following stop clears the phrase’s final word').toBeGreaterThanOrEqual(layout.words.at(-1)!.rects[0].right)
                expect(layout.punctuation.right).toBeLessThanOrEqual(layout.viewport)
              }
              if (!doubled) {
                expect(new Set(layout.words.map((word) => word.rects[0].top)).size).toBe(1)
              }

              // Word bounds alone miss a wrapped inline block painting over the preceding descender.
              // Compare normal, phrase-ink-off, and fill-off captures. Phrase glyphs (including
              // descenders) need fill behind them; fill must not alter any neighboring ink.
              const background = await heading.evaluate((element) => {
                // The auth pane has its own opaque ground; body would misclassify every pane pixel
                // as neighboring ink. These headings have no translucent/image ground layers.
                for (let node: Element | null = element; node; node = node.parentElement) {
                  const style = getComputedStyle(node)
                  if (style.backgroundImage !== 'none') throw new Error('Heading ground needs image compositing')
                  if (style.backgroundColor.startsWith('rgb(')) return style.backgroundColor
                  if (style.backgroundColor !== 'rgba(0, 0, 0, 0)') throw new Error('Heading ground needs alpha compositing')
                }
                throw new Error('No opaque heading ground')
              })
              expect(background).toMatch(/^rgb\(/)
              const paper = background.match(/\d+/g)!.slice(0, 3).map(Number)
              await heading.evaluate((element) => {
                // Center the whole ink union, including glyphs beyond the h1's CSS box, below
                // the sticky header. Fitting only the h1 can leave a descender outside the shot.
                const range = document.createRange()
                range.selectNodeContents(element)
                const rects = [element.getBoundingClientRect(), ...range.getClientRects()]
                const top = Math.min(...rects.map((rect) => rect.top))
                const bottom = Math.max(...rects.map((rect) => rect.bottom))
                const header = document.querySelector('header')
                const headerBottom = header && getComputedStyle(header).position === 'sticky' ? header.getBoundingClientRect().bottom + 2 : 0
                const targetTop = Math.max(headerBottom, (innerHeight - (bottom - top)) / 2)
                window.scrollTo({ top: scrollY + top - targetTop, behavior: 'instant' })
              })
              const clip = await heading.evaluate((element) => {
                // A min-content phrase may use the heading's gutters at 200%. Include those
                // glyphs and the final stop instead of cropping the diagnostic to the h1 box.
                const range = document.createRange()
                range.selectNodeContents(element)
                const rects = [element.getBoundingClientRect(), ...range.getClientRects()]
                const left = Math.max(0, Math.floor(Math.min(...rects.map((rect) => rect.left))) - 2)
                const right = Math.min(document.documentElement.clientWidth, Math.ceil(Math.max(...rects.map((rect) => rect.right))) + 2)
                const top = Math.max(0, Math.floor(Math.min(...rects.map((rect) => rect.top))) - 2)
                const bottom = Math.ceil(Math.max(...rects.map((rect) => rect.bottom))) + 2
                if (bottom > innerHeight) throw new Error('Heading diagnostic needs a taller viewport')
                return { x: left, y: top, width: right - left, height: bottom - top }
              })
              let painted: Buffer
              let unpainted: Buffer
              const shotScroll = await page.evaluate(() => window.scrollY)
              const shotHeading = await heading.boundingBox()
              const capture = async () => {
                // Full-page capture resets CDP font sizing. These viewport crops include the
                // whole heading and its gutters while preserving actual browser text sizing.
                const shot = await page.screenshot({ animations: 'disabled', clip })
                expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe(doubled ? '32px' : '16px')
                expect(await page.evaluate(() => window.scrollY), 'The paint comparison must not move while scrolling').toBe(shotScroll)
                expect(await heading.evaluate((element, original) => element === original, headingNode)).toBe(true)
                expect(await heading.boundingBox(), 'The paint comparison must preserve heading geometry').toEqual(shotHeading)
                return shot
              }
              const visible = await capture()
              const fillColor = await phrase.evaluate((element) => getComputedStyle(element, '::before').backgroundColor)
              expect(fillColor).toMatch(/^rgb\(/)
              const fill = fillColor.match(/\d+/g)!.slice(0, 3).map(Number)
              const hiddenPhrase = await page.addStyleTag({
                content: '.en-hero-emphasis { color: transparent !important; }',
              })
              try {
                painted = await capture()
                const diagnostic = await page.addStyleTag({
                  content: '.en-hero-emphasis, .en-hero-emphasis::before { background: transparent !important; box-shadow: none !important; }',
                })
                try {
                  unpainted = await capture()
                } finally {
                  await diagnostic.evaluate((element) => element.remove())
                }
              } finally {
                await hiddenPhrase.evaluate((element) => element.remove())
              }
              const pixels = await page.evaluate(async ({ visible, painted, unpainted, paper, fill }) => {
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
                const [withInk, withFill, withoutFill] = await Promise.all([read(visible), read(painted), read(unpainted)])
                if (withFill.width !== withoutFill.width || withFill.height !== withoutFill.height
                  || withInk.width !== withFill.width || withInk.height !== withFill.height) {
                  throw new Error('The paint-only diagnostic changed the headline layout')
                }
                let lostInk = 0
                let paintedPhraseInk = 0
                let phraseInkOutsideFill = 0
                for (let i = 0; i < withoutFill.data.length; i += 4) {
                  if (paper.some((channel, j) => withoutFill.data[i + j] !== channel)
                    && paper.some((_, j) => withFill.data[i + j] !== withoutFill.data[i + j])) lostInk++
                  if (fill.some((_, j) => withInk.data[i + j] !== withFill.data[i + j])) {
                    paintedPhraseInk++
                    if (fill.some((channel, j) => withFill.data[i + j] !== channel)) phraseInkOutsideFill++
                  }
                }
                return { lostInk, paintedPhraseInk, phraseInkOutsideFill }
              }, { visible: visible.toString('base64'), painted: painted!.toString('base64'), unpainted: unpainted!.toString('base64'), paper, fill })
              if (pixels.lostInk || pixels.phraseInkOutsideFill) {
                await test.info().attach('phrase-ink-visible', { body: visible, contentType: 'image/png' })
                await test.info().attach('neighbor-ink-with-fill', { body: painted!, contentType: 'image/png' })
                await test.info().attach('neighbor-ink-without-fill', { body: unpainted!, contentType: 'image/png' })
                await test.info().attach('neighbor-ink-layout', { body: JSON.stringify({ paper, fill, clip, layout, pixels }), contentType: 'application/json' })
              }
              expect(pixels.lostInk, 'The highlight must not cover neighboring heading ink').toBe(0)
              expect(pixels.paintedPhraseInk, 'The phrase must paint visible ink').toBeGreaterThan(0)
              expect(pixels.phraseInkOutsideFill, 'The fill must enclose every painted phrase glyph, including descenders').toBe(0)

              // The face must really load; font-style:italic on the roman face would synthesize a slant.
              await cdp.send('DOM.enable')
              await cdp.send('CSS.enable')
              const document = await cdp.send('DOM.getDocument')
              const node = await cdp.send('DOM.querySelector', { nodeId: document.root.nodeId, selector: `${surface.selector} .en-hero-emphasis` })
              const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId: node.nodeId })
              expect(fonts.some((font) => font.isCustomFont && font.postScriptName === 'Inter-Italic')).toBe(true)
            })
          }
        })
      }
    }
  }
}
