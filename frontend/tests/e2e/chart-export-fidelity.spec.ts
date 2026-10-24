import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { openAnalysis, type AnalysisTheme } from './fixtures/analysisLayoutApi'

/**
 * The downloaded chart PNG paints the plot the reader saw. The export rasterizes the plot's SVG as an
 * isolated image, which the page's webfonts never reach on their own, so the axis and label text used
 * to paint in the platform monospace (1.5–1.7% of the plot's pixels differed from the screen).
 * chartExport now carries the Geist Mono faces into that image. This gate takes each panel's plot
 * region out of the PNG the real export downloads and compares it with an element screenshot of the
 * on-screen SVG, both at the export's 2× scale. The plot region is where the export drew the SVG image,
 * read from a drawImage hook, so a header or footer change moves it without failing the gate.
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

test.describe.configure({ mode: 'parallel' })

for (const theme of THEMES) {
  test.describe(`chart PNG export / ${theme}`, () => {
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
      await openAnalysis(page, baseURL!, 'captured', theme)
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
