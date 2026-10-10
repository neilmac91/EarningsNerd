// Measures the CURRENT production components (the repo's own frontend build, `next start`) on the
// real META 12-quarter dataset in its production-like legacy state, with every API answered inside
// the browser (page.route) — the same no-backend discipline as tests/e2e. Records page overflow,
// KPI card-child containment, the metrics table's width and per-column widths, sticky-column
// occlusion at the far right, and the count of repeated source-check labels, at six viewport widths,
// both themes, 200% browser zoom (CSS viewport halved at 2x) and 200% text size.
//
//   node harness/measure-current.mjs --base http://localhost:3000 --data prototype/data --out measurements/current.json [--shots dir]
//
// Run from tasks/analysis-redesign-2026-10/. Needs the global Playwright (NODE_PATH) or the frontend's.
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
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
const OUT = path.resolve(ROOT, args.out || 'measurements/current.json')
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
    if (p === '/api/subscriptions/usage') return json({ is_pro: true, summaries_used: 0, summaries_limit: 0, analyses_used: 1, analyses_limit: 50, qa_used: 0, qa_limit: 0 })
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

async function measure(page) {
  return page.evaluate(() => {
    const vw = window.innerWidth
    const doc = document.documentElement
    const r = (el) => el.getBoundingClientRect()
    const badges = [...document.querySelectorAll('span.rounded-full')].filter((el) => /source check/i.test(el.textContent || ''))
    // KPI strip: the first grid with four Card children after the picker.
    const kpiGrid = [...document.querySelectorAll('main div.grid')].find((g) => g.className.includes('lg:grid-cols-4'))
    const cards = kpiGrid ? [...kpiGrid.children] : []
    const kpi = cards.map((card) => {
      const cr = r(card)
      const children = [...card.querySelectorAll('*')]
      let worst = 0
      let worstText = ''
      for (const child of children) {
        const b = r(child)
        if (b.width === 0) continue
        const over = Math.max(b.right - cr.right, cr.left - b.left)
        if (over > worst) { worst = over; worstText = (child.textContent || '').trim().slice(0, 40) }
      }
      const value = card.querySelector('.text-2xl')
      return { label: (card.querySelector('.uppercase')?.textContent || '').trim(), width: Math.round(cr.width), height: Math.round(cr.height), valueTop: value ? Math.round(r(value).top - cr.top) : null, worstOverflowPx: Math.round(worst * 10) / 10, worstOverflowText: worstText }
    })
    // Metrics table.
    const heading = [...document.querySelectorAll('h2')].find((h) => /Metrics by period/.test(h.textContent || ''))
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
      scroller.scrollLeft = scroller.scrollWidth
      const stickyRight = r(ths[0]).right
      // The first body row's cells partially hidden under the sticky column at the far right.
      const firstRow = table.querySelector('tbody tr')
      const occluded = [...firstRow.children].slice(1).map((td) => {
        const b = r(td)
        const value = td.querySelector('button') || td
        const vb = r(value)
        return { col: cols[[...firstRow.children].indexOf(td)].header, cellLeft: Math.round(b.left - stickyRight), valueLeft: Math.round(vb.left - stickyRight), valueWidth: Math.round(vb.width) }
      }).filter((c) => c.valueLeft < 0 && c.valueLeft + c.valueWidth > 0)
      scroller.scrollLeft = 0
      tableInfo = { tableWidth: Math.round(table.scrollWidth), containerWidth: Math.round(scroller.clientWidth), columns: cols, warnedWidths: cols.filter((c) => c.warned).map((c) => c.width), cleanWidths: cols.slice(1).filter((c) => !c.warned).map((c) => c.width), occludedAtFarRight: occluded }
    }
    const sm = [...document.querySelectorAll('summary')].find((s) => /Sources/.test(s.textContent || ''))
    return {
      viewport: vw,
      documentWidth: doc.scrollWidth,
      pageOverflowPx: doc.scrollWidth - vw,
      sourceCheckLabels: badges.length,
      sourceCheckLabelTexts: [...new Set(badges.map((b) => (b.textContent || '').trim()))],
      summaryLine: sm ? (sm.textContent || '').replace(/\s+/g, ' ').trim() : null,
      kpi,
      table: tableInfo,
    }
  })
}

async function run() {
  const browser = await chromium.launch()
  const results = { base: BASE, state: STATE, generatedAt: new Date().toISOString(), configs: [] }
  for (const theme of ['light', 'dark']) {
    for (const cfg of CONFIGS) {
      const context = await browser.newContext({ viewport: { width: cfg.width, height: cfg.height }, deviceScaleFactor: cfg.dsf || 1, isMobile: !!cfg.mobile, hasTouch: !!cfg.mobile, reducedMotion: 'reduce' })
      await mockApi(context)
      await context.addInitScript((t) => { try { localStorage.setItem('theme', t); localStorage.setItem('cookie-consent', 'accepted'); localStorage.setItem('en-cookie-consent', 'accepted') } catch {} }, theme)
      const page = await context.newPage()
      await page.goto(`${BASE}/analysis?ticker=META`, { waitUntil: 'networkidle' })
      if (cfg.textZoom) await page.evaluate((z) => { document.documentElement.style.fontSize = `${z * 100}%` }, cfg.textZoom)
      await page.getByRole('button', { name: 'Run analysis' }).click()
      await page.getByRole('heading', { name: 'Metrics by period' }).waitFor({ timeout: 30000 })
      await page.getByRole('heading', { name: 'AI trend analysis' }).waitFor({ timeout: 30000 })
      await page.waitForTimeout(600)
      const m = await measure(page)
      results.configs.push({ theme, ...cfg, ...m })
      if (SHOTS) {
        mkdirSync(SHOTS, { recursive: true })
        await page.screenshot({ path: path.join(SHOTS, `current-${theme}-${cfg.name.replace(/[@%]/g, '')}.png`), fullPage: true })
      }
      console.log(theme, cfg.name, 'overflow', m.pageOverflowPx, 'labels', m.sourceCheckLabels, 'table', m.table?.tableWidth, '/', m.table?.containerWidth, 'kpi worst', m.kpi.map((k) => k.worstOverflowPx).join(','))
      await context.close()
    }
  }
  mkdirSync(path.dirname(OUT), { recursive: true })
  writeFileSync(OUT, JSON.stringify(results, null, 1))
  await browser.close()
}

run().catch((e) => { console.error(e); process.exit(1) })
