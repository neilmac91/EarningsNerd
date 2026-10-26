import { readFileSync } from 'node:fs'
import { crc32 } from 'node:zlib'
import { expect, test } from '@playwright/test'
import type { AnalysisDataset } from '../../features/analysis/api/analysis-api'
import { openAnalysis, type AnalysisGeometryState, type AnalysisTheme } from './fixtures/analysisLayoutApi'

/**
 * The downloaded chart PNG paints the plot the reader saw. The export rasterizes the plot's SVG as an
 * isolated image, which the page's webfonts never reach on their own, so the axis and label text used
 * to paint in the platform monospace (1.5–1.7% of the plot's pixels differed from the screen).
 * chartExport now carries the Geist Mono faces into that image. This gate takes each panel's plot
 * region out of the PNG the real export downloads and compares it with an element screenshot of the
 * on-screen SVG, both at the export's 2× scale. The plot region is where the export drew the SVG image,
 * read from a drawImage hook, so a header or footer change moves it without failing the gate. It also reads the
 * downloaded file's pHYs chunk: the export declares 144 dpi without changing that scale.
 */
const THEMES: AnalysisTheme[] = ['light', 'dark']
const SCALE = 2
/** A channel difference above this is a different pixel; smaller ones are antialiasing noise. */
const CHANNEL_TOLERANCE = 25
/** The share of a plot's pixels that may differ. Measured on one machine: with the fallback font
 *  1.5–1.7% did; with the faces embedded the worst panel had 0.011%. Chromium only, the browser CI runs. */
const MAX_DIFFERING = 0.001

declare global {
  interface Window {
    __plotDraws: number[][]
  }
}

/** The PNG's chunks in file order, each with its type, its data and whether its CRC-32 is right. */
function pngChunks(png: Buffer): Array<{ type: string; data: Buffer; crcMatches: boolean }> {
  const chunks: Array<{ type: string; data: Buffer; crcMatches: boolean }> = []
  for (let offset = 8; offset + 12 <= png.length;) {
    const length = png.readUInt32BE(offset)
    chunks.push({
      type: png.toString('latin1', offset + 4, offset + 8),
      data: png.subarray(offset + 8, offset + 8 + length),
      crcMatches: png.readUInt32BE(offset + 8 + length) === crc32(png.subarray(offset + 4, offset + 8 + length)),
    })
    offset += 12 + length
  }
  return chunks
}

// The screen may draw text with LCD subpixel antialiasing (CI's headless shell does), which text rasterized
// into an image never has: an SVG image and a canvas antialias in grayscale. The PNG cannot carry it, so the
// gate compares the fonts with LCD text off: in grayscale both, the same glyphs match and a fallback face does
// not. With it on, every glyph edge differed (1.6–1.7% of a plot's pixels) though both drew Geist Mono.
test.use({ launchOptions: { args: ['--disable-lcd-text'] } })

/** Every amount in Swiss francs: the tick labels then carry a no-break space ("CHF\u00a020B"), which the faces must cover. */
const inSwissFrancs = (dataset: AnalysisDataset) => {
  for (const series of dataset.series) if (!series.percent) {
    series.unit = 'CHF'
    for (const point of series.points) point.unit = 'CHF'
  }
}
const CASES: Array<[string, AnalysisGeometryState, ((dataset: AnalysisDataset) => void) | undefined]> = [
  ['quarterly', 'captured', undefined],
  ['annual in CHF', 'annual', inSwissFrancs],
]

test.describe.configure({ mode: 'parallel' })

