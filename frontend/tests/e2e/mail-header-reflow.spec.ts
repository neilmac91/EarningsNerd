import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { test, expect, type Page } from '@playwright/test'

// The mail header reflows under a phone's text zoom. docs/brand/templates/email-header.html is the header and footer
// line of every mail backend/app/services/email_service.py builds: backend/tests/unit/test_mail_header_template.py
// holds the two to the same markup, cell by cell, and the page around them to the same frame (one <html> and one
// <body> tag, the outer table alone in <body>, a bare row around each of its cells). The tile is measured as the mail
// draws it, the hosted raster the template's note spells, which that test holds the mail's <img> to, in place of the
// preview's SVG, which mail clients drop.
//
// With its text at 200% no painted text or image lies outside the screen, clipped or not: at 320 px, the width a
// phone at Android's largest display size lays a page out at (AOSP keeps its narrow side at 320 dp), and at 390 px, a
// width the site's own reflow rule checks (reflow-200.spec.ts). The wordmark may wrap between its two words, at a
// zero-width space, and nowhere else (D-048): at 200% it reads "Earnings" over "Nerd", and at its set size it is one
// line. The tagline's mark keeps its three words and full stop on one line wherever they fit, at its set size and at
// 390 px under 200%, and wraps inside itself, between its words alone, where they do not, its tint following them, a
// fragment under each line. Nothing on either lets a word split (overflow-wrap, word-break, line-break, hyphens). The
// tile stays beside the wordmark: left of its painted lines, its middle level with them. Each is measured in painted
// text with a Range (lessons/frontend-check-brand-layouts-at-200-percent-text.md). At 320 px and the default size the
// page fits too. Unchecked here: the mail's panel and the body it holds (a long word in a body widens the column the
// header shares; E112), other widths and zooms (a 360 px screen holding to 230% is a measurement, not a check),
// WebKit, which an iPhone's mail apps draw with, and any real mail client.
//
// A text zoom, which an Android WebView sets from the phone's font size unless its mail app sets its own, scales
// every font size and line-height on the page, however each is written, and nothing else: the tile, the padding and
// the gutters keep theirs. The browser's text setting, which reflow-200 doubles (Page.setFontSizes), moves no px
// size, so here each element's computed size is written back doubled, as such a zoom doubles it. The template styles
// nothing but its font faces, each the repository's Inter as it is, upright and italic, drawn with its optical sizes
// off: Inter's display cut narrows large text, and the text cut is the wider measure. The mail sends no font, so a
// phone draws it in its own sans-serif.
//
// The lockup is the tile beside a one-word wordmark, and the tagline's mark kept its three words on one
// line, so the page measured about 420 px at 200%, whatever the screen's width below that. With the
// wordmark's break, and the mark an inline-block that wraps inside itself only where its words do not fit,
// the page needs 315 to 316 px at 200% (Chromium 156 and 141, the font pinned), so 320 px fits it from
// both, and a 360 px screen holds to 230%.

const TEMPLATE = path.resolve(__dirname, '../../../docs/brand/templates/email-header.html')
// The mail's tile, as the template's note spells it and test_mail_header_template.py holds the mail's to it, on the files
// the site serves.
const TILE = /<img src="\{base\}[^>]*>/.exec(fs.readFileSync(TEMPLATE, 'utf8'))?.[0]
const PUBLIC = pathToFileURL(path.resolve(__dirname, '../../public')).href
const WORDMARK = /^Earnings\u200b?Nerd$/
const TAGLINE = /^The summary that shows its work\.$/
const MARK = 'shows its work.'
// Each face draws the repository's Inter as it is: its family, style, weight range and file, and nothing that changes
// its measure (a size-adjust, a metric override, a unicode-range, a feature setting).
const FACES = [
  { declared: 'font-family font-style font-weight src', style: 'italic', weight: '100 900', file: 'Inter-Variable-Italic-latin.woff2' },
  { declared: 'font-family font-style font-weight src', style: 'normal', weight: '100 900', file: 'Inter-Variable-latin.woff2' },
]
// What lets a word split, at its initial value on the wordmark and the tagline, each element of their cells.
const NO_SPLIT = 'normal normal auto manual' // overflow-wrap, word-break, line-break, hyphens

// Where the mark fits a line it must be one line: at 320 px and 200% its 268 px do not fit the 232 px its cell
// leaves, and it wraps inside itself.
const CASES = [
  { width: 320, zoom: 1, lines: ['EarningsNerd'], markFits: true },
  { width: 320, zoom: 2, lines: ['Earnings', 'Nerd'], markFits: false },
  { width: 390, zoom: 2, lines: ['Earnings', 'Nerd'], markFits: true },
]

interface Line {
  text: string
  top: number
  bottom: number
  left: number
  right: number
}

/** A phrase's painted lines, in reading order, in the innermost cell that holds it: each line's ink, character by
 * character (a space and the zero-width space paint nothing), and the box its characters span. Empty when no cell
 * holds the phrase. */
