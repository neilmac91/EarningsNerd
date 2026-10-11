// Measures the CURRENT production components (the repo's own frontend build, `next start`) on the
// (The recorded run, measurements/current.json, is of main at 97293e7, before #1199–#1203; the probes
// below find the markup of that build AND of main after #1200/#1202 by data attribute, and every
// probe asserts how many elements it found so a markup change fails the run instead of passing it.)
// real META 12-quarter dataset in its production-like legacy state, with every API answered inside
// the browser (page.route) — the same no-backend discipline as tests/e2e. Records page overflow,
// KPI card-child containment, the metrics table's width and per-column widths, sticky-column
// occlusion at every scroll rest position, and the count of repeated source-check labels, at six viewport
// widths, both themes, 200% browser zoom (CSS viewport halved at 2x) and 200% text size at 1480, 390 and 320
// (the same profiles as measure-proto.mjs, so the two recorded runs compare like for like).
//
//   node harness/measure-current.mjs --base http://localhost:3000 --data prototype/data --out measurements/current.json [--shots dir]
//
// Run from tasks/analysis-redesign-2026-10/. Needs the global Playwright (NODE_PATH) or the frontend's.
// measurements/current.json is the recording of main at 97293e7 and is written only from a checkout of that
// revision: on any other checkout the run needs --out naming another file (a fresh measurement of the shipped
// components, never a comparison with the recording), and it refuses an --out that holds a recording of another
// commit. Every run records the checkout's commit, the frontend/ tree hash and the uncommitted files under
// frontend/ and this directory; the served build must come from that checkout.
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs'
import { execSync } from 'node:child_process'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
// The cloud image ships Playwright globally (NODE_PATH, CommonJS); the frontend's own @playwright/test works too.
const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) => (a.startsWith('--') ? [a.slice(2), all[i + 1]] : [])).filter((x) => x.length))
const BASE = args.base || 'http://localhost:3000'
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DATA = path.resolve(ROOT, args.data || 'prototype/data')
const BASELINE = { file: 'measurements/current.json', revision: '97293e76fe71ff6b7e1848d57f00e808866e8c1c' }
const git = (cmd) => { try { return execSync(cmd, { cwd: ROOT, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() } catch { return null } }
const COMMIT = git('git rev-parse HEAD') || ''
const sameCommit = (a, b) => !!a && !!b && (a.startsWith(b) || b.startsWith(a))
if (!args.out && !sameCommit(COMMIT, BASELINE.revision)) throw new Error(`${BASELINE.file} is the recording of main at ${BASELINE.revision.slice(0, 7)}; this checkout is ${COMMIT.slice(0, 7) || 'unknown'}: pass --out <another file> for a fresh measurement of this build (it does not compare with the recording), or run from a worktree of ${BASELINE.revision.slice(0, 7)} to retake the baseline`)
const OUT = path.resolve(ROOT, args.out || BASELINE.file)
if (existsSync(OUT)) {
  let recorded = null
  try { recorded = (JSON.parse(readFileSync(OUT, 'utf8')).environment || {}).commit || null } catch {}
  if (recorded && !sameCommit(COMMIT, recorded)) throw new Error(`${path.relative(ROOT, OUT)} records a run of ${recorded}; this checkout is ${COMMIT.slice(0, 7) || 'unknown'}: pass a different --out`)
}
const DIRTY = (git('git status --porcelain -- :/frontend :/tasks/analysis-redesign-2026-10/harness') || '').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
const SHOTS = args.shots || null
const STATE = args.state || 'legacy'
const API = 'http://localhost:8010'

// The prototype's data modules are JS assignments (file:// pages cannot fetch JSON); read the literal out of them.
const literal = (file) => { const last = readFileSync(path.join(DATA, file), 'utf8').trim().split('\n').pop(); return JSON.parse(last.slice(last.indexOf('= ') + 2).replace(/;\s*$/, '')) }
const state = literal(`${STATE}.js`)
const coverage = literal('coverage.js')
const company = { id: 1, cik: '1326801', ticker: 'META', name: 'Meta Platforms, Inc.', exchange: 'NASDAQ' }
const user = { id: 1, email: 'design-review@example.com', full_name: 'Design review', is_verified: true, is_admin: false, created_at: '2026-01-01T00:00:00Z', role: 'user', oauth_provider: null }
const subscription = { is_pro: true, stripe_customer_id: 'cus_design', stripe_subscription_id: 'sub_design', subscription_status: 'active', plan: 'pro', status: 'active', trial_end: null, current_period_end: '2027-01-01T00:00:00Z', cancel_at_period_end: false }

const CONFIGS = [
  { name: '1480', width: 1480, height: 1000 },
  { name: '1054', width: 1054, height: 1000 },
  { name: '1024', width: 1024, height: 1000 },
  { name: '768', width: 768, height: 1024 },
  { name: '390', width: 390, height: 844, mobile: true },
  { name: '320', width: 320, height: 568, mobile: true },
  { name: '1480@200%zoom', width: 740, height: 500, dsf: 2 },
  { name: '1480@200%text', width: 1480, height: 1000, textZoom: 2 },
  { name: '390@200%text', width: 390, height: 844, mobile: true, textZoom: 2 },
  { name: '320@200%text', width: 320, height: 568, mobile: true, textZoom: 2 },
]

function sse(events) {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
}

async function mockApi(context) {
  await context.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (p === '/api/auth/me') return json(user)
    if (p === '/api/subscriptions/subscription') return json(subscription)
    if (p === '/api/subscriptions/usage') return json({ is_pro: true, summaries_used: 0, summaries_limit: 0, analysis_used: 1, analysis_limit: 50, qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 0 })
    if (p === '/api/companies/META') return json(company)
    if (p === '/api/analysis/META/coverage') return json(coverage)
    if (p === '/api/analysis/META/dataset') return json(state.dataset)
    if (p === '/api/analysis/META/stream') {
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse([{ type: 'progress', stage: 'assembling' }, state.completion]) })
    }
    return json({ detail: 'not mocked' }, 404)
  })
  // Nothing leaves the machine: analytics, fonts and any other host are refused.
  await context.route(/^https?:\/\/(?!localhost)/, (route) => route.abort())
}