for (const theme of THEMES) for (const [name, state, edit] of CASES) {
  test.describe(`chart PNG export / ${theme} / ${name}`, () => {
    test.use({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: SCALE, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test('paints each plot in the fonts the screen shows', async ({ page, baseURL }, testInfo) => {
      test.setTimeout(90_000)
      await page.addInitScript(() => {
        // Record where the export draws each plot image; the footer's EN mark is the one other SVG image.
        window.__plotDraws = []
        const draw = CanvasRenderingContext2D.prototype.drawImage
        CanvasRenderingContext2D.prototype.drawImage = function (this: CanvasRenderingContext2D, ...args: unknown[]) {
          const [image, ...geometry] = args
          if (image instanceof HTMLImageElement && image.src.startsWith('data:image/svg+xml')
            && !decodeURIComponent(image.src).includes('viewBox="0 0 94.6 73.2"')) window.__plotDraws.push(geometry as number[])
          return (draw as (...rest: unknown[]) => void).apply(this, args)
        }
      })
      await openAnalysis(page, baseURL!, state, theme, 1, false, edit)
      const plots = page.locator('[data-analysis-chart]')
      await expect(plots).toHaveCount(4)
      const buttons = page.getByRole('button', { name: 'Download chart as PNG', exact: true })
      await expect(buttons).toHaveCount(4)

      for (let index = 0; index < 4; index++) {
        const plot = plots.nth(index)
        const name = await plot.getAttribute('data-analysis-chart')
        await plot.scrollIntoViewIfNeeded()
        await page.mouse.move(0, 0) // no hover state on either picture
        const screen = await plot.locator('svg').first().screenshot({ animations: 'disabled' })
        const [download] = await Promise.all([page.waitForEvent('download'), buttons.nth(index).click()])
        await page.mouse.move(0, 0)
        const exported = readFileSync((await download.path())!)
        const draws = await page.evaluate(() => window.__plotDraws.splice(0))
        expect(draws, `${name}: the export draws its plot once`).toHaveLength(1)
        // The file declares 144 dpi (5669 pixels a metre, unit 1) once, right after its header, so a document prints
        // the 2× raster at 1 CSS px a point; the raster's scale is the one compared below.
        const chunks = pngChunks(exported)
        expect(chunks.map((chunk) => chunk.type).slice(0, 2), `${name}: pHYs follows IHDR`).toEqual(['IHDR', 'pHYs'])
        expect(chunks.filter((chunk) => chunk.type === 'pHYs'), `${name}: one pHYs`).toHaveLength(1)
        expect(chunks.every((chunk) => chunk.crcMatches), `${name}: every chunk's CRC`).toBe(true)
        const pHYs = chunks[1].data
        expect([pHYs.readUInt32BE(0), pHYs.readUInt32BE(4), pHYs[8]], `${name}: 144 dpi`).toEqual([5669, 5669, 1])

        const result = await page.evaluate(async ({ exported, screen, draw, scale, tolerance }) => {
          const load = (base64: string) => new Promise<HTMLImageElement>((resolve, reject) => {
            const image = new Image()
            image.onload = () => resolve(image)
            image.onerror = () => reject(new Error('undecodable PNG'))
            image.src = `data:image/png;base64,${base64}`
          })
          const [png, shot] = await Promise.all([load(exported), load(screen)])
          const [x, y, w, h] = draw.map((value) => Math.round(value * scale))
          const pixels = (image: HTMLImageElement, sx: number, sy: number) => {
            const canvas = document.createElement('canvas')
            canvas.width = w
            canvas.height = h
            const context = canvas.getContext('2d')!
            context.drawImage(image, sx, sy, w, h, 0, 0, w, h)
            return context.getImageData(0, 0, w, h).data
          }
          const a = pixels(png, x, y)
          const b = pixels(shot, 0, 0)
          let differing = 0
          let inked = 0
          for (let i = 0; i < a.length; i += 4) {
            const delta = Math.max(Math.abs(a[i] - b[i]), Math.abs(a[i + 1] - b[i + 1]), Math.abs(a[i + 2] - b[i + 2]))
            if (delta > tolerance) differing++
            // Pixels unlike the top-left one (the panel ground): the plot is really drawn.
            if (Math.max(Math.abs(b[i] - b[0]), Math.abs(b[i + 1] - b[1]), Math.abs(b[i + 2] - b[2])) > tolerance) inked++
          }
          return { size: [w, h], shot: [shot.naturalWidth, shot.naturalHeight], differing: differing / (w * h), inked: inked / (w * h) }
        }, { exported: exported.toString('base64'), screen: screen.toString('base64'), draw: draws[0], scale: SCALE, tolerance: CHANNEL_TOLERANCE })

        if (result.differing > MAX_DIFFERING) {
          await testInfo.attach(`${name} screen`, { body: screen, contentType: 'image/png' })
          await testInfo.attach(`${name} export`, { body: exported, contentType: 'image/png' })
        }
        expect(result.size, `${name}: the export draws the plot at the size it has on screen`).toEqual(result.shot)
        expect(result.inked, `${name}: the screenshot shows a drawn plot`).toBeGreaterThan(0.01)
        expect(result.differing, `${name}: share of plot pixels unlike the screen`).toBeLessThanOrEqual(MAX_DIFFERING)
      }
    })
  })
}