function paintedLines(page: Page, phrase: string): Promise<Line[]> {
  return page.evaluate((phrase) => {
    const ink = (c: string) => c !== '\u200b' && c.trim() !== ''
    const wanted = [...phrase].filter(ink).join('')
    for (const cell of document.querySelectorAll('td')) {
      if (cell.querySelector('td')) continue
      const chars: { node: Text; i: number }[] = []
      const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
        for (let i = 0; i < node.data.length; i++) if (ink(node.data[i])) chars.push({ node, i })
      }
      const at = chars.map(({ node, i }) => node.data[i]).join('').indexOf(wanted)
      if (at < 0) continue
      const lines: Line[] = []
      for (const { node, i } of chars.slice(at, at + wanted.length)) {
        const range = document.createRange()
        range.setStart(node, i)
        range.setEnd(node, i + 1)
        const { top, bottom, left, right } = range.getBoundingClientRect()
        const last = lines[lines.length - 1]
        if (last && Math.abs(top - last.top) <= 4) {
          Object.assign(last, { text: last.text + node.data[i], bottom: Math.max(last.bottom, bottom), left: Math.min(last.left, left), right: Math.max(last.right, right) })
        } else lines.push({ text: node.data[i], top, bottom, left, right })
      }
      return lines
    }
    return []
  }, phrase)
}

const texts = (lines: Line[]) => lines.map((line) => line.text)

/** Whether painted lines break a phrase between its words alone: each line one or more of its words, whole. */
function betweenWords(lines: string[], phrase: string): boolean {
  const words = phrase.split(' ')
  let next = 0
  for (const line of lines) {
    let ink = ''
    while (next < words.length && ink.length < line.length) ink += words[next++]
    if (ink !== line) return false
  }
  return next === words.length
}

