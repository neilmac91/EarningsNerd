// Measures the CURRENT production components (the repo's own frontend build, `next start`) on the
// (The recorded run, measurements/current.json, is of main at 97293e7, before #1199–#1203; the probes
// below find the markup of that build AND of main after #1200/#1202 by data attribute, and every
// probe asserts how many elements it found so a markup change fails the run instead of passing it.)
// real META 12-quarter dataset in its production-like legacy state, with every API answered inside
// the browser (page.route) — the same no-backend discipline as tests/e2e. Records page overflow,
// KPI card-child containment, the metrics table's width and per-column widths, sticky-column
// occlusion at the start, every column boundary and the far-right end (with the table's scroll-snap-type), and the count of repeated source-check labels, at six viewport
// widths, both themes, 200% browser zoom (CSS viewport halved at 2x) and 200% text size at 1480, 390 and 320
// (the same profiles as measure-proto.mjs, so the two recorded runs compare like for like).
//
//   node harness/measure-current.mjs [--build <checkout>] [--port 3100 | --base <url>] [--data prototype/data] [--out file] [--shots dir]
//
// Run from tasks/analysis-redesign-2026-10/. Needs the global Playwright (NODE_PATH) or the frontend's.
// measurements/current.json is the recording of main at 97293e7 and is written only for a served build of that
// revision. --build names the checkout whose frontend/ build is measured (default: this harness's own repository);
// the run reads its commit, its frontend/ tree hash, its uncommitted files under frontend/ and its .next/BUILD_ID.
// By default the harness serves that build itself: `next start` through Next's own CLI on this Node, on --port
// (default 3100), in build-hash.mjs's controlled environment with WAITLIST_MODE=false (the middleware's gate on
// /analysis), refusing the untracked env files Next would load at start, and it stops the server when the run ends and
// records how it ran it. --base <url> measures a server started elsewhere instead, whose environment the harness
// cannot see; the baseline refuses it. Either way the run verifies before measuring that the server serves that build
// id. On any other build the run
// needs --out naming another file (a fresh measurement of the shipped components, never a comparison with the
// recording), and it refuses an --out that holds a recording of another commit; the revision is enforced whenever
// the output is the baseline file, named by --out or defaulted (paths compare canonically: a symbolic link to the
// baseline, a path through a linked directory, or a hard link on the baseline's inode is the baseline; a dangling
// link and any other multiply linked output are refused). The fixtures --data names (default: prototype/data)
// are recorded by a content hash of their .js files and, inside this repository, by their tree hash with their
// uncommitted files; the baseline is written only for the legacy state from the committed fixtures whose content
// hash BASELINE pins, from clean trees (no uncommitted frontend, harness or fixture files) and from a build that
// build-stamped.mjs stamped with its source tree, build inputs and output (frontend/.next/SOURCE_TREE.json; .next is
// ignored by git, so the stamp is the only link between a build and its inputs; when present it must name the served
// build id and the checkout's frontend/ tree, its media hash must match the build's .next/static/media, where the
// fonts next/font downloaded sit, and its output hash must match everything the build wrote under .next but Next's
// caches, so a file edited, added or removed there after the stamp is caught); for the baseline the stamp must be of
// build-hash.mjs's STAMP_FORMAT (the build ran `next build` itself, not through npm, right after `npm ci` installed
// the lockfile's packages, with no Node flags but heap sizes, and the stamp records its output), its public build
// variables and media hash must equal the pins in BASELINE, and the harness must serve the build itself.
// 97293e7 has no harness, so the baseline is retaken by running this tree's harness with --build pointing at a
// worktree of that revision, built there with build-stamped.mjs.
import { readFileSync, readdirSync, mkdirSync, writeFileSync, existsSync, lstatSync, realpathSync, statSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execSync, spawn } from 'node:child_process'
import { createServer } from 'node:net'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { ENV_FILES, STAMP_FORMAT, controlledEnv, hashMedia, hashOutput, heapOptions } from './build-hash.mjs'
// The cloud image ships Playwright globally (NODE_PATH, CommonJS); the frontend's own @playwright/test works too.
const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) => (a.startsWith('--') ? [a.slice(2), all[i + 1]] : [])).filter((x) => x.length))
// The server: the harness's own unless --base names one started elsewhere.
const OWN_SERVER = !args.base
const PORT = Number(args.port || 3100)
if (OWN_SERVER && !(Number.isInteger(PORT) && PORT > 0 && PORT < 65536)) throw new Error(`--port ${args.port} is not a port number`)
const BASE = args.base || `http://localhost:${PORT}`
const ROOT = realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'))
// A path with every existing component resolved through its symbolic links, so an alias of a file (a link to it, or
// a path through a linked directory) compares equal to the file; a dangling link is refused rather than written through.
const canonical = (p) => {
  const rest = []
  let cur = p
  while (!existsSync(cur)) {
    try { if (lstatSync(cur).isSymbolicLink()) throw new Error(`${cur} is a dangling symbolic link: pass a real path`) } catch (e) { if (e.code !== 'ENOENT') throw e }
    rest.unshift(path.basename(cur)); const parent = path.dirname(cur); if (parent === cur) break; cur = parent
  }
  return path.join(realpathSync(cur), ...rest)
}
const DATA = canonical(path.resolve(ROOT, args.data || 'prototype/data'))
const STATE = args.state || 'legacy'
// The baseline's inputs: the revision whose build it measures, the fixtures it was fed (prototype/data at the tree
// below, pinned by the content hash of its .js files), and the build's inputs outside the tree: the public variables
// the build inlined (the README's command passes exactly these) and the fonts and assets next/font and the build put
// in .next/static/media (two builds of 97293e7 on 2026-10-11 hashed alike). Retaking it with other inputs needs a new
// pin here and a README note.
const BASELINE = {
  file: 'measurements/current.json',
  revision: '97293e76fe71ff6b7e1848d57f00e808866e8c1c',
  fixtureTree: '50e1c7d92925eaba6503a21979b556679f25760d',
  fixtureHash: '001717037fc42562f06978020451d4e355d99ad5656aa6f478b1f20cb0b17180',
  buildEnv: { NEXT_PUBLIC_API_BASE_URL: 'http://localhost:8010', NEXT_PUBLIC_ENABLE_ANALYSIS: 'true' },
  media: { files: 26, hash: 'd7c8317fed90f1bd87eff175eed351ef4715eb870551ea3f11d478ff79c2030c' },
}
const git =(cwd, cmd) => { try { return execSync(`git ${cmd}`, { cwd, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() } catch { return null } }
// The served build: the checkout whose frontend/ was built and is served at --base (default: this repository).
const BUILD = path.resolve(args.build || path.join(ROOT, '..', '..'))
const buildIdFile = path.join(BUILD, 'frontend', '.next', 'BUILD_ID')
if (!existsSync(buildIdFile)) throw new Error(`no frontend build at ${BUILD} (${path.relative(process.cwd(), buildIdFile) || buildIdFile} is missing): build it there first, or pass --build <the checkout whose build the server serves>`)
const SERVED = {
  commit: git(BUILD, 'rev-parse HEAD') || '',
  frontendTree: git(BUILD, 'rev-parse HEAD:frontend'),
  dirty: (git(BUILD, 'status --porcelain -- frontend') || '').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, '')),
  buildId: readFileSync(buildIdFile, 'utf8').trim(),
  builtAt: statSync(buildIdFile).mtime.toISOString(),
}
if (!SERVED.commit) throw new Error(`${BUILD} is not a git checkout: pass --build <the checkout whose build the server serves>`)
// The build's stamp, written by build-stamped.mjs right after `npm run build` from a clean frontend tree. The
// harness cannot see which tree a build came from (.next is ignored by git), so a stamped build is required for
// the baseline and, whenever a stamp is present, it must name this build id and the checkout's frontend/ tree, and
// the build's output and media must still hash as the stamp recorded them (build-hash.mjs: the server's own writes
// while it serves, its route cache, are left out).
const nextDir = path.join(BUILD, 'frontend', '.next')
const stampFile = path.join(nextDir, 'SOURCE_TREE.json')
let STAMP = null
if (existsSync(stampFile)) {
  try { STAMP = JSON.parse(readFileSync(stampFile, 'utf8')) } catch { throw new Error(`${stampFile} is not JSON: rebuild with harness/build-stamped.mjs`) }
  if (!STAMP || STAMP.buildId !== SERVED.buildId) throw new Error(`the stamp at ${stampFile} names build ${STAMP && STAMP.buildId}, but the build there is ${SERVED.buildId}: rebuild with harness/build-stamped.mjs`)
  if (STAMP.output) { const output = hashOutput(nextDir); if (output.hash !== STAMP.output.hash) throw new Error(`the build at ${BUILD} is not the output its stamp recorded right after the build: .next outside Next's caches holds ${output.files} files hashing ${output.hash.slice(0, 12)}…, the stamp ${STAMP.output.files} files hashing ${String(STAMP.output.hash).slice(0, 12)}…, so a file there was edited, added or removed since: rebuild with harness/build-stamped.mjs`) }
  if (STAMP.media) { const media = hashMedia(nextDir); if (media.hash !== STAMP.media.hash) throw new Error(`the build at ${BUILD} holds other fonts and assets in .next/static/media (${media.files} files, ${media.hash.slice(0, 12)}…) than its stamp records (${STAMP.media.files} files, ${String(STAMP.media.hash).slice(0, 12)}…): rebuild with harness/build-stamped.mjs`) }
  if (STAMP.frontendTree !== SERVED.frontendTree) throw new Error(`the build at ${BUILD} was stamped from frontend tree ${String(STAMP.frontendTree).slice(0, 7)}, but the checkout's frontend/ is ${String(SERVED.frontendTree).slice(0, 7)}: rebuild with harness/build-stamped.mjs from the checkout the server should serve`)
}
// A build older than the checkout's last commit touching frontend/ cannot be that checkout's build (the harness
// cannot see which tree a build came from, so build from the checkout right before measuring).
const lastFrontendCommit = git(BUILD, 'log -1 --format=%h%x20%ct -- frontend')
if (lastFrontendCommit) { const [hash, ct] = lastFrontendCommit.split(' '); const committedAt = new Date(Number(ct) * 1000); if (new Date(SERVED.builtAt) < committedAt) throw new Error(`the build at ${BUILD} (${SERVED.builtAt}) predates its checkout's last frontend commit (${hash} at ${committedAt.toISOString()}): rebuild from that checkout before measuring`) }
// The harness's own server runs Next's CLI from the build's checkout in the controlled environment; `next start`
// loads the same env files `next build` does, so untracked ones are refused here too.
const SERVE = OWN_SERVER ? { nextBin: path.join(BUILD, 'frontend', 'node_modules', 'next', 'dist', 'bin', 'next'), env: controlledEnv({ WAITLIST_MODE: 'false' }), nodeOptions: heapOptions() || null } : null
if (SERVE) {
  if (!existsSync(SERVE.nextBin)) throw new Error(`${SERVE.nextBin} is missing: build ${BUILD} with harness/build-stamped.mjs first`)
  const envFiles = ENV_FILES.filter((f) => existsSync(path.join(BUILD, 'frontend', f)) && !git(BUILD, `ls-files -- frontend/${f}`))
  if (envFiles.length) throw new Error(`untracked env files in ${path.join(BUILD, 'frontend')} (${envFiles.join(', ')}) would feed the server values its tree does not hold: move them aside`)
}
const sameCommit = (a, b) => !!a && !!b && (a.startsWith(b) || b.startsWith(a))
// Output and baseline compare as canonical paths: a symbolic link to the baseline, or a path through a linked
// directory, is the baseline and meets every baseline guard. Hard links share an inode under different names,
// which realpath does not collapse, so an existing output on the baseline's inode is the baseline too, and any
// other output with more than one hard link is refused (the harness cannot tell what else it would overwrite).
const sameFile = (a, b) => { if (!existsSync(a) || !existsSync(b)) return false; const x = statSync(a), y = statSync(b); return x.dev === y.dev && x.ino === y.ino }
const BASELINE_PATH = canonical(path.resolve(ROOT, BASELINE.file))
const outArg = canonical(path.resolve(ROOT, args.out || BASELINE.file))
const OUT = sameFile(outArg, BASELINE_PATH) ? BASELINE_PATH : outArg
const WRITING_BASELINE = OUT === BASELINE_PATH
if (!WRITING_BASELINE && existsSync(OUT) && statSync(OUT).nlink > 1) throw new Error(`${OUT} has ${statSync(OUT).nlink} hard links, so writing it would overwrite a file under another name: pass an --out with one name`)
// The revision is enforced whenever the output is the baseline, however that path was chosen.
if (WRITING_BASELINE && !sameCommit(SERVED.commit, BASELINE.revision)) throw new Error(`${BASELINE.file} is the recording of main at ${BASELINE.revision.slice(0, 7)}; the served build (${BUILD}) is ${SERVED.commit.slice(0, 7)}: pass --out <another file> for a fresh measurement of this build (it does not compare with the recording), or --build <a worktree of ${BASELINE.revision.slice(0, 7)} whose build the server serves> to retake the baseline`)
if (existsSync(OUT)) {
  let recorded = null
  try { recorded = (JSON.parse(readFileSync(OUT, 'utf8')).environment || {}).commit || null } catch {}
  if (recorded && !sameCommit(SERVED.commit, recorded)) throw new Error(`${path.relative(ROOT, OUT)} records a run of ${recorded}; the served build is ${SERVED.commit.slice(0, 7)}: pass a different --out`)
}
const HARNESS_COMMIT = (git(ROOT, 'rev-parse HEAD') || '').slice(0, 7)
const HARNESS_DIRTY = (git(ROOT, 'status --porcelain -- harness') || '').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, ''))
// The fixtures the page is fed (--data): recorded by a content hash of their .js files, and, when they are a
// directory of this repository, by their committed tree hash with their uncommitted files.
const CANONICAL_DATA = canonical(path.resolve(ROOT, 'prototype/data'))
const dataFiles = readdirSync(DATA).filter((f) => f.endsWith('.js')).sort()
const dataHash = createHash('sha256'); for (const f of dataFiles) { dataHash.update(`${f}\0`); dataHash.update(readFileSync(path.join(DATA, f))); dataHash.update('\0') }
const dataInRepo = git(DATA, 'rev-parse --show-toplevel') === git(ROOT, 'rev-parse --show-toplevel')
const FIXTURES = {
  dir: DATA,
  hash: dataHash.digest('hex'),
  tree: dataInRepo ? git(ROOT, `rev-parse HEAD:./${path.relative(ROOT, DATA)}`) : null,
  dirty: dataInRepo ? (git(ROOT, `status --porcelain -- ${path.relative(ROOT, DATA)}`) || '').split('\n').map((l) => l.trim()).filter(Boolean).map((l) => l.replace(/^\S+\s+/, '')) : null,
}
// The baseline is written only for the legacy state from the committed fixtures and from clean trees, so its
// recorded state, commit and tree hashes identify the measured code and data.
if (WRITING_BASELINE) {
  if (STATE !== 'legacy') throw new Error(`${BASELINE.file} records the legacy state (the production-like dataset); --state ${STATE} needs --out <another file>`)
  if (DATA !== CANONICAL_DATA) throw new Error(`${BASELINE.file} records the committed fixtures in prototype/data; --data ${DATA} needs --out <another file>`)
  if (FIXTURES.hash !== BASELINE.fixtureHash) throw new Error(`${BASELINE.file} records the fixtures at tree ${BASELINE.fixtureTree.slice(0, 7)} (content hash ${BASELINE.fixtureHash.slice(0, 12)}…); prototype/data now hashes ${FIXTURES.hash.slice(0, 12)}… (tree ${String(FIXTURES.tree).slice(0, 7)}): retaking the baseline from other fixtures needs a new pin in BASELINE and a note in the README, or pass --out <another file>`)
  const what = [SERVED.dirty.length ? `uncommitted frontend files in ${BUILD} (${SERVED.dirty.join(', ')})` : null, HARNESS_DIRTY.length ? `uncommitted harness files (${HARNESS_DIRTY.join(', ')})` : null, FIXTURES.dirty && FIXTURES.dirty.length ? `uncommitted fixture files (${FIXTURES.dirty.join(', ')})` : null].filter(Boolean).join(' and ')
  if (what) throw new Error(`${BASELINE.file} is written only from clean trees: ${what}; commit or stash them, or pass --out <another file>`)
  if (!OWN_SERVER) throw new Error(`${BASELINE.file} is measured only on a server the harness starts itself, in the controlled environment it records; a server at --base ${args.base} runs in an environment the harness cannot see: drop --base (and pass --port if 3100 is taken)`)
  if (!STAMP) throw new Error(`${BASELINE.file} is written only from a stamped build: build ${BUILD} with harness/build-stamped.mjs (it writes frontend/.next/SOURCE_TREE.json from the clean checkout right after the build) and serve that build`)
  if (STAMP.format !== STAMP_FORMAT) throw new Error(`${BASELINE.file} is written only from a stamp of format ${STAMP_FORMAT} (the build ran \`next build\` itself, not through npm, right after \`npm ci\` installed the lockfile's packages, with no Node flags but heap sizes, and the stamp records its whole output); the stamp at ${stampFile} is ${STAMP.format === undefined ? 'from an older build-stamped.mjs' : `of format ${JSON.stringify(STAMP.format)}`}: rebuild with harness/build-stamped.mjs (the README's command)`)
  const env =STAMP.env ? JSON.stringify(STAMP.env) : null
  if (env !== JSON.stringify(BASELINE.buildEnv)) throw new Error(`${BASELINE.file} records a build whose public build variables were exactly ${JSON.stringify(BASELINE.buildEnv)}; the stamp at ${stampFile} records ${env || 'none (it predates recorded build inputs)'}: rebuild with harness/build-stamped.mjs and exactly those variables (the README's command)`)
  if (!STAMP.media || STAMP.media.hash !== BASELINE.media.hash) throw new Error(`${BASELINE.file} records a build whose downloaded fonts and assets hash ${BASELINE.media.hash.slice(0, 12)}… (${BASELINE.media.files} files in .next/static/media); the build at ${BUILD} has ${STAMP.media ? `${STAMP.media.hash.slice(0, 12)}… (${STAMP.media.files} files)` : 'none recorded'}: retaking the baseline with other fonts needs a new pin here and a README note`)
}
const SHOTS = args.shots || null
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
  // sides of each cell's content box, and visit the start, every column boundary and the far-right end, as the
  // prototype's do.
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
      // Rest positions. A table that snaps rests only at its column boundaries; one that does not (the build at 97293e7)
      // rests wherever a scroll stops, and every position between two boundaries leaves a period column straddling
      // the sticky edge. The probe visits the start, every column boundary (the scroll position at which a period
      // header's left edge meets the sticky column's right edge, clamped to the range) and the far-right end, where a
      // range that is not a whole number of columns leaves a column straddling, and records the table's scroll-snap-type.
      const snap = getComputedStyle(scroller).scrollSnapType
      const occluded = []
      let restPositions = 0
      if (ths.length > 1 && table.scrollWidth > scroller.clientWidth + 1) {
        const range = scroller.scrollWidth - scroller.clientWidth
        scroller.scrollLeft = 0
        await settle()
        const edge = r(ths[0]).right
        const sorted = [0, ...ths.slice(1).map((th) => r(th).left - edge), range].map((x) => Math.min(Math.max(x, 0), range)).sort((a, b) => a - b)
        const stops = sorted.filter((x, i) => i === 0 || x - sorted[i - 1] > EPS)
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
      tableInfo = { tableWidth: Math.round(table.scrollWidth), containerWidth: Math.round(scroller.clientWidth), columns: cols, warnedWidths: cols.filter((c) => c.warned).map((c) => c.width), cleanWidths: cols.slice(1).filter((c) => !c.warned).map((c) => c.width), snap, restPositions, occludedPositions: occluded, occludedAtFarRight: occluded.filter((o) => o.scrollLeft >= (scroller.scrollWidth - scroller.clientWidth) - 1), clippedCount: clipped.length, clippedCells: clipped.slice(0, 8) }
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

// The harness's own server: a taken port is refused (another server there could answer for this build), `next start`
// runs until it serves this build's manifest, and it is stopped when the run ends, however it ends.
const portFree = (port) => new Promise((resolve) => { const probe = createServer(); probe.once('error', () => resolve(false)); probe.listen(port, () => probe.close(() => resolve(true))) })
async function serve() {
  if (!(await portFree(PORT))) throw new Error(`port ${PORT} is taken, so another server could answer for this build: stop it, or pass --port <a free port>`)
  const child = spawn(process.execPath, [SERVE.nextBin, 'start', '-p', String(PORT)], { cwd: path.join(BUILD, 'frontend'), env: SERVE.env, stdio: ['ignore', 'pipe', 'pipe'] })
  let log = ''
  child.stdout.on('data', (d) => { log += d })
  child.stderr.on('data', (d) => { log += d })
  process.on('exit', () => child.kill())
  const tail = () => log.trim().split('\n').slice(-3).join(' / ')
  const manifest = `${BASE}/_next/static/${SERVED.buildId}/_buildManifest.js`
  for (const deadline = Date.now() + 60000; Date.now() < deadline;) {
    if (child.exitCode !== null) throw new Error(`next start for ${BUILD} exited (${child.exitCode}) before serving on port ${PORT}: ${tail()}`)
    try { if ((await fetch(manifest)).status === 200) return child } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  child.kill()
  throw new Error(`next start for ${BUILD} did not serve its build manifest on port ${PORT} within 60 s: ${tail()}`)
}

async function run() {
  const server = SERVE ? await serve() : null
  try { await measureAll() } finally { if (server) server.kill() }
}

async function measureAll() {
  const browser = await chromium.launch()
  const results = { base: BASE, server: SERVE ? { by: 'measure-current.mjs', command: 'next start', port: PORT, nodeOptions: SERVE.nodeOptions, waitlistMode: 'false' } : { by: 'external' }, state: STATE, data: path.relative(ROOT, DATA), generatedAt: new Date().toISOString(), environment: { chromium: browser.version(), platform: `${process.platform} ${process.arch}`, node: process.version, commit: SERVED.commit.slice(0, 7), frontendTree: SERVED.frontendTree, dirty: SERVED.dirty, buildId: SERVED.buildId, builtAt: SERVED.builtAt, buildStamp: STAMP, harnessCommit: HARNESS_COMMIT, harnessDirty: HARNESS_DIRTY, fixtureHash: FIXTURES.hash, fixtureTree: FIXTURES.tree, fixtureDirty: FIXTURES.dirty }, configs: [] }
  // The server must serve the build of --build: its build manifest lives under the build id.
  const manifest = await (await browser.newContext()).request.get(`${BASE}/_next/static/${SERVED.buildId}/_buildManifest.js`)
  if (manifest.status() !== 200) { await browser.close(); throw new Error(`${BASE} does not serve the build of ${BUILD} (build id ${SERVED.buildId}: ${manifest.status()} for its build manifest): start the server from that checkout's build, or pass --build <the checkout it serves>, or drop --base to let the harness serve it`) }
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
