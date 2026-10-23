#!/usr/bin/env node
/* =============================================================================
   capture-company-marks.mjs — the both-themes check for company marks (rule 11)
   -----------------------------------------------------------------------------
   Opens a running site, finds every company mark (components/CompanyLogo.tsx marks its slot
   with data-company-mark), crops each at native pixels in both themes at DPR 1, 2 and 3, and
   writes one contact sheet per theme and DPR, the crops enlarged 3x with no smoothing, so a
   clipped tile, a dark mark on a dark ground or a monogram where a logo was expected is seen
   in one glance. Reads only; signs in to nothing; the dashboard needs a session, so it is not
   a default route.

     node scripts/capture-company-marks.mjs <base url> [out dir] [routes]
     node scripts/capture-company-marks.mjs https://www.earningsnerd.io
     node scripts/capture-company-marks.mjs http://localhost:3000 /tmp/marks "/,/company/NFLX"

   Routes default to the landing, a company page and the calendar (the calendar route 404s
   while NEXT_PUBLIC_ENABLE_CALENDAR is off; it is skipped then). Output, in a fresh folder under
   the OS temp directory unless an out dir is given (never inside the repo):
     <out>/<theme>-dpr<n>-<route>-<i>-<ticker>.png   one crop per mark, native pixels + 6px
     <out>/sheet-<theme>-dpr<n>.png                   the sheet, read it for the done-gate
   Exits 1 when it finds no mark at all (a renamed hook or a page without marks is a finding,
   not a pass). Uses the project's Playwright Chromium (`npx playwright install chromium` once),
   or the binary named by PLAYWRIGHT_CHROMIUM_PATH. A Vercel preview sits behind deployment
   protection (an SSO redirect, which reads as a page with no marks): pass the project's
   "Protection Bypass for Automation" secret as VERCEL_PROTECTION_BYPASS and the script sends it
   with every request (`x-vercel-protection-bypass`).

   Proportion: this is a release check, run once against a preview after a change to the marks,
   not a monitor. Each run loads the routes six times (two themes, three pixel ratios) in a real
   browser with the site's own publishable key; Logo.dev's fair-use page asks that its CDN be
   loaded by browsers for display and not fetched by scripts, so keep it to that.
============================================================================= */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { chromium } from '@playwright/test'

const [, , base, outArg, routesArg] = process.argv
if (!base) {
  console.error('usage: node scripts/capture-company-marks.mjs <base url> [out dir] [routes]')
  process.exit(2)
}
const outDir = outArg || fs.mkdtempSync(path.join(os.tmpdir(), 'company-marks-'))
const routes = (routesArg || '/,/company/AAPL,/calendar').split(',').map((r) => r.trim()).filter(Boolean)
const THEMES = ['light', 'dark']
const SCREENS = [
  { name: 'dpr1', viewport: { width: 1280, height: 900 }, dpr: 1 },
  { name: 'dpr2', viewport: { width: 1280, height: 900 }, dpr: 2 },
  { name: 'dpr3', viewport: { width: 390, height: 844 }, dpr: 3, mobile: true },
]
const SLOT = '[data-company-mark]'
fs.mkdirSync(outDir, { recursive: true })

const slug = (route) => (route === '/' ? 'landing' : route.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, ''))

/** A mark has settled when its image loaded (opacity 1) or failed (removed), or it has no image. */
const isSettled = (el) => {
  const img = el.querySelector('img')
  return !img || (img.complete && (img.naturalWidth === 0 || getComputedStyle(img).opacity === '1'))
}

