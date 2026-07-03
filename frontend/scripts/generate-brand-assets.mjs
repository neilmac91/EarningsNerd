#!/usr/bin/env node
/* =============================================================================
   generate-brand-assets.mjs — regenerates the committed binary brand assets
   -----------------------------------------------------------------------------
   Source of truth: public/assets/earningsnerd-*.svg (the sage monogram set).
   Outputs (all COMMITTED — rerun only on a brand change, then commit the diff):
     public/favicon.ico              16/32/48 from the appicon tile
     public/apple-touch-icon.png     180×180 FULL-BLEED sage tile (Apple applies
                                     its own corner mask — pre-rounded corners
                                     leave halo artifacts)
     public/icons/icon-192.png       appicon as-is (purpose "any")
     public/icons/icon-512.png
     public/icons/icon-maskable-192.png  full-bleed tile, mark scaled 0.62 so it
     public/icons/icon-maskable-512.png  fits the r=40% maskable safe zone
     public/og-image.png             1200×630 social card (Playwright render of
                                     scripts/brand/og-template.html at 2× then
                                     downscaled; committed Inter woff2 keeps the
                                     render deterministic on any machine)

   Run: npm run brand:assets
   Requires devDeps sharp + png-to-ico + playwright. If playwright's managed
   chromium isn't installed (e.g. CI containers with a system chromium), set
   BRAND_CHROMIUM=/path/to/chrome.
============================================================================= */
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import sharp from 'sharp'
import pngToIco from 'png-to-ico'
import { chromium } from 'playwright'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..') // frontend/
const pub = path.join(root, 'public')
const assets = path.join(pub, 'assets')
const icons = path.join(pub, 'icons')

const SAGE = '#4F7A63'
const CREAM = '#F4F3EE'
const MARK_RATIO = 73.2 / 94.6 // mark height / width

const appiconSvg = path.join(assets, 'earningsnerd-appicon.svg')

/** The mark geometry recolored — built from the mono rendition. */
async function markSvg(fill) {
  const mono = await fs.readFile(path.join(assets, 'earningsnerd-mark-mono.svg'), 'utf8')
  return Buffer.from(mono.replaceAll('currentColor', fill))
}

/** Full-bleed sage square with the cream mark centered at `scale` of the edge. */
async function fullBleedTile(size, scale) {
  const markW = Math.round(size * scale)
  const markH = Math.round(markW * MARK_RATIO)
  // density matters: without it sharp rasterizes at the 94.6px viewBox size and
  // upscales (blurry at the 317px mark inside the 512 maskable tile).
  const mark = await sharp(await markSvg(CREAM), { density: 300 }).resize(markW, markH).png().toBuffer()
  return sharp({ create: { width: size, height: size, channels: 4, background: SAGE } })
    .composite([{ input: mark, gravity: 'center' }])
    .png()
    .toBuffer()
}

async function main() {
  await fs.mkdir(icons, { recursive: true })

  // favicon.ico — classic multi-size from the appicon tile
  const faviconPngs = await Promise.all(
    [16, 32, 48].map((s) => sharp(appiconSvg, { density: 300 }).resize(s, s).png().toBuffer()),
  )
  await fs.writeFile(path.join(pub, 'favicon.ico'), await pngToIco(faviconPngs))
  console.log('✓ favicon.ico (16/32/48)')

  // apple-touch-icon — full-bleed, no alpha, mark at 0.68
  await fs.writeFile(
    path.join(pub, 'apple-touch-icon.png'),
    await sharp(await fullBleedTile(180, 0.68)).flatten({ background: SAGE }).png().toBuffer(),
  )
  console.log('✓ apple-touch-icon.png (180, full-bleed)')

  // PWA icons — appicon as-is for "any", full-bleed 0.62 for "maskable"
  for (const s of [192, 512]) {
    await fs.writeFile(
      path.join(icons, `icon-${s}.png`),
      await sharp(appiconSvg, { density: 300 }).resize(s, s).png().toBuffer(),
    )
    await fs.writeFile(path.join(icons, `icon-maskable-${s}.png`), await fullBleedTile(s, 0.62))
  }
  console.log('✓ icons/icon-{192,512}.png + maskable variants')

  // og-image — deterministic Playwright render of the committed template
  const browser = await chromium.launch(
    process.env.BRAND_CHROMIUM ? { executablePath: process.env.BRAND_CHROMIUM } : {},
  )
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 2 })
  await page.goto(pathToFileURL(path.join(here, 'brand', 'og-template.html')).href)
  await page.evaluate(() => document.fonts.ready)
  const shot = await page.screenshot({ type: 'png' })
  await browser.close()
  await fs.writeFile(path.join(pub, 'og-image.png'), await sharp(shot).resize(1200, 630).png().toBuffer())
  console.log('✓ og-image.png (1200×630)')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
