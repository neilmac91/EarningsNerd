#!/usr/bin/env node
/* =============================================================================
   impeccable-panel-harness.mjs — renders .impeccable/design.json specimens the
   way the Impeccable live design panel does, then measures them
   -----------------------------------------------------------------------------
   Manual verification aid for DESIGN.md / sidecar refreshes (not run in CI: it
   needs a local copy of the Impeccable skill). The panel's own code is not
   reimplemented. `designPanelCss`, `renderComponentTiles` and the helpers and
   constants they use are extracted verbatim from the skill's
   scripts/live-browser.js and evaluated in Chromium, so the specimens get the
   consumer's real nesting:

     html(.dark) > body > #impeccable-live-design-host
       └ shadow: <style>designPanelCss</style> .root > aside.panel > .panel-body
           └ .tile.cmp-tile > .cmp-stage (centered flex column) > bare <div> host
               └ shadow: <style>component.css</style> <div>component.html</div>

   The page also carries the app's own theme signal: the `:root` and `.dark`
   custom-property rules from app/globals.css, with `.dark` toggled on <html>
   exactly as the app's theme bootstrap does. By default those rules go through
   lightningcss first, as `next dev` / `next build` (Turbopack) serve them: it
   lowercases hex values, so the served signal is `#d7dadc`, not the source
   `#D7DADC`. One scenario keeps the source spelling (`next dev --webpack`).
   With --app-url the panel is mounted in the running app instead, so the real
   served CSS, fonts and theme bootstrap apply. The OS colour scheme is emulated
   independently to prove it never overrides the app's explicit theme.

   Matrix: 440px panel on a 1440px viewport and the panel on a 375px viewport,
   app light/dark × OS light/dark, plus one 1200px-wide host to prove the
   navigation and modal container queries still reach their wide layouts.
   Checks per specimen: the host fits its stage and nothing overflows it (so a
   wide table can only scroll inside its own container), nothing widens the
   panel body, the stage paints the expected page ground, and the navigation
   and modal pick the layout for their available width. report.json records the
   table's scroll metrics.

   Run (from frontend/):
     node scripts/impeccable-panel-harness.mjs \
       --live-browser <impeccable>/plugin/skills/impeccable/scripts/live-browser.js \
       [--sidecar ../.impeccable/design.json] [--out <dir for report + PNGs>] \
       [--app-url http://localhost:3000/waitlist]   # mount in a running `npm run dev`
   Set HARNESS_CHROMIUM=/path/to/chrome when Playwright's managed Chromium is
   not installed. Exits 1 when any check fails; report.json lists each result.

   The real live panel: Impeccable reads the sidecar only from
   `<project root>/.impeccable/design.json`. Booted from the repository root it
   resolves the project to frontend/ and shows no specimens, so give the repo
   root its own `.impeccable/live/config.json` ({"files":
   ["frontend/app/layout.tsx"], "insertBefore": "</body>", "commentSyntax":
   "jsx"}) rather than moving or copying the sidecar. Live mode also expects a
   PRODUCT.md, which this repository does not have.
============================================================================= */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`)
  return i > -1 ? process.argv[i + 1] : fallback
}

const liveBrowserPath = arg('live-browser', process.env.IMPECCABLE_LIVE_BROWSER)
if (!liveBrowserPath) {
  console.error('usage: node scripts/impeccable-panel-harness.mjs --live-browser <path to live-browser.js>')
  process.exit(2)
}
const appUrl = arg('app-url')
const sidecarPath = path.resolve(arg('sidecar', path.join(FRONTEND, '../.impeccable/design.json')))
const outDir = path.resolve(arg('out', fs.mkdtempSync(path.join(os.tmpdir(), 'impeccable-harness-'))))
fs.mkdirSync(outDir, { recursive: true })

const liveSrc = fs.readFileSync(liveBrowserPath, 'utf8')
const sidecar = JSON.parse(fs.readFileSync(sidecarPath, 'utf8'))
const globalsCss = fs.readFileSync(path.join(FRONTEND, 'app/globals.css'), 'utf8')

/** Source text of the block that starts at `start`, up to its balanced closing brace. */
function block(src, start, label) {
  const at = src.indexOf(start)
  if (at < 0) throw new Error(`${label}: "${start}" not found in ${liveBrowserPath}`)
  let depth = 0
  for (let i = src.indexOf('{', at); i < src.length; i += 1) {
    if (src[i] === '{') depth += 1
    else if (src[i] === '}' && --depth === 0) return src.slice(at, i + 1)
  }
  throw new Error(`${label}: unbalanced block`)
}
/** A single `const X = …;` statement (the extracted values contain no semicolons). */
function statement(src, start) {
  const at = src.indexOf(start)
  if (at < 0) throw new Error(`"${start}" not found in ${liveBrowserPath}`)
  return src.slice(at, src.indexOf(';', at) + 1)
}

const panelSource = [
  statement(liveSrc, 'const FONT = '),
  statement(liveSrc, 'const MONO = '),
  statement(liveSrc, 'const EASE = '),
  statement(liveSrc, 'const DESIGN_PANEL_WIDTH = '),
  statement(liveSrc, 'const PICKER_SHADOW ='),
  `${block(liveSrc, 'const C = {', 'C')};`,
  `${block(liveSrc, 'const DP = {', 'DP')};`,
  block(liveSrc, 'function barPaletteForTheme(', 'barPaletteForTheme'),
  block(liveSrc, 'function designPanelCss(', 'designPanelCss'),
  block(liveSrc, 'function renderComponentTiles(', 'renderComponentTiles'),
  block(liveSrc, 'function groupByKind(', 'groupByKind'),
  block(liveSrc, 'function titleForKind(', 'titleForKind'),
  block(liveSrc, 'function escapeHtml(', 'escapeHtml'),
].join('\n')

/** The app's theme signal: the :root and .dark custom-property rules, as written in source… */
const sourceThemeCss = [block(globalsCss, ':root {', ':root'), globalsCss.match(/^\.dark \{[^}]*\}/m)?.[0]]
  .filter(Boolean)
  .join('\n')
/** …and as Turbopack serves them (lightningcss, the same transform Next 16 applies). */
async function servedCss(code) {
  const { transform } = await import('lightningcss').catch(() => {
    throw new Error('lightningcss is not resolvable from frontend/; run npm ci, or use --app-url')
  })
  return transform({ filename: 'globals.css', code: Buffer.from(code), minify: false }).code.toString()
}
const THEME_CSS = { source: sourceThemeCss, served: await servedCss(sourceThemeCss) }

const PAGE_GROUND = { light: 'rgb(244, 243, 238)', dark: 'rgb(11, 17, 32)' }

const SCENARIOS = [
  ...['light', 'dark'].flatMap((app) =>
    ['light', 'dark'].map((osScheme) => ({
      name: `wide-viewport_app-${app}_os-${osScheme}`,
      viewport: { width: 1440, height: 900 },
      app,
      osScheme,
    })),
  ),
  { name: 'mobile-viewport_app-light_os-dark', viewport: { width: 375, height: 812 }, app: 'light', osScheme: 'dark' },
  { name: 'mobile-viewport_app-dark_os-light', viewport: { width: 375, height: 812 }, app: 'dark', osScheme: 'light' },
  { name: 'wide-host-probe_app-light_os-light', viewport: { width: 1440, height: 900 }, app: 'light', osScheme: 'light', panelWidth: 1240 },
  // `next dev --webpack` keeps the source spelling of the signal.
  { name: 'wide-viewport_app-dark_os-light_source-css', viewport: { width: 1440, height: 900 }, app: 'dark', osScheme: 'light', css: 'source' },
].filter((s) => !(appUrl && s.css === 'source')) // --app-url always uses what the app serves

function pageHtml(scenario) {
  return `<!doctype html><html${scenario.app === 'dark' ? ' class="dark"' : ''}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><style>${THEME_CSS[scenario.css ?? 'served']}</style></head><body></body></html>`
}

/** Runs in the page: mirrors initDesignPanel + renderDesignChrome, then measures each specimen. */
function mountAndMeasure({ panelSource, components, panelWidth }) {
  // Evaluates the consumer's own source, extracted verbatim from live-browser.js above.
  const api = new Function(`${panelSource}; return { designPanelCss, barPaletteForTheme, renderComponentTiles };`)()
  const designHost = document.createElement('div')
  designHost.id = 'impeccable-live-design-host'
  Object.assign(designHost.style, { position: 'fixed', top: '0', left: '0', width: '0', height: '0', zIndex: '100015' })
  const designShadow = designHost.attachShadow({ mode: 'open' })
  const style = document.createElement('style')
  style.textContent = api.designPanelCss(api.barPaletteForTheme('light'))
  if (panelWidth) style.textContent += `\n.panel { width: ${panelWidth}px; max-width: calc(100vw - 24px); }`
  designShadow.appendChild(style)
  const root = document.createElement('div')
  root.className = 'root'
  const panel = document.createElement('aside')
  panel.className = 'panel'
  panel.setAttribute('data-open', 'true')
  const header = document.createElement('div')
  header.className = 'panel-header'
  header.innerHTML = '<div class="panel-title">DESIGN.md</div>'
  panel.appendChild(header)
  const body = document.createElement('div')
  body.className = 'panel-body'
  panel.appendChild(body)
  root.appendChild(panel)
  designShadow.appendChild(root)
  document.body.appendChild(designHost)
  api.renderComponentTiles(body, components)

  const stages = [...body.querySelectorAll('.cmp-stage')]
  const results = stages.map((stage, index) => {
    const host = stage.firstElementChild
    const sub = host.shadowRoot
    const stageStyle = getComputedStyle(stage)
    const stageInner = stage.clientWidth - parseFloat(stageStyle.paddingLeft) - parseFloat(stageStyle.paddingRight)
    const hostRect = host.getBoundingClientRect()
    const dsStage = sub.querySelector('.ds-stage')
    const shown = (sel) => {
      const el = sub.querySelector(sel)
      return !!el && getComputedStyle(el).display !== 'none'
    }
    const scroll = sub.querySelector('.ds-table-scroll')
    const footer = sub.querySelector('.ds-modal-footer')
    return {
      index,
      name: components[index].name,
      stageInner: Math.round(stageInner),
      hostWidth: Math.round(hostRect.width),
      hostScrollWidth: host.scrollWidth,
      hostClientWidth: host.clientWidth,
      ground: dsStage ? getComputedStyle(dsStage).backgroundColor : null,
      nav: sub.querySelector('.ds-header')
        ? { desktopNav: shown('.ds-desktop-nav'), mobileActions: shown('.ds-mobile-actions'), wordmark: shown('.ds-wordmark') }
        : null,
      table: scroll ? { scrollWidth: scroll.scrollWidth, clientWidth: scroll.clientWidth } : null,
      modalFooter: footer ? getComputedStyle(footer).flexDirection : null,
    }
  })
  return {
    panelBody: { scrollWidth: body.scrollWidth, clientWidth: body.clientWidth },
    stageInner: results[0]?.stageInner,
    results,
  }
}

function check(scenario, measured) {
  const failures = []
  const fail = (msg) => failures.push(msg)
  if (measured.panelBody.scrollWidth > measured.panelBody.clientWidth + 1) {
    fail(`panel body scrolls sideways (${measured.panelBody.scrollWidth} > ${measured.panelBody.clientWidth})`)
  }
  for (const r of measured.results) {
    if (r.hostWidth > r.stageInner + 1) fail(`${r.name}: host ${r.hostWidth}px exceeds its ${r.stageInner}px stage`)
    if (r.hostScrollWidth > r.hostClientWidth + 1) {
      fail(`${r.name}: content overflows its host (${r.hostScrollWidth} > ${r.hostClientWidth})`)
    }
    if (r.ground !== PAGE_GROUND[scenario.app]) fail(`${r.name}: ground ${r.ground}, expected ${PAGE_GROUND[scenario.app]} (app ${scenario.app})`)
    const wide = r.stageInner >= 1024
    if (r.nav && (r.nav.desktopNav !== wide || r.nav.mobileActions === wide)) {
      fail(`${r.name}: ${wide ? 'desktop' : 'mobile'} layout expected at ${r.stageInner}px, got ${JSON.stringify(r.nav)}`)
    }
    if (r.nav && r.nav.wordmark !== r.stageInner >= 640) fail(`${r.name}: wordmark visibility wrong at ${r.stageInner}px`)
    if (r.modalFooter && r.modalFooter !== (r.stageInner >= 640 ? 'row' : 'column')) {
      fail(`${r.name}: footer ${r.modalFooter} at ${r.stageInner}px`)
    }
  }
  return failures
}

const browser = await chromium.launch(process.env.HARNESS_CHROMIUM ? { executablePath: process.env.HARNESS_CHROMIUM } : {})
const report = { liveBrowser: path.resolve(liveBrowserPath), sidecar: sidecarPath, appUrl: appUrl ?? null, scenarios: [] }
let failed = 0
try {
  for (const scenario of SCENARIOS) {
    const context = await browser.newContext({ viewport: scenario.viewport, colorScheme: scenario.osScheme })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
    if (appUrl) {
      // The app's own bootstrap reads localStorage.theme before first paint.
      await page.addInitScript((theme) => localStorage.setItem('theme', theme), scenario.app)
      await page.goto(appUrl, { waitUntil: 'networkidle' })
      await page.evaluate(() => document.fonts.ready)
    } else {
      await page.setContent(pageHtml(scenario))
    }
    const measured = await page.evaluate(mountAndMeasure, {
      panelSource,
      components: sidecar.components,
      panelWidth: scenario.panelWidth ?? null,
    })
    // A running app without its API logs its own errors; only the synthetic page must stay clean.
    const failures = [...check(scenario, measured), ...(appUrl ? [] : errors.map((e) => `console: ${e}`))]
    failed += failures.length
    const tiles = await page.locator('#impeccable-live-design-host .cmp-tile').all()
    for (const [i, tile] of tiles.entries()) {
      await tile.screenshot({ path: path.join(outDir, `${scenario.name}_${String(i).padStart(2, '0')}.png`) })
    }
    report.scenarios.push({ ...scenario, ...measured, failures })
    console.log(`${failures.length ? 'FAIL' : 'PASS'} ${scenario.name} (stage ${measured.stageInner}px)`)
    for (const f of failures) console.log(`  - ${f}`)
    await context.close()
  }
} finally {
  await browser.close()
}
fs.writeFileSync(path.join(outDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(`${failed ? 'FAIL' : 'PASS'}: ${SCENARIOS.length} scenarios × ${sidecar.components.length} specimens; report and PNGs in ${outDir}`)
process.exit(failed ? 1 : 0)
