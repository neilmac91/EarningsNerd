// Measures the PROTOTYPE (prototype/index.html) in every state, in the proposed view and in the
// reproduction of today's markup, at the brief's widths, both themes, 200% browser zoom and 200%
// text size: page overflow, KPI card-child containment and value alignment, table width and
// column widths, sticky-column occlusion at EVERY rest position (the start, every column boundary and
// the far-right end), both-sided cell clipping of the rendered
// text, text-aware KPI containment, the painted fill of a hovered sticky row header (it must be opaque,
// or the values scrolling beneath it show through), and the count of repeated labels; 200% text at 1480,
// 390 and 320.
//
//   node harness/measure-proto.mjs [--out file] [--fonts dir] [--shots dir] [--allow-dirty]
//
// The recorded run is auditable only from a committed tree: the output carries the commit, the prototype
// directory's tree hash (`git rev-parse <any later commit>:tasks/analysis-redesign-2026-10/prototype`
// reproduces it) and the list of uncommitted prototype or harness files, and the run refuses to start
// with such files unless --allow-dirty records them; even then the committed recording,
// measurements/prototype.json (the default --out; a symbolic or hard link to it counts as it, and any other
// multiply linked output is refused), is written only from a committed tree, since a recording of uncommitted
// bytes cannot be reproduced: a dirty run needs --out naming another file. Every probe asserts its element counts (4 cards, 13
// header cells in the 12-quarter window and 7 in Newest 6, exactly the dataset's metric rows), so a probe that finds
// nothing fails the run instead of recording a clean result.
//
// Run from tasks/analysis-redesign-2026-10/. With --fonts, Google Fonts requests are answered from a
// local directory holding the CSS as fonts.css plus the .woff2 files it names (no network needed); the run
// records those inputs by content hash, and the committed recording is written only from the pinned ones.
import { readFileSync, existsSync, lstatSync, mkdirSync, realpathSync, statSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { execSync } from 'node:child_process'
const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) => (a.startsWith('--') ? [a.slice(2), all[i + 1]] : [])).filter((x) => x.length))
const ROOT = realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'))
const git = (cmd) => { try { return execSync(cmd, { cwd: ROOT, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() } catch { return null } }
// A path with every existing component resolved through its symbolic links (a dangling link is refused), and an
// existing file compared by device and inode, so a symbolic or hard link to the committed recording is the recording.
const canonical = (p) => {
  const rest = []
  let cur = p
  while (!existsSync(cur)) {
    try { if (lstatSync(cur).isSymbolicLink()) throw new Error(`${cur} is a dangling symbolic link: pass a real path`) } catch (e) { if (e.code !== 'ENOENT') throw e }
    rest.unshift(path.basename(cur)); const parent = path.dirname(cur); if (parent === cur) break; cur = parent
  }
  return path.join(realpathSync(cur), ...rest)
}
const sameFile = (a, b) => { if (!existsSync(a) || !existsSync(b)) return false; const x = statSync(a), y = statSync(b); return x.dev === y.dev && x.ino === y.ino }
const BASELINE_PATH = canonical(path.resolve(ROOT, 'measurements/prototype.json'))
const outArg = canonical(path.resolve(ROOT, args.out || 'measurements/prototype.json'))
const OUT = sameFile(outArg, BASELINE_PATH) ? BASELINE_PATH : outArg
const WRITING_BASELINE = OUT === BASELINE_PATH
if (!WRITING_BASELINE && existsSync(OUT) && statSync(OUT).nlink > 1) throw new Error(`${OUT} has ${statSync(OUT).nlink} hard links, so writing it would overwrite a file under another name: pass an --out with one name`)
// The committed recording is written only from a committed tree: a run of uncommitted prototype or harness bytes
// can be recorded (--allow-dirty lists the files) but never reproduced, so it needs --out naming another file.
const dirty = (git('git status --porcelain -- prototype harness') || '').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
if (dirty.length && !('allow-dirty' in args)) throw new Error(`uncommitted prototype or harness files; commit them first, or pass --allow-dirty (with --out naming another file) to record them: ${dirty.join(', ')}`)
if (dirty.length && WRITING_BASELINE) throw new Error(`measurements/prototype.json is written only from a committed tree (uncommitted: ${dirty.join(', ')}): commit them, or pass --out <another file> for this dirty run`)
const FONTS = args.fonts ? canonical(path.resolve(process.cwd(), args.fonts)) : null
// The fonts the page renders with set every measured width, so the run records them: with --fonts, a content hash
// of the inputs the harness serves (fonts.css and the .woff2 files it names, by name and bytes); without it the page
// loads Google's live bytes, which no hash pins. The committed recording is written only from the pinned fonts
// below (the README says how that directory was fetched and how to check a fetch against the pin).
const fontsInputs = (dir) => {
  const css = readFileSync(path.join(dir, 'fonts.css'))
  const names = [...new Set([...css.toString('utf8').matchAll(/https:\/\/fonts\.gstatic\.com\/[^)\s'"]+/g)].map((m) => path.basename(new URL(m[0]).pathname)))].sort()
  const h = createHash('sha256'); h.update('fonts.css\0'); h.update(css); h.update('\0')
  for (const n of names) { h.update(`${n}\0`); h.update(readFileSync(path.join(dir, n))); h.update('\0') }
  return { dir, files: names.length + 1, hash: h.digest('hex') }
}
const FONT_INPUTS = FONTS ? fontsInputs(FONTS) : null
const BASELINE_FONTS = { files: 14, hash: '4bf26761317d2d6a0e324cf36e0ba1ce88612d4cabe4844088e125ccedb13903' }
if (WRITING_BASELINE && !FONT_INPUTS) throw new Error(`measurements/prototype.json is written only with --fonts <dir> holding the pinned fonts (${BASELINE_FONTS.files} inputs, hash ${BASELINE_FONTS.hash.slice(0, 12)}…): live Google Fonts bytes cannot be pinned; pass --out <another file> for an online run`)
if (WRITING_BASELINE && FONT_INPUTS.hash !== BASELINE_FONTS.hash) throw new Error(`the fonts in ${FONTS} (${FONT_INPUTS.files} inputs, hash ${FONT_INPUTS.hash.slice(0, 12)}…) are not the recording's (${BASELINE_FONTS.files} inputs, hash ${BASELINE_FONTS.hash.slice(0, 12)}…): measurements/prototype.json is written only from the pinned fonts (the README says how they were fetched); pass --out <another file> for a run with these`)
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
  { name: '390@200%text', width: 390, height: 844, mobile: true, textZoom: 2 },
  { name: '320@200%text', width: 320, height: 568, mobile: true, textZoom: 2 },
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

// A probe that finds nothing must fail the run, never record a clean result (measure-current.mjs does the same).
function expectCounts(m, headers, rows, key) {
  const problems = []
  if (!m.kpi || m.kpi.length !== 4) problems.push(`${(m.kpi || []).length} KPI cards, expected 4`)
  if (!m.table) problems.push('no metrics table')
  else {
    if (m.table.columns.length !== headers) problems.push(`${m.table.columns.length} header cells, expected ${headers}`)
    if (m.table.rows !== rows) problems.push(`${m.table.rows} metric rows, expected the dataset's ${rows}`)
  }
  if (problems.length) throw new Error(`${key}: ${problems.join('; ')}`)
}

async function run() {
  const browser = await chromium.launch()
  const results = { generatedAt: new Date().toISOString(), environment: { chromium: browser.version(), platform: `${process.platform} ${process.arch}`, node: process.version, fonts: FONT_INPUTS, commit: git('git rev-parse --short HEAD'), prototypeTree: git('git rev-parse HEAD:./prototype'), dirty }, configs: [] }
  for (const theme of ['light', 'dark']) {
    for (const cfg of CONFIGS) {
      const context = await browser.newContext({ viewport: { width: cfg.width, height: cfg.height }, deviceScaleFactor: cfg.dsf || 1, isMobile: !!cfg.mobile, hasTouch: !!cfg.mobile, reducedMotion: 'reduce' })
      await routeFonts(context)
      await context.addInitScript((t) => { try { localStorage.setItem('proto-theme', t) } catch {} }, theme)
      const page = await context.newPage()
      await page.goto(PROTO_URL, { waitUntil: 'load' })
      await page.evaluate(() => document.fonts.ready)
      for (const stateName of STATES) {
        const rows = await page.evaluate((s) => window.EN_STATES[s].dataset.series.length, stateName)
        for (const mode of MODES) {
          await page.evaluate(({ stateName, mode, textZoom }) => {
            window.EN_PROTO.state.stateName = stateName
            window.EN_PROTO.state.mode = mode
            window.EN_PROTO.state.window = '12'
            document.documentElement.style.fontSize = textZoom ? `${textZoom * 100}%` : ''
            window.EN_PROTO.render()
          }, { stateName, mode, textZoom: cfg.textZoom || null })
          await page.waitForTimeout(120)
          const m = await page.evaluate((w) => window.EN_PROTO.measure(w), cfg.width)
          expectCounts(m, 13, rows, `${stateName}/${mode}/${theme}/${cfg.name}`)
          // A hovered sticky row header must paint an opaque fill (review item 17, #1206's rule): a translucent
          // wash lets the values scrolling beneath it show through, a state the rest-position probe cannot see.
          if (mode === 'proposed') {
            const label = `${stateName}/${mode}/${theme}/${cfg.name}`
            // Aim the pointer at the visible part of the first row header ourselves: the prototype bar (not
            // part of the design) is sticky and must not take the pointer, and below 640 px the table starts
            // at its newest columns, so the container is scrolled to the start first. The probe proves the
            // hover landed (the row's cells change fill) before it judges the header's fill.
            const target = await page.evaluate(() => {
              const bar = document.querySelector('.proto-bar'); if (bar) bar.style.pointerEvents = 'none'
              const scroll = document.querySelector('.metrics-scroll'); scroll.scrollLeft = 0
              const th = document.querySelector('table.metrics tbody tr th.sticky'); th.scrollIntoView({ block: 'center' })
              const td = th.parentElement.querySelector('td')
              const r = th.getBoundingClientRect(), c = scroll.getBoundingClientRect()
              const left = Math.max(r.left, c.left, 0), right = Math.min(r.right, c.right, window.innerWidth), top = Math.max(r.top, c.top, 0), bottom = Math.min(r.bottom, c.bottom, window.innerHeight)
              return { x: (left + right) / 2, y: (top + bottom) / 2, visible: right > left && bottom > top, tdRest: getComputedStyle(td).backgroundColor }
            })
            if (!target.visible) throw new Error(`${label}: the first row header is not visible for the hover probe`)
            await page.mouse.move(target.x, target.y)
            m.stickyHover = await page.evaluate((tdRest) => {
              const th = document.querySelector('table.metrics tbody tr th.sticky'), td = th.parentElement.querySelector('td')
              const fill = getComputedStyle(th).backgroundColor
              const channels = (fill.match(/^rgba?\(([^)]+)\)$/) || [, ''])[1].split(/[\s,/]+/).filter(Boolean)
              const bar = document.querySelector('.proto-bar'); if (bar) bar.style.pointerEvents = ''
              return { fill, opaque: channels.length === 3 || (channels.length === 4 && parseFloat(channels[3]) >= 1), rowHovered: getComputedStyle(td).backgroundColor !== tdRest }
            }, target.tdRest)
            await page.mouse.move(0, 0)
            await page.evaluate(() => window.scrollTo(0, 0))
            if (!m.stickyHover.rowHovered) throw new Error(`${label}: the hover probe did not reach the row (its cells kept their resting fill)`)
            if (!m.stickyHover.opaque) throw new Error(`${label}: the hovered sticky row header paints ${m.stickyHover.fill}, not an opaque fill`)
          }
          // Does the proposed table fit without scrolling in the "Newest 6" window?
          let window6 = null
          if (mode === 'proposed') {
            await page.evaluate(() => { window.EN_PROTO.state.window = '6n'; window.EN_PROTO.render() })
            await page.waitForTimeout(80)
            const m6 = await page.evaluate((w) => window.EN_PROTO.measure(w), cfg.width)
            expectCounts(m6, 7, rows, `${stateName}/${mode}/${theme}/${cfg.name}/newest6`)
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
          if (mode === 'proposed' && stateName === 'legacy') console.log(theme, cfg.name, 'overflow', m.pageOverflowPx, 'kpi worst', m.kpi.map((k) => k.worstOverflowPx).join(','), 'clippedCells', m.table && m.table.clippedCount, 'occludedPositions', m.table && m.table.occludedPositions.length, 'readableCols', m.table && m.table.readableColumns, 'stickyHover', m.stickyHover && m.stickyHover.fill, 'valueTop', [...new Set(m.kpi.map((k) => k.valueTop))].join('/'), 'table', m.table && `${m.table.tableWidth}/${m.table.containerWidth} cols ${m.table.minColumn}-${m.table.maxColumn} scrolls=${m.table.scrolls} clipped=${m.table.cellTextClipped} occluded=${m.table.occludedAtFarRight.length}`, 'win6', window6 && `${window6.tableWidth}/${window6.containerWidth} scrolls=${window6.scrolls}`)
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
