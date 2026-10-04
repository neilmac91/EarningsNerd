#!/usr/bin/env node
/**
 * Playwright capture harness for the EarningsNerd critique.
 *
 *   node capture.mjs --out <name> --route /filing/3 [--scenario pro,content] [--theme light|dark]
 *        [--viewport 1440x900|390x844|768x1024] [--mobile] [--reduced-motion] [--zoom 2]
 *        [--steps 'click=text=Ask this Filing;wait=800;shot=rail-open;press=Tab;press=Tab;shot=focus-2']
 *        [--full] [--styles 'h1,button,.text-text-tertiary-light'] [--aria] [--coach-seen]
 *   node capture.mjs --jobs jobs.json          # batch: array of {out, route, scenario, theme, viewport, mobile, steps, full, styles, aria}
 *
 * Writes evidence/<out>.png (+ step shots evidence/<out>__<shot>.png) and evidence/<out>.json with the
 * final URL, console errors/warnings, failed requests, viewport, scenario, aria snapshot (if --aria),
 * computed-style + contrast samples (if --styles), focus trail from press=Tab steps, and timings.
 *
 * Steps DSL (semicolon-separated `verb=arg`): click, dblclick, hover, focus, fill(sel|text), press(key),
 * wait(ms), waitfor(sel), scroll(sel | px), shot(name), fullshot(name), eval(js), setcookie(scenario),
 * reload, goto(path), select(sel|value), keyfocus (record active element), tabtrail(n) (press Tab n times
 * recording the focused element each time), styles(sel list), aria(sel), viewport(WxH), emulate(reduced|normal),
 * type(sel|text), blur, text(sel) (record textContent), count(sel), rect(sel), hidecoach.
 * Selectors use Playwright syntax (text=, role=button[name="x"] via getByRole shorthand `role:button:Name`).
 */
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const HERE = path.dirname(new URL(import.meta.url).pathname)
const REPO = path.resolve(HERE, '..', '..')
const { chromium, devices } = await import(pathToFileURL(path.join(REPO, 'frontend/node_modules/@playwright/test/index.mjs')).href)

const BASE = process.env.CRITIQUE_BASE_URL || 'http://localhost:3000'
const EVID = process.env.CRITIQUE_EVIDENCE_DIR || path.join(HERE, 'evidence')
fs.mkdirSync(EVID, { recursive: true })

function parseArgs(argv) {
  const a = {}
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i]
    if (!k.startsWith('--')) continue
    const key = k.slice(2)
    const next = argv[i + 1]
    if (next === undefined || next.startsWith('--')) a[key] = true
    else { a[key] = next; i++ }
  }
  return a
}

function loc(page, sel) {
  if (sel.startsWith('role:')) {
    const [, role, ...rest] = sel.split(':')
    const name = rest.join(':')
    return name ? page.getByRole(role, { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') }).first() : page.getByRole(role).first()
  }
  if (sel.startsWith('label:')) return page.getByLabel(sel.slice(6)).first()
  if (sel.startsWith('placeholder:')) return page.getByPlaceholder(sel.slice(12)).first()
  return page.locator(sel).first()
}

const relLum = (r, g, b) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4) }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b) }

// Runs in the page: computed styles + effective background + WCAG contrast for each selector match (first 6).
const STYLE_PROBE = (selectors) => {
  const parse = (s) => { const m = s && s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map((x) => parseFloat(x)); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 } }
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b) }
  const blend = (top, bottom) => ({ r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1 })
  const effectiveBg = (el) => { let acc = null; let node = el; while (node && node !== document.documentElement.parentNode) { const cs = getComputedStyle(node); const c = parse(cs.backgroundColor); if (c && c.a > 0) { acc = acc ? blend(acc, c) : c; if (acc.a >= 0.999 && c.a >= 0.999) return acc } node = node.parentElement } const html = parse(getComputedStyle(document.documentElement).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 }; return acc ? blend(acc, html) : html }
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05) }
  const out = []
  for (const sel of selectors) {
    let nodes = []
    try { nodes = Array.from(document.querySelectorAll(sel)).slice(0, 6) } catch (e) { out.push({ selector: sel, error: String(e) }); continue }
    for (const el of nodes) {
      const cs = getComputedStyle(el); const r = el.getBoundingClientRect()
      const fg = parse(cs.color); const bg = effectiveBg(el)
      const fgOnBg = fg && fg.a < 1 ? blend(fg, bg) : fg
      const size = parseFloat(cs.fontSize); const weight = parseInt(cs.fontWeight, 10)
      const large = size >= 24 || (size >= 18.66 && weight >= 700)
      out.push({ selector: sel, tag: el.tagName.toLowerCase(), text: (el.textContent || '').trim().slice(0, 80), classes: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 200),
        rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }, visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
        color: cs.color, backgroundColor: cs.backgroundColor, effectiveBackground: bg ? 'rgb(' + Math.round(bg.r) + ', ' + Math.round(bg.g) + ', ' + Math.round(bg.b) + ')' : null,
        contrast: fgOnBg && bg ? Math.round(ratio(fgOnBg, bg) * 100) / 100 : null, wcagAA: fgOnBg && bg ? (ratio(fgOnBg, bg) >= (large ? 3 : 4.5)) : null, largeText: large,
        fontFamily: cs.fontFamily.slice(0, 80), fontSize: cs.fontSize, fontWeight: cs.fontWeight, lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing, textAlign: cs.textAlign, hyphens: cs.hyphens,
        borderRadius: cs.borderRadius, boxShadow: cs.boxShadow.slice(0, 120), outline: cs.outlineStyle + ' ' + cs.outlineWidth, zIndex: cs.zIndex, position: cs.position })
    }
  }
  return out
}