async function measure(page, configuredWidth, expectedRows) {
  // Mobile Chromium widens the layout viewport to overflowing content, so innerWidth cannot detect
  // overflow: compare the document with the configured viewport width instead. The probes read the
  // rendered text (text-node rectangles and scrollWidth per block, `.sr-only` excluded), test both
  // sides of each cell's content box, and visit every scroll rest position, as the prototype's do.
  return page.evaluate(async ({ vw, expectedRows }) => {
    const doc = document.documentElement
    const r = (el) => el.getBoundingClientRect()
    const EPS = 0.5
    const settle = () => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)))
    const textRects = (root) => {
      const out = []
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.nodeValue.trim() || node.parentElement.closest('.sr-only')) continue
        const range = document.createRange(); range.selectNodeContents(node)
        for (const b of range.getClientRects()) if (b.width) out.push({ b, text: node.nodeValue.trim().slice(0, 40) })
      }
      return out
    }
    const worstOutside = (root, box) => {
      let worst = 0, text = ''
      for (const c of root.querySelectorAll('*')) { if (c.closest('.sr-only')) continue; const b = r(c); if (!b.width) continue; const o = Math.max(b.right - box.right, box.left - b.left); if (o > worst) { worst = o; text = (c.textContent || '').trim().slice(0, 40) } }
      for (const { b, text: t } of textRects(root)) { const o = Math.max(b.right - box.right, box.left - b.left); if (o > worst) { worst = o; text = t } }
      for (const c of root.querySelectorAll('*')) { if (c.closest('.sr-only')) continue; const cs = getComputedStyle(c); if (cs.overflow !== 'visible' && (c.scrollWidth > c.clientWidth + 1 || c.scrollHeight > c.clientHeight + 1)) { worst = Math.max(worst, c.scrollWidth - c.clientWidth, c.scrollHeight - c.clientHeight); text = (c.textContent || '').trim().slice(0, 40) } }
      return { worst: Math.round(worst * 10) / 10, text }
    }
    const badges = [...document.querySelectorAll('span.rounded-full')].filter((el) => /source check/i.test(el.textContent || ''))
    // main after #1200: cards marked data-analysis-kpi; main at 97293e7: a div.grid of four Cards.
    const markedCards = [...document.querySelectorAll('[data-analysis-kpi]')]
    const legacyGrid = [...document.querySelectorAll('main div.grid')].find((g) => g.className.includes('lg:grid-cols-4'))
    const cards = markedCards.length ? markedCards : legacyGrid ? [...legacyGrid.children] : []
    const kpi = cards.map((card) => {
      const cr = r(card)
      const w = worstOutside(card, cr)
      const value = card.querySelector('[data-kpi-value], .text-2xl')
      return { label: (card.querySelector('dt, .uppercase')?.textContent || '').trim(), width: Math.round(cr.width), height: Math.round(cr.height), valueTop: value ? Math.round(r(value).top - cr.top) : null, worstOverflowPx: w.worst, worstOverflowText: w.text }
    })
    // Metrics table.
    const heading = [...document.querySelectorAll('h2, h3')].find((h) => /Metrics by period/.test(h.textContent || ''))
    const section = heading?.closest('section')
    const table = section?.querySelector('table')
    const scroller = table?.parentElement
    let tableInfo = null
    if (table && scroller) {
      const ths = [...table.querySelectorAll('thead th')]
      const cols = ths.map((th, i) => {
        const cells = [...table.querySelectorAll(`tbody tr > :nth-child(${i + 1})`)]
        const warned = cells.some((c) => /source check/i.test(c.textContent || ''))
        return { header: (th.textContent || '').trim(), width: Math.round(r(th).width), warned }
      })
      // Both-sided cell clipping of the rendered text.
      const clipped = []
      for (const td of table.querySelectorAll('tbody td, tbody th')) {
        const cs = getComputedStyle(td); const b = r(td)
        const box = { left: b.left + parseFloat(cs.paddingLeft), right: b.right - parseFloat(cs.paddingRight) }
        const w = worstOutside(td, box)
        if (w.worst > EPS) clipped.push({ text: w.text, by: w.worst })
      }
      // Every rest position: a period header straddling the sticky column's right edge is an occluded column.
      const colWidth = ths.length > 1 ? r(ths[1]).width : 0
      const occluded = []
      let restPositions = 0
      if (colWidth && table.scrollWidth > scroller.clientWidth + 1) {
        const range = scroller.scrollWidth - scroller.clientWidth
        const stops = []
        for (let k = 0; k * colWidth <= range + EPS; k++) stops.push(Math.min(k * colWidth, range))
        if (stops[stops.length - 1] < range - EPS) stops.push(range)
        for (const stop of stops) {
          scroller.scrollLeft = stop
          await settle()
          restPositions++
          const stickyRight = r(ths[0]).right
          const straddling = ths.slice(1).filter((th) => { const hb = r(th); return hb.left < stickyRight - EPS && hb.right > stickyRight + EPS })
          if (straddling.length) occluded.push({ scrollLeft: Math.round(scroller.scrollLeft), columns: straddling.map((th) => (th.textContent || '').replace(/\s+/g, ' ').trim()) })
        }
        scroller.scrollLeft = 0
        await settle()
      }
      tableInfo = { tableWidth: Math.round(table.scrollWidth), containerWidth: Math.round(scroller.clientWidth), columns: cols, warnedWidths: cols.filter((c) => c.warned).map((c) => c.width), cleanWidths: cols.slice(1).filter((c) => !c.warned).map((c) => c.width), restPositions, occludedPositions: occluded, occludedAtFarRight: occluded.filter((o) => o.scrollLeft >= (scroller.scrollWidth - scroller.clientWidth) - 1), clippedCount: clipped.length, clippedCells: clipped.slice(0, 8) }
    }
    // The report-level summary line: the Data notes strip after #1200, the Sources & methods summary before it.
    const sm = document.querySelector('[data-analysis-data-notes] > details > summary') || [...document.querySelectorAll('summary')].find((s) => /Sources/.test(s.textContent || ''))
    const counts = { kpiCards: cards.length, tableHeaders: tableInfo ? tableInfo.columns.length : 0, tableRows: table ? table.querySelectorAll('tbody tr').length : 0 }
    // Every probe states what it found; a run whose counts are off measures nothing and must not pass.
    const probeErrors = []
    if (counts.kpiCards !== 4) probeErrors.push(`expected 4 KPI cards, found ${counts.kpiCards}`)
    if (counts.tableHeaders !== 13) probeErrors.push(`expected 13 table header cells, found ${counts.tableHeaders}`)
    if (counts.tableRows !== expectedRows) probeErrors.push(`expected the dataset's ${expectedRows} metric rows, found ${counts.tableRows}`)
    return {
      viewport: vw,
      layoutViewport: window.innerWidth,
      counts,
      probeErrors,
      fonts: ['Inter', 'Geist Mono'].map((f) => `${f}:${document.fonts.check(`12px "${f}"`)}`),
      documentWidth: doc.scrollWidth,
      pageOverflowPx: doc.scrollWidth - vw,
      sourceCheckLabels: badges.length,
      sourceCheckLabelTexts: [...new Set(badges.map((b) => (b.textContent || '').trim()))],
      summaryLine: sm ? (sm.textContent || '').replace(/\s+/g, ' ').trim() : null,
      kpi,
      table: tableInfo,
    }
  }, { vw: configuredWidth, expectedRows })
}

