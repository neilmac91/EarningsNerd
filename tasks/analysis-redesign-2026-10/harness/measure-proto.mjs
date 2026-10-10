// Measures the PROTOTYPE (prototype/index.html) in every state, in the proposed view and in the
// reproduction of today's markup, at the brief's widths, both themes, 200% browser zoom and 200%
// text size: page overflow, KPI card-child containment and value alignment, table width and
// column widths, far-right sticky-column occlusion, clipped cells and the count of repeated labels.
//
//   node harness/measure-proto.mjs --out measurements/prototype.json [--fonts dir] [--shots dir]
//
// Run from tasks/analysis-redesign-2026-10/. With --fonts, Google Fonts requests are answered from a
// local directory holding the CSS as fonts.css plus the .woff2 files it names (no network needed).
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) => (a.startsWith('--') ? [a.slice(2), all[i + 1]] : [])).filter((x) => x.length))
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const OUT = path.resolve(ROOT, args.out || 'measurements/prototype.json')
const FONTS = args.fonts || null
const SHOTS = args.shots || null
const PROTO_URL = pathToFileURL(path.join(ROOT, 'prototype/index.html')).href

const CONFIGS = [
  { name: '1480', width: 1480, height: 1000 },
  { name: '1054', width: 1054, height: 1000 },
  { name: '1024', width: 1024, height: 1000 },
  { name: '768', width: 768, height: 1024 },
  { name: '390', width: 390, height: 844, mobile: true },
  { name: '320', width: 320, height: 568, mobile: true },
  { name: '1480@200%zoom', width: 740, height: 500, dsf: 2 },
  { name: '1480@200%text', width: 1480, height: 1000, textZoom: 2 },
]
const STATES = ['clean', 'legacy', 'discrepancy']
const MODES = ['proposed', 'current']
const SHOT_SET = new Set(['legacy/proposed/light/1480', 'legacy/proposed/dark/1480', 'legacy/proposed/light/390', 'legacy/proposed/dark/320', 'legacy/current/light/1480', 'legacy/current/light/390', 'discrepancy/proposed/light/1480', 'discrepancy/proposed/light/390', 'clean/proposed/light/1480', 'clean/proposed/dark/390', 'legacy/proposed/light/1480@200%text', 'legacy/proposed/light/768', 'legacy/proposed/light/1024'])

async function routeFonts(context) {
  if (!FONTS) return
  await context.route('https://fonts.googleapis.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/css', body: readFileSync(path.join(FONTS, 'fonts.css'), 'utf8') }))
  await context.route('https://fonts.gstatic.com/**', (route) => {
    const file = path.join(FONTS, path.basename(new URL(route.request().url()).pathname))
    return existsSync(file) ? route.fulfill({ status: 200, contentType: 'font/woff2', body: readFileSync(file) }) : route.abort()
  })
}

async function run() {
  const browser = await chromium.launch()
  const results = { generatedAt: new Date().toISOString(), configs: [] }
  for (const theme of ['light', 'dark']) {
    for (const cfg of CONFIGS) {
      const context = await browser.newContext({ viewport: { width: cfg.width, height: cfg.height }, deviceScaleFactor: cfg.dsf || 1, isMobile: !!cfg.mobile, hasTouch: !!cfg.mobile, reducedMotion: 'reduce' })
      await routeFonts(context)
      await context.addInitScript((t) => { try { localStorage.setItem('proto-theme', t) } catch {} }, theme)
      const page = await context.newPage()
      await page.goto(PROTO_URL, { waitUntil: 'load' })
      await page.evaluate(() => document.fonts.ready)
      for (const stateName of STATES) {
        for (const mode of MODES) {
          await page.evaluate(({ stateName, mode, textZoom }) => {
            window.EN_PROTO.state.stateName = stateName
            window.EN_PROTO.state.mode = mode
            window.EN_PROTO.state.window = '12'
            document.documentElement.style.fontSize = textZoom ? `${textZoom * 100}%` : ''
            window.EN_PROTO.render()
          }, { stateName, mode, textZoom: cfg.textZoom || null })
          await page.waitForTimeout(120)
          const m = await page.evaluate(() => window.EN_PROTO.measure())
          // Does the proposed table fit without scrolling in the "Newest 6" window?
          let window6 = null
          if (mode === 'proposed') {
            await page.evaluate(() => { window.EN_PROTO.state.window = '6n'; window.EN_PROTO.render() })
            await page.waitForTimeout(80)
            const m6 = await page.evaluate(() => window.EN_PROTO.measure())
            window6 = m6.table
            await page.evaluate(() => { window.EN_PROTO.state.window = '12'; window.EN_PROTO.render() })
            await page.waitForTimeout(80)
          }
          results.configs.push({ theme, state: stateName, mode, ...cfg, ...m, window6 })
          const key = `${stateName}/${mode}/${theme}/${cfg.name}`
          if (SHOTS && SHOT_SET.has(key)) {
            mkdirSync(SHOTS, { recursive: true })
            await page.screenshot({ path: path.join(SHOTS, `proto-${key.replace(/[/@%]/g, '-')}.png`), fullPage: true })
          }
          if (mode === 'proposed' && stateName === 'legacy') console.log(theme, cfg.name, 'overflow', m.pageOverflowPx, 'kpi worst', m.kpi.map((k) => k.worstOverflowPx).join(','), 'valueTop', [...new Set(m.kpi.map((k) => k.valueTop))].join('/'), 'table', m.table && `${m.table.tableWidth}/${m.table.containerWidth} cols ${m.table.minColumn}-${m.table.maxColumn} scrolls=${m.table.scrolls} clipped=${m.table.cellTextClipped} occluded=${m.table.occludedAtFarRight.length}`, 'win6', window6 && `${window6.tableWidth}/${window6.containerWidth} scrolls=${window6.scrolls}`)
        }
      }
      await context.close()
    }
  }
  mkdirSync(path.dirname(OUT), { recursive: true })
  writeFileSync(OUT, JSON.stringify(results, null, 1))
  await browser.close()
}

run().catch((e) => { console.error(e); process.exit(1) })