const ACTIVE_PROBE = () => { const el = document.activeElement; if (!el) return null; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return { tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), name: el.getAttribute('aria-label') || (el.textContent || '').trim().slice(0, 60), id: el.id, ariaDisabled: el.getAttribute('aria-disabled'), disabled: el.disabled === true, rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }, inViewport: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth, boxShadow: cs.boxShadow.slice(0, 160), outline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor, focusVisible: el.matches(':focus-visible') } }

async function runJob(browser, job) {
  const t0 = Date.now()
  const [vw, vh] = String(job.viewport || '1440x900').split('x').map(Number)
  const mobile = job.mobile === true || job.mobile === 'true' || vw < 600
  const ctxOpts = { viewport: { width: vw, height: vh }, deviceScaleFactor: Number(job.dpr || 1), isMobile: mobile, hasTouch: mobile, reducedMotion: job.reducedMotion ? 'reduce' : 'no-preference', colorScheme: job.theme === 'dark' ? 'dark' : 'light', locale: 'en-US', timezoneId: 'America/New_York' }
  if (mobile) Object.assign(ctxOpts, { userAgent: devices['iPhone 13'].userAgent })
  const context = await browser.newContext(ctxOpts)
  const scenario = job.scenario || 'anon'
  await context.addCookies([{ name: 'en_scenario', value: scenario, domain: 'localhost', path: '/', sameSite: 'Lax' }])
  const theme = job.theme || 'light'
  await context.addInitScript(({ theme, coachSeen, extraLs }) => {
    try { localStorage.setItem('theme', theme); if (coachSeen) localStorage.setItem('en:copilot-coachmark-v1', '1'); for (const [k, v] of Object.entries(extraLs || {})) localStorage.setItem(k, v) } catch {}
  }, { theme, coachSeen: !!job.coachSeen, extraLs: job.localStorage || {} })
  const page = await context.newPage()
  const record = { out: job.out, route: job.route, scenario, theme, viewport: { width: vw, height: vh }, mobile, reducedMotion: !!job.reducedMotion, zoom: job.zoom || 1, console: [], pageErrors: [], failedRequests: [], steps: [], shots: [], styles: [], aria: null, focusTrail: [], texts: {}, counts: {}, rects: {} }
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) record.console.push({ type: m.type(), text: m.text().slice(0, 400) }) })
  page.on('pageerror', (e) => record.pageErrors.push(String(e).slice(0, 400)))
  page.on('requestfailed', (r) => record.failedRequests.push({ url: r.url().slice(0, 200), error: r.failure()?.errorText }))
  page.on('response', (r) => { if (r.status() >= 400 && !r.url().includes('/_next/')) record.failedRequests.push({ url: r.url().slice(0, 200), status: r.status() }) })

  const shot = async (name, full = false) => { const file = path.join(EVID, `${job.out}${name ? '__' + name : ''}.png`); await page.screenshot({ path: file, fullPage: full }); record.shots.push(path.basename(file)); return file }
  const applyZoom = async () => { if (job.zoom && Number(job.zoom) !== 1) { const client = await context.newCDPSession(page); await client.send('Emulation.setPageScaleFactor', { pageScaleFactor: Number(job.zoom) }).catch(() => {}); await page.evaluate((z) => { document.documentElement.style.zoom = String(z) }, Number(job.zoom)) } }

  try {
    await page.goto(BASE + job.route, { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => record.steps.push({ note: 'networkidle timeout' }))
    await page.waitForTimeout(Number(job.settle || 700))
    await applyZoom()
    const steps = typeof job.steps === 'string' ? job.steps.split(';').map((s) => s.trim()).filter(Boolean) : (job.steps || [])
    for (const raw of steps) {
      const eq = raw.indexOf('=')
      const verb = eq === -1 ? raw : raw.slice(0, eq)
      const arg = eq === -1 ? '' : raw.slice(eq + 1)
      const entry = { step: raw }
      try {
        switch (verb) {
          case 'click': await loc(page, arg).click({ timeout: 8000 }); break
          case 'dblclick': await loc(page, arg).dblclick({ timeout: 8000 }); break
          case 'hover': await loc(page, arg).hover({ timeout: 8000 }); break
          case 'focus': await loc(page, arg).focus({ timeout: 8000 }); break
          case 'blur': await page.evaluate(() => document.activeElement && document.activeElement.blur()); break
          case 'fill': { const [sel, ...t] = arg.split('|'); await loc(page, sel).fill(t.join('|'), { timeout: 8000 }); break }
          case 'type': { const [sel, ...t] = arg.split('|'); await loc(page, sel).pressSequentially(t.join('|'), { delay: 20, timeout: 8000 }); break }
          case 'select': { const [sel, v] = arg.split('|'); await loc(page, sel).selectOption(v, { timeout: 8000 }); break }
          case 'press': await page.keyboard.press(arg); break
          case 'wait': await page.waitForTimeout(Number(arg)); break
          case 'waitfor': await loc(page, arg).waitFor({ timeout: 15000 }); break
          case 'waitidle': await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}); break
          case 'scroll': if (/^-?\d+$/.test(arg)) await page.evaluate((y) => window.scrollBy(0, y), Number(arg)); else await loc(page, arg).scrollIntoViewIfNeeded({ timeout: 8000 }); break
          case 'shot': await shot(arg); break
          case 'fullshot': await shot(arg, true); break
          case 'eval': entry.result = await page.evaluate(arg); break
          case 'setcookie': await context.addCookies([{ name: 'en_scenario', value: arg, domain: 'localhost', path: '/', sameSite: 'Lax' }]); break
          case 'reload': await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}); await applyZoom(); break
          case 'goto': await page.goto(BASE + arg, { waitUntil: 'domcontentloaded' }); await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}); await applyZoom(); break
          case 'keyfocus': entry.active = await page.evaluate(ACTIVE_PROBE); record.focusTrail.push({ after: raw, ...entry.active }); break
          case 'tabtrail': { const n = Number(arg || 10); for (let i = 0; i < n; i++) { await page.keyboard.press('Tab'); const a = await page.evaluate(ACTIVE_PROBE); record.focusTrail.push({ tab: i + 1, ...a }) } break }
          case 'styles': record.styles.push(...(await page.evaluate(STYLE_PROBE, arg.split(',').map((s) => s.trim())))); break
          case 'aria': record.aria = (record.aria || '') + '\n--- ' + (arg || 'body') + ' ---\n' + (await (arg ? loc(page, arg) : page.locator('body')).ariaSnapshot({ timeout: 10000 })); break
          case 'text': entry.text = (await loc(page, arg).textContent({ timeout: 5000 }))?.trim().slice(0, 500); record.texts[arg] = entry.text; break
          case 'count': entry.count = await page.locator(arg).count(); record.counts[arg] = entry.count; break
          case 'rect': entry.rect = await loc(page, arg).boundingBox({ timeout: 5000 }); record.rects[arg] = entry.rect; break
          case 'viewport': { const [w, h] = arg.split('x').map(Number); await page.setViewportSize({ width: w, height: h }); record.viewport = { width: w, height: h }; break }
          case 'emulate': await page.emulateMedia({ reducedMotion: arg === 'reduced' ? 'reduce' : 'no-preference' }); break
          case 'hidecoach': await page.evaluate(() => { try { localStorage.setItem('en:copilot-coachmark-v1', '1') } catch {} }); break
          default: entry.error = 'unknown verb'
        }
      } catch (e) { entry.error = String(e).split('\n')[0].slice(0, 300) }
      record.steps.push(entry)
    }
    if (job.styles) record.styles.push(...(await page.evaluate(STYLE_PROBE, String(job.styles).split(',').map((s) => s.trim()))))
    if (job.aria) record.aria = (record.aria || '') + '\n--- body ---\n' + (await page.locator('body').ariaSnapshot({ timeout: 10000 }))
    record.finalUrl = page.url()
    record.title = await page.title()
    record.docHeight = await page.evaluate(() => document.documentElement.scrollHeight)
    record.horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 ? { scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth } : null)
    await shot('', !!job.full)
  } catch (e) {
    record.fatal = String(e).slice(0, 500)
    try { await shot('fatal') } catch {}
  }
  record.ms = Date.now() - t0
  fs.writeFileSync(path.join(EVID, `${job.out}.json`), JSON.stringify(record, null, 2))
  await context.close()
  return record
}

const args = parseArgs(process.argv.slice(2))
const jobs = args.jobs ? JSON.parse(fs.readFileSync(args.jobs, 'utf8')) : [{ out: args.out || 'capture', route: args.route || '/', scenario: args.scenario, theme: args.theme, viewport: args.viewport, mobile: !!args.mobile, reducedMotion: !!args['reduced-motion'], zoom: args.zoom, steps: args.steps, full: !!args.full, styles: args.styles, aria: !!args.aria, coachSeen: !!args['coach-seen'], dpr: args.dpr, settle: args.settle }]
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined })
const summary = []
for (const job of jobs) {
  const r = await runJob(browser, job)
  summary.push({ out: r.out, route: r.route, scenario: r.scenario, theme: r.theme, viewport: r.viewport, shots: r.shots.length, consoleErrors: r.console.filter((c) => c.type === 'error').length, failed: r.failedRequests.length, fatal: r.fatal || null, ms: r.ms, hOverflow: r.horizontalOverflow })
  console.log(JSON.stringify(summary[summary.length - 1]))
}
await browser.close()