async function run() {
  const browser = await chromium.launch()
  const results = { base: BASE, state: STATE, generatedAt: new Date().toISOString(), environment: { chromium: browser.version(), platform: `${process.platform} ${process.arch}`, node: process.version, commit: COMMIT.slice(0, 7), frontendTree: git('git rev-parse HEAD:frontend'), dirty: DIRTY }, configs: [] }
  for (const theme of ['light', 'dark']) {
    for (const cfg of CONFIGS) {
      const context = await browser.newContext({ viewport: { width: cfg.width, height: cfg.height }, deviceScaleFactor: cfg.dsf || 1, isMobile: !!cfg.mobile, hasTouch: !!cfg.mobile, reducedMotion: 'reduce' })
      await mockApi(context)
      // The app's consent key is `cookie_consent` (CookieConsent.tsx); a stored decision hides the bar.
      await context.addInitScript((t) => { try { localStorage.setItem('theme', t); localStorage.setItem('cookie_consent', JSON.stringify({ necessary: true, analytics: false, decidedAt: '2026-01-01T00:00:00Z' })) } catch {} }, theme)
      const page = await context.newPage()
      await page.goto(`${BASE}/analysis?ticker=META`, { waitUntil: 'networkidle' })
      if (cfg.textZoom) await page.evaluate((z) => { document.documentElement.style.fontSize = `${z * 100}%` }, cfg.textZoom)
      // The page opens in annual mode; the mocked dataset is quarterly, so choose Quarterly first.
      const quarterly = page.getByRole('button', { name: 'Quarterly' })
      if (await quarterly.count()) await quarterly.first().click()
      await page.getByRole('button', { name: 'Run analysis' }).click()
      await page.getByRole('heading', { name: 'Metrics by period' }).waitFor({ timeout: 30000 })
      await page.getByRole('heading', { name: 'AI trend analysis' }).waitFor({ timeout: 30000 })
      await page.evaluate(() => document.fonts.ready)
      await page.waitForTimeout(600)
      const m = await measure(page, cfg.width, state.dataset.series.length)
      if (m.probeErrors.length) throw new Error(`${theme} ${cfg.name}: ${m.probeErrors.join('; ')}`)
      results.configs.push({ theme, ...cfg, ...m })
      if (SHOTS) {
        mkdirSync(SHOTS, { recursive: true })
        await page.screenshot({ path: path.join(SHOTS, `current-${theme}-${cfg.name.replace(/[@%]/g, '')}.png`), fullPage: true })
      }
      console.log(theme, cfg.name, 'overflow', m.pageOverflowPx, 'labels', m.sourceCheckLabels, 'table', m.table?.tableWidth, '/', m.table?.containerWidth, 'clipped', m.table?.clippedCount, 'occludedPositions', m.table?.occludedPositions.length, 'kpi worst', m.kpi.map((k) => k.worstOverflowPx).join(','))
      await context.close()
    }
  }
  mkdirSync(path.dirname(OUT), { recursive: true })
  writeFileSync(OUT, JSON.stringify(results, null, 1))
  await browser.close()
}

run().catch((e) => { console.error(e); process.exit(1) })