async function captureRoute(page, route, tag) {
  let response
  try {
    response = await page.goto(new URL(route, base).href, { waitUntil: 'networkidle', timeout: 120_000 })
  } catch (error) {
    console.log(`${tag}: ${route} did not load (${String(error).split('\n')[0]}), skipped`)
    return []
  }
  if (!response || response.status() >= 400) {
    console.log(`${tag}: ${route} answered ${response ? response.status() : 'nothing'}, skipped`)
    return []
  }
  // The consent banner is fixed chrome; answer it on the first page so it never sits over a mark.
  const decline = page.getByRole('button', { name: /essential only|necessary only|decline|reject/i })
  if (await decline.count()) await decline.first().click({ timeout: 5_000 }).catch(() => {})
  // Lazy marks load as they scroll in: walk the page once so every mark has been near the viewport.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 500) {
      window.scrollTo(0, y)
      await new Promise((r) => setTimeout(r, 120))
    }
  })
  const crops = []
  let i = 0
  for (const slot of await page.$$(SLOT)) {
    const box = await slot.boundingBox()
    if (!box || box.width === 0) continue
    const ticker = (await slot.getAttribute('data-company-mark')) || 'monogram'
    // Centred, so neither fixed chrome nor a dev overlay in a corner sits over the crop; then this mark's
    // own load and 200ms crossfade are given a moment to finish.
    await slot.evaluate((el) => el.scrollIntoView({ block: 'center', inline: 'center' }))
    try {
      await slot.waitForElementState('stable', { timeout: 2_000 })
      await page.waitForFunction(isSettled, slot, { timeout: 5_000 })
    } catch {
      console.log(`${tag}: ${route} ${ticker} had not settled after 5s (cropped as it was)`)
    }
    await page.waitForTimeout(250)
    const r = await slot.boundingBox()
    const pad = 6
    const file = path.join(outDir, `${tag}-${slug(route)}-${String(i).padStart(2, '0')}-${ticker}.png`)
    const viewport = page.viewportSize()
    const clip = { x: Math.max(0, r.x - pad), y: Math.max(0, r.y - pad), width: r.width + pad * 2, height: r.height + pad * 2 }
    const inside = viewport && clip.x + clip.width <= viewport.width && clip.y + clip.height <= viewport.height && r.x >= 0 && r.y >= 0
    if (inside) await page.screenshot({ path: file, clip })
    else await slot.screenshot({ path: file }) // a mark a scroll container keeps off-screen: the element alone
    crops.push({ file, label: `${ticker} ${Math.round(r.width)}px ${slug(route)}` })
    i += 1
  }
  console.log(`${tag}: ${route} ${crops.length} marks`)
  return crops
}

/** One sheet per theme and DPR: every crop at 3x with no smoothing, labelled, screenshotted by the same browser. */
async function writeSheet(browser, crops, file, title) {
  const cells = crops
    .map(({ file: f, label }) => {
      const data = fs.readFileSync(f).toString('base64')
      return `<figure><img src="data:image/png;base64,${data}" alt=""><figcaption>${label}</figcaption></figure>`
    })
    .join('')
  const html = `<!doctype html><meta charset="utf-8"><title>${title}</title><style>
    body{margin:0;padding:16px;background:#808080;font:12px system-ui;color:#fff}
    h1{font-size:14px;margin:0 0 12px}
    main{display:flex;flex-wrap:wrap;gap:12px}
    figure{margin:0;display:flex;flex-direction:column;gap:4px}
    img{image-rendering:pixelated;display:block}
    figcaption{max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  </style><h1>${title}</h1><main>${cells}</main>
  <script>
    const enlarge = (i) => { i.width = i.naturalWidth * 3; i.height = i.naturalHeight * 3 }
    for (const i of document.images) { if (i.complete && i.naturalWidth > 0) enlarge(i); else i.onload = () => enlarge(i) }
  </script>`
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 })
  await page.setContent(html, { waitUntil: 'load' })
  await page.waitForTimeout(200)
  await page.screenshot({ path: file, fullPage: true })
  await page.close()
}

const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
)
let total = 0
try {
  for (const theme of THEMES) {
    for (const screen of SCREENS) {
      const tag = `${theme}-${screen.name}`
      const context = await browser.newContext({
        viewport: screen.viewport,
        deviceScaleFactor: screen.dpr,
        isMobile: Boolean(screen.mobile),
        colorScheme: theme,
        ...(process.env.VERCEL_PROTECTION_BYPASS
          ? { extraHTTPHeaders: { 'x-vercel-protection-bypass': process.env.VERCEL_PROTECTION_BYPASS, 'x-vercel-set-bypass-cookie': 'true' } }
          : {}),
      })
      // The app reads its theme from localStorage (no system-preference detection).
      await context.addInitScript((t) => localStorage.setItem('theme', t), theme)
      const page = await context.newPage()
      const crops = []
      for (const route of routes) crops.push(...(await captureRoute(page, route, tag)))
      total += crops.length
      if (crops.length) await writeSheet(browser, crops, path.join(outDir, `sheet-${tag}.png`), `Company marks, ${theme} theme, DPR ${screen.dpr}, ${base}`)
      await context.close()
    }
  }
} finally {
  await browser.close()
}
if (total === 0) {
  console.error(`no company mark found on ${routes.join(', ')} at ${base}: nothing to check (is the [data-company-mark] hook on the slot?)`)
  process.exit(1)
}
console.log(`${total} crops and ${THEMES.length * SCREENS.length} sheets in ${outDir}`)