for (const { width, zoom, lines, markFits } of CASES) {
  test.describe(`at ${width} px with the text at ${zoom * 100}%`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 })

    test(`the mail header fits a ${width} px screen with its text at ${zoom * 100}%`, async ({ page }) => {
      await page.goto(pathToFileURL(TEMPLATE).href)
      const sheets = await page.evaluate(() => {
        const rules = [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules])
        return {
          other: rules.filter((rule) => !(rule instanceof CSSFontFaceRule)).map((rule) => rule.cssText),
          faces: rules.flatMap((rule) => (rule instanceof CSSFontFaceRule ? [rule.style] : [])).map((face) => ({
            declared: [...face].sort().join(' '),
            family: face.getPropertyValue('font-family').replace(/["']/g, ''),
            style: face.getPropertyValue('font-style'),
            weight: face.getPropertyValue('font-weight'),
            file: /url\(["']?\.\.\/\.\.\/\.\.\/frontend\/scripts\/brand\/fonts\/([^"')]+)["']?\)/.exec(face.getPropertyValue('src'))?.[1],
          })),
        }
      })
      expect(sheets.other, 'the template styles more than its font faces, which the mail has no way to carry').toEqual([])
      expect(
        sheets.faces.sort((a, b) => a.style.localeCompare(b.style)),
        "the template's faces are not the repository's Inter as it is, each its file, style and weight range alone",
      ).toEqual(FACES.map((face) => ({ ...face, family: 'Inter' })))
      await page.addStyleTag({ content: '* { font-optical-sizing: none !important; }' })
      // Measured in the repository's Inter, upright and italic, or the width is a fallback font's.
      await page.evaluate(() => Promise.all([document.fonts.load('700 22px Inter'), document.fonts.load('italic 700 22px Inter')]))
      const faces = await page.evaluate(() =>
        [...document.fonts].filter((face) => face.family.replace(/["']/g, '') === 'Inter').map((face) => `${face.style} ${face.status}`),
      )
      expect(faces.sort(), "the template's @font-face rules no longer load the repository's Inter").toEqual(['italic loaded', 'normal loaded'])

      // The tile as the mail draws it: the note's <img>, the whole of its cell, in place of the preview's SVG.
      expect(TILE, "the template's note no longer spells the mail's tile").toBeDefined()
      await expect(page.locator('svg'), 'the template no longer draws its tile as one SVG').toHaveCount(1)
      await page.locator('svg').evaluate((svg, img) => (svg.parentElement!.innerHTML = img), TILE!.replace('{base}', PUBLIC))
      const tile = page.locator('img')
      await tile.evaluate((img: HTMLImageElement) => img.decode())

      const wordmark = page.locator('td', { hasText: WORDMARK })
      const tagline = page.locator('td', { hasText: TAGLINE })
      await expect(wordmark, 'the template no longer holds the wordmark').toHaveCount(1)
      await expect(tagline, 'the template no longer holds the tagline').toHaveCount(1)
      for (const [name, cell] of [['wordmark', wordmark], ['tagline', tagline]] as const) {
        const split = await cell.evaluate((cell) =>
          [cell, ...cell.querySelectorAll('*')].map((element) => {
            const style = getComputedStyle(element)
            return [style.overflowWrap, style.wordBreak, style.lineBreak, style.hyphens].join(' ')
          }),
        )
        expect([...new Set(split)], `something lets the ${name} split a word`).toEqual([NO_SPLIT])
      }
      expect(texts(await paintedLines(page, 'EarningsNerd')), 'the wordmark is not one line at its set size').toEqual(['EarningsNerd'])
      expect(texts(await paintedLines(page, MARK)), "the tagline's mark is not one line at its set size").toHaveLength(1)

      if (zoom !== 1) {
        await page.evaluate((factor) => {
          const sizes = [...document.querySelectorAll<HTMLElement>('body, body *')].map((element) => {
            const style = getComputedStyle(element)
            return [element, parseFloat(style.fontSize), style.lineHeight] as const
          })
          for (const [element, size, lineHeight] of sizes) {
            element.style.setProperty('font-size', `${size * factor}px`, 'important')
            if (lineHeight.endsWith('px')) element.style.setProperty('line-height', `${parseFloat(lineHeight) * factor}px`, 'important')
          }
        }, zoom)
      }
      expect(await wordmark.evaluate((cell) => getComputedStyle(cell).fontSize), 'the zoom did not reach the wordmark').toBe(`${22 * zoom}px`)

      const { scrolled, outside } = await page.evaluate((screen) => {
        const outside: { text: string; left: number; right: number }[] = []
        const off = (left: number, right: number) => left < -0.5 || right > screen + 0.5
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          const text = (node.textContent ?? '').replace(/\s+/g, ' ').trim()
          if (!text) continue
          const range = document.createRange()
          range.selectNodeContents(node)
          const rects = [...range.getClientRects()].filter((rect) => rect.width > 0)
          const left = Math.min(Infinity, ...rects.map((rect) => rect.left))
          const right = Math.max(-Infinity, ...rects.map((rect) => rect.right))
          if (off(left, right)) outside.push({ text: text.slice(0, 40), left: Math.round(left), right: Math.round(right) })
        }
        for (const image of document.body.querySelectorAll('img, svg')) {
          const { left, right } = image.getBoundingClientRect()
          if (off(left, right)) outside.push({ text: `<${image.tagName.toLowerCase()}>`, left: Math.round(left), right: Math.round(right) })
        }
        return { scrolled: document.documentElement.scrollWidth, outside }
      }, width)
      expect(outside, `painted text or an image lies outside the ${width} px screen, clipped or not`).toEqual([])
      expect(scrolled, `the header scrolls sideways at ${width} px with its text at ${zoom * 100}%`).toBeLessThanOrEqual(width)

      const words = await paintedLines(page, 'EarningsNerd')
      expect(texts(words), 'the wordmark breaks other than between its two words').toEqual(lines)
      const mark = await paintedLines(page, MARK)
      expect(texts(mark).join(''), "the template no longer holds the tagline's mark").toBe('showsitswork.')
      expect(betweenWords(texts(mark), MARK), `the tagline's mark breaks other than between its words: ${JSON.stringify(texts(mark))}`).toBe(true)
      if (markFits) expect(texts(mark), "the tagline's mark wraps where its line fits it").toHaveLength(1)
      // The mark's tint follows its words: a fragment on each of their lines, under them.
      const tint = await tagline.evaluate((cell) =>
        [...cell.querySelectorAll('*')]
          .filter((element) => getComputedStyle(element).backgroundColor !== 'rgba(0, 0, 0, 0)')
          .map((element) => [...element.getClientRects()].map(({ top, bottom, left, right }) => ({ top, bottom, left, right }))),
      )
      expect(tint, "the tagline's mark has no tint, or more than one").toHaveLength(1)
      expect(
        tint[0].length === mark.length &&
          tint[0].every((rect, i) => {
            const middle = (rect.top + rect.bottom) / 2
            return middle >= mark[i].top && middle <= mark[i].bottom && rect.left < mark[i].right && rect.right > mark[i].left
          }),
        `the mark's tint does not follow its words line by line: tint ${JSON.stringify(tint[0])}, lines ${JSON.stringify(mark)}`,
      ).toBe(true)
      // The lockup stays the tile beside the wordmark: left of its painted lines, its middle level with them.
      const box = await tile.boundingBox()
      const middle = box === null ? NaN : box.y + box.height / 2
      expect(
        box !== null && box.x + box.width <= Math.min(...words.map((line) => line.left)) + 0.5 && middle >= words[0].top && middle <= words[words.length - 1].bottom,
        `the tile no longer sits beside the wordmark: tile ${JSON.stringify(box)}, wordmark ${JSON.stringify(words)}`,
      ).toBe(true)
    })
  })
}
